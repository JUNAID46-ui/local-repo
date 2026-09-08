from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify

from app.config import settings, PROJECT_ROOT
from app.agents.business_manager import BusinessManager
from app.integrations.google_sheets import GoogleSheetsClient, MockSheetClient, load_active_businesses
from app.models.business import BusinessProfile


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )
    app.secret_key = "seo-content-automation-dev-key"

    biz_manager = BusinessManager()
    _pipeline_status: dict = {"running": False, "last_result": None}

    def _get_businesses() -> list[BusinessProfile]:
        if not settings.google.sheet_id:
            from app.main import get_mock_businesses
            return get_mock_businesses()
        try:
            client = GoogleSheetsClient()
            return load_active_businesses(client)
        except BaseException:
            from app.main import get_mock_businesses
            return get_mock_businesses()

    def _get_log_files() -> list[dict]:
        log_dir = PROJECT_ROOT / settings.paths.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        files = []
        for p in sorted(log_dir.glob("run_*.json"), reverse=True):
            stat = p.stat()
            files.append({
                "name": p.name,
                "path": str(p),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            })
        return files

    def _get_output_files() -> list[dict]:
        output_dir = PROJECT_ROOT / settings.paths.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        files = []
        for p in sorted(output_dir.rglob("*.docx"), reverse=True):
            stat = p.stat()
            rel = p.relative_to(output_dir)
            files.append({
                "name": p.name,
                "rel_path": str(rel),
                "abs_path": str(p),
                "size_kb": round(stat.st_size / 1024, 1),
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "business": str(rel.parts[0]) if len(rel.parts) > 1 else "Unknown",
                "date": str(rel.parts[1]) if len(rel.parts) > 2 else "",
            })
        return files

    @app.context_processor
    def inject_now():
        return {"now": datetime.now(timezone.utc)}

    @app.route("/")
    def dashboard():
        businesses = _get_businesses()
        logs = _get_log_files()[:5]
        outputs = _get_output_files()[:5]

        total_articles = 0
        for b in businesses:
            state = biz_manager.load_state(b.business_id)
            total_articles += state.total_articles_generated

        stats = {
            "total_businesses": len(businesses),
            "active_businesses": sum(1 for b in businesses if b.active),
            "total_articles": total_articles,
            "recent_logs": len(logs),
            "total_documents": len(_get_output_files()),
        }

        last_log = None
        if logs:
            try:
                with open(logs[0]["path"]) as f:
                    last_log = json.load(f)
            except Exception:
                pass

        return render_template(
            "dashboard.html",
            stats=stats,
            businesses=businesses,
            recent_logs=logs,
            recent_outputs=outputs,
            last_log=last_log,
            pipeline_running=_pipeline_status["running"],
        )

    @app.route("/businesses")
    def businesses_list():
        businesses = _get_businesses()
        business_data = []
        for b in businesses:
            state = biz_manager.load_state(b.business_id)
            business_data.append({"profile": b, "state": state})
        return render_template("businesses.html", businesses=business_data)

    @app.route("/businesses/<business_id>")
    def business_detail(business_id: str):
        businesses = _get_businesses()
        business = next((b for b in businesses if b.business_id == business_id), None)
        if not business:
            flash("Business not found.", "error")
            return redirect(url_for("businesses_list"))
        state = biz_manager.load_state(business_id)
        outputs = [f for f in _get_output_files() if f["business"].lower().replace("_", " ") in business.business_name.lower().replace("_", " ") or business.output_folder and f["business"] == business.output_folder]
        return render_template("business_detail.html", business=business, state=state, outputs=outputs)

    @app.route("/runs")
    def runs_list():
        logs = _get_log_files()
        return render_template("runs.html", logs=logs)

    @app.route("/runs/<log_name>")
    def run_detail(log_name: str):
        log_path = PROJECT_ROOT / settings.paths.log_dir / log_name
        if not log_path.exists():
            flash("Log file not found.", "error")
            return redirect(url_for("runs_list"))
        with open(log_path) as f:
            log_data = json.load(f)
        return render_template("run_detail.html", log=log_data, log_name=log_name)

    @app.route("/documents")
    def documents_list():
        outputs = _get_output_files()
        return render_template("documents.html", outputs=outputs)

    @app.route("/documents/download")
    def download_document():
        path = request.args.get("path", "")
        abs_path = Path(path)
        output_dir = PROJECT_ROOT / settings.paths.output_dir
        if not abs_path.exists() or not str(abs_path).startswith(str(output_dir)):
            flash("File not found or access denied.", "error")
            return redirect(url_for("documents_list"))
        return send_file(abs_path, as_attachment=True)

    @app.route("/settings")
    def settings_page():
        config = {
            "Schedule": {
                "Timezone": settings.schedule.timezone,
                "Hour": settings.schedule.hour,
                "Minute": settings.schedule.minute,
            },
            "Content": {
                "Max Articles per Business": settings.content.max_articles_per_business,
                "Target Keyword Density": f"{settings.content.target_keyword_density}%",
                "Density Tolerance": f"+/- {settings.content.keyword_density_tolerance}%",
                "Max Revision Attempts": settings.content.max_revision_attempts,
                "Meta Description Length": f"{settings.content.meta_description_min_length}-{settings.content.meta_description_max_length} chars",
                "Article Word Count": f"{settings.content.min_article_word_count}-{settings.content.max_article_word_count} words",
            },
            "Models": {
                "Primary (Writing)": settings.models.primary,
                "Research": settings.models.research,
                "Validation": settings.models.validation,
            },
            "Paths": {
                "Output Directory": settings.paths.output_dir,
                "Log Directory": settings.paths.log_dir,
                "Data Directory": settings.paths.data_dir,
            },
            "Images": {
                "Featured Count": settings.images.featured_count,
                "Supporting Range": f"{settings.images.supporting_min}-{settings.images.supporting_max}",
            },
        }
        api_configured = bool(settings.anthropic_api_key)
        sheets_configured = bool(settings.google.sheet_id)
        return render_template(
            "settings.html",
            config=config,
            api_configured=api_configured,
            sheets_configured=sheets_configured,
        )

    @app.route("/pipeline/run", methods=["POST"])
    def trigger_pipeline():
        if _pipeline_status["running"]:
            flash("Pipeline is already running.", "warning")
            return redirect(url_for("dashboard"))

        business_id = request.form.get("business_id", "").strip() or None
        dry_run = request.form.get("dry_run") == "on"
        use_mock = request.form.get("use_mock") == "on"

        def _run():
            from app.main import run_pipeline
            _pipeline_status["running"] = True
            try:
                run_pipeline(
                    business_id=business_id,
                    dry_run=dry_run,
                    use_mock=use_mock,
                )
            finally:
                _pipeline_status["running"] = False

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        mode = "dry run" if dry_run else ("mock" if use_mock else "full")
        flash(f"Pipeline started ({mode} mode). Refresh to check progress.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/api/status")
    def api_status():
        return jsonify({"running": _pipeline_status["running"]})

    return app
