from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify

from app.config import settings, PROJECT_ROOT
from app.agents.business_manager import BusinessManager
from app.integrations.google_sheets import GoogleSheetsClient, MockSheetClient, load_active_businesses
from app.models.business import BusinessProfile
from app.utils.text import sanitize_filename


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )
    app.secret_key = "seo-content-automation-dev-key"

    biz_manager = BusinessManager()
    _pipeline_status: dict = {
        "running": False,
        "current_business": "",
        "current_stage": "",
        "current_topic": "",
        "stage_index": 0,
        "total_stages": 12,
        "started_at": "",
        "completed_businesses": 0,
        "total_businesses": 0,
        "mode": "",
        "errors": [],
    }

    PIPELINE_STAGES = [
        "Business Validation",
        "Topic Selection",
        "Keyword Research",
        "SEO Research",
        "AEO/GEO Research",
        "Web Research",
        "Content Writing",
        "SEO Editing",
        "Fact Checking",
        "Quality Control",
        "DOCX Generation",
        "Complete",
    ]

    _local_businesses_file = PROJECT_ROOT / "data" / "local_businesses.json"

    def _load_local_businesses() -> list[BusinessProfile]:
        if _local_businesses_file.exists():
            with open(_local_businesses_file) as f:
                data = json.load(f)
            return [BusinessProfile(**b) for b in data]
        return []

    def _save_local_businesses(businesses: list[BusinessProfile]) -> None:
        _local_businesses_file.parent.mkdir(parents=True, exist_ok=True)
        data = [b.model_dump() for b in businesses]
        with open(_local_businesses_file, "w") as f:
            json.dump(data, f, indent=2)

    def _get_businesses() -> list[BusinessProfile]:
        local = _load_local_businesses()
        if not settings.google.sheet_id:
            from app.main import get_mock_businesses
            return local + get_mock_businesses()
        try:
            client = GoogleSheetsClient()
            sheet_biz = load_active_businesses(client)
            return local + sheet_biz
        except BaseException:
            from app.main import get_mock_businesses
            return local + get_mock_businesses()

    def _get_log_files() -> list[dict]:
        log_dir = PROJECT_ROOT / settings.paths.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        files = []
        for p in sorted(log_dir.glob("run_*.json"), reverse=True):
            stat = p.stat()
            try:
                with open(p) as f:
                    log_data = json.load(f)
                entry_count = len(log_data.get("entries", []))
                duration = log_data.get("duration_seconds", 0)
                run_id = log_data.get("run_id", "")
                biz_entries = [e for e in log_data.get("entries", []) if e.get("event") == "business_complete"]
                completed = sum(1 for e in biz_entries if e.get("status") in ("completed", "dry_run"))
                failed = sum(1 for e in log_data.get("entries", []) if e.get("event") == "error")
            except Exception:
                entry_count = 0
                duration = 0
                run_id = ""
                completed = 0
                failed = 0
            files.append({
                "name": p.name,
                "path": str(p),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "entry_count": entry_count,
                "duration": round(duration, 1),
                "run_id": run_id,
                "completed": completed,
                "failed": failed,
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
    def inject_globals():
        return {
            "now": datetime.now(timezone.utc),
            "pipeline_running": _pipeline_status["running"],
            "schedule_time": f"{settings.schedule.hour:02d}:{settings.schedule.minute:02d}",
            "schedule_tz": settings.schedule.timezone,
        }

    # ── Pages ──

    @app.route("/")
    def dashboard():
        businesses = _get_businesses()
        logs = _get_log_files()[:5]
        outputs = _get_output_files()[:10]

        total_articles = 0
        last_run_date = ""
        for b in businesses:
            state = biz_manager.load_state(b.business_id)
            total_articles += state.total_articles_generated
            if state.last_run and state.last_run > last_run_date:
                last_run_date = state.last_run

        all_logs = _get_log_files()
        total_failed = sum(lg.get("failed", 0) for lg in all_logs)

        stats = {
            "total_businesses": len(businesses),
            "active_businesses": sum(1 for b in businesses if b.active),
            "total_articles": total_articles,
            "total_documents": len(_get_output_files()),
            "total_runs": len(all_logs),
            "failed_jobs": total_failed,
            "last_run": last_run_date or "Never",
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
            pipeline_status=_pipeline_status,
            stages=PIPELINE_STAGES,
        )

    @app.route("/businesses")
    def businesses_list():
        businesses = _get_businesses()
        business_data = []
        for b in businesses:
            state = biz_manager.load_state(b.business_id)
            business_data.append({"profile": b, "state": state})
        return render_template("businesses.html", businesses=business_data)

    @app.route("/businesses/add", methods=["GET", "POST"])
    def add_business():
        if request.method == "POST":
            biz = BusinessProfile(
                business_id=sanitize_filename(request.form.get("business_name", "")).lower().replace(" ", "_"),
                business_name=request.form.get("business_name", "").strip(),
                website=request.form.get("website", "").strip(),
                location=request.form.get("location", "").strip(),
                country=request.form.get("country", "").strip(),
                industry=request.form.get("industry", "").strip(),
                services=[s.strip() for s in request.form.get("services", "").split(",") if s.strip()],
                primary_service=request.form.get("primary_service", "").strip(),
                target_audience=request.form.get("target_audience", "").strip(),
                business_description=request.form.get("business_description", "").strip(),
                business_facts=[f.strip() for f in request.form.get("business_facts", "").split(",") if f.strip()],
                brand_voice=request.form.get("brand_voice", "professional, helpful, knowledgeable").strip(),
                primary_keywords=[k.strip() for k in request.form.get("primary_keywords", "").split(",") if k.strip()],
                commercial_keywords=[k.strip() for k in request.form.get("commercial_keywords", "").split(",") if k.strip()],
                service_areas=[a.strip() for a in request.form.get("service_areas", "").split(",") if a.strip()],
                existing_content_urls=[u.strip() for u in request.form.get("existing_content_urls", "").split(",") if u.strip()],
                internal_link_base=request.form.get("website", "").strip(),
                output_folder=sanitize_filename(request.form.get("business_name", "")),
                active=True,
            )
            if not biz.business_name:
                flash("Business name is required.", "error")
                return render_template("add_business.html")

            local = _load_local_businesses()
            if any(b.business_id == biz.business_id for b in local):
                flash("A business with this name already exists.", "error")
                return render_template("add_business.html")

            local.append(biz)
            _save_local_businesses(local)
            flash(f"Business '{biz.business_name}' added successfully.", "success")
            return redirect(url_for("business_detail", business_id=biz.business_id))
        return render_template("add_business.html")

    @app.route("/businesses/<business_id>")
    def business_detail(business_id: str):
        businesses = _get_businesses()
        business = next((b for b in businesses if b.business_id == business_id), None)
        if not business:
            flash("Business not found.", "error")
            return redirect(url_for("businesses_list"))
        state = biz_manager.load_state(business_id)
        outputs = [
            f for f in _get_output_files()
            if (business.output_folder and f["business"] == business.output_folder)
            or f["business"].lower().replace("_", " ") in business.business_name.lower().replace("_", " ")
        ]
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
        if not abs_path.exists() or not str(abs_path.resolve()).startswith(str(output_dir.resolve())):
            flash("File not found or access denied.", "error")
            return redirect(url_for("documents_list"))
        return send_file(abs_path, as_attachment=True)

    @app.route("/settings")
    def settings_page():
        config = {
            "Schedule": {
                "Timezone": settings.schedule.timezone,
                "Daily Run Time": f"{settings.schedule.hour:02d}:{settings.schedule.minute:02d}",
            },
            "Content": {
                "Max Articles per Business": settings.content.max_articles_per_business,
                "Target Keyword Density": f"{settings.content.target_keyword_density}%",
                "Density Tolerance": f"+/- {settings.content.keyword_density_tolerance}%",
                "Max Revision Attempts": settings.content.max_revision_attempts,
                "Meta Description Length": f"{settings.content.meta_description_min_length}-{settings.content.meta_description_max_length} chars",
                "Article Word Count": f"{settings.content.min_article_word_count}-{settings.content.max_article_word_count} words",
            },
            "AI Models": {
                "Primary (Writing)": settings.models.primary,
                "Research": settings.models.research,
                "Validation (QA)": settings.models.validation,
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

    # ── Pipeline Control ──

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
            _pipeline_status["started_at"] = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            _pipeline_status["mode"] = "dry run" if dry_run else ("mock" if use_mock else "full")
            _pipeline_status["errors"] = []
            _pipeline_status["current_stage"] = "Starting..."
            _pipeline_status["stage_index"] = 0
            try:
                run_pipeline(
                    business_id=business_id,
                    dry_run=dry_run,
                    use_mock=use_mock,
                )
                _pipeline_status["current_stage"] = "Complete"
                _pipeline_status["stage_index"] = len(PIPELINE_STAGES) - 1
            except Exception as e:
                _pipeline_status["errors"].append(str(e))
                _pipeline_status["current_stage"] = f"Failed: {e}"
            finally:
                _pipeline_status["running"] = False

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        mode = "dry run" if dry_run else ("mock" if use_mock else "full")
        flash(f"Pipeline started ({mode} mode).", "success")
        return redirect(url_for("dashboard"))

    # ── API Endpoints ──

    @app.route("/api/status")
    def api_status():
        return jsonify(_pipeline_status)

    @app.route("/api/businesses")
    def api_businesses():
        businesses = _get_businesses()
        result = []
        for b in businesses:
            state = biz_manager.load_state(b.business_id)
            result.append({
                "id": b.business_id,
                "name": b.business_name,
                "industry": b.industry,
                "location": b.location,
                "services": len(b.services),
                "active": b.active,
                "total_articles": state.total_articles_generated,
                "last_run": state.last_run or "Never",
            })
        return jsonify(result)

    @app.route("/api/businesses/<business_id>")
    def api_business_detail(business_id: str):
        businesses = _get_businesses()
        biz = next((b for b in businesses if b.business_id == business_id), None)
        if not biz:
            return jsonify({"error": "Not found"}), 404
        state = biz_manager.load_state(business_id)
        return jsonify({
            "profile": biz.model_dump(),
            "state": state.model_dump(),
        })

    @app.route("/api/runs")
    def api_runs():
        return jsonify(_get_log_files())

    @app.route("/api/documents")
    def api_documents():
        return jsonify(_get_output_files())

    @app.route("/api/dashboard")
    def api_dashboard():
        businesses = _get_businesses()
        total_articles = 0
        for b in businesses:
            state = biz_manager.load_state(b.business_id)
            total_articles += state.total_articles_generated
        return jsonify({
            "total_businesses": len(businesses),
            "active_businesses": sum(1 for b in businesses if b.active),
            "total_articles": total_articles,
            "total_documents": len(_get_output_files()),
            "total_runs": len(_get_log_files()),
            "pipeline_running": _pipeline_status["running"],
            "schedule": f"{settings.schedule.hour:02d}:{settings.schedule.minute:02d} {settings.schedule.timezone}",
        })

    return app
