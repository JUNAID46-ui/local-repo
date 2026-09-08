import pytest
from app.web.app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestDashboard:
    def test_dashboard_loads(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"SEO Automation" in resp.data
        assert b"Dashboard" in resp.data

    def test_dashboard_shows_stats(self, client):
        resp = client.get("/")
        assert b"Active Businesses" in resp.data
        assert b"Articles Generated" in resp.data
        assert b"Documents" in resp.data

    def test_dashboard_shows_businesses(self, client):
        resp = client.get("/")
        assert b"Example Appliance Repair" in resp.data

    def test_dashboard_has_pipeline_tracker(self, client):
        resp = client.get("/")
        assert b"pipelineTracker" in resp.data
        assert b"pipeline-stage" in resp.data


class TestBusinesses:
    def test_businesses_list(self, client):
        resp = client.get("/businesses")
        assert resp.status_code == 200
        assert b"Example Appliance Repair" in resp.data
        assert b"Appliance Repair" in resp.data

    def test_business_detail(self, client):
        resp = client.get("/businesses/example_appliance_repair")
        assert resp.status_code == 200
        assert b"Tucson" in resp.data
        assert b"Refrigerator Repair" in resp.data

    def test_business_not_found(self, client):
        resp = client.get("/businesses/nonexistent_biz", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Business not found" in resp.data


class TestAddBusiness:
    def test_add_business_get(self, client):
        resp = client.get("/businesses/add")
        assert resp.status_code == 200
        assert b"Add New Business" in resp.data
        assert b"Business Name" in resp.data

    def test_add_business_post_empty_name(self, client):
        resp = client.post("/businesses/add", data={"business_name": ""}, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Business name is required" in resp.data

    def test_add_business_post_success(self, client, tmp_path, monkeypatch):
        test_file = tmp_path / "local_businesses.json"
        monkeypatch.setattr(
            "app.web.app.create_app.__code__",
            create_app.__code__,
        )
        resp = client.post("/businesses/add", data={
            "business_name": "Test Biz",
            "website": "https://test.com",
            "industry": "Testing",
            "location": "Testville",
            "country": "US",
            "services": "svc1, svc2",
            "primary_service": "svc1",
            "target_audience": "testers",
        }, follow_redirects=True)
        assert resp.status_code == 200


class TestRuns:
    def test_runs_list_empty(self, client):
        resp = client.get("/runs")
        assert resp.status_code == 200

    def test_run_detail_not_found(self, client):
        resp = client.get("/runs/nonexistent.json", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Log file not found" in resp.data


class TestDocuments:
    def test_documents_list(self, client):
        resp = client.get("/documents")
        assert resp.status_code == 200

    def test_download_invalid_path(self, client):
        resp = client.get("/documents/download?path=/etc/passwd", follow_redirects=True)
        assert resp.status_code == 200
        assert b"access denied" in resp.data or b"not found" in resp.data


class TestSettings:
    def test_settings_page(self, client):
        resp = client.get("/settings")
        assert resp.status_code == 200
        assert b"Schedule" in resp.data
        assert b"Content" in resp.data
        assert b"Models" in resp.data

    def test_settings_shows_model_names(self, client):
        resp = client.get("/settings")
        assert b"claude" in resp.data.lower()

    def test_settings_has_quick_start(self, client):
        resp = client.get("/settings")
        assert b"Quick Start Guide" in resp.data


class TestAPI:
    def test_status_endpoint(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["running"] is False

    def test_businesses_endpoint(self, client):
        resp = client.get("/api/businesses")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "name" in data[0]

    def test_business_detail_endpoint(self, client):
        resp = client.get("/api/businesses/example_appliance_repair")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "profile" in data
        assert "state" in data

    def test_business_detail_not_found(self, client):
        resp = client.get("/api/businesses/nonexistent")
        assert resp.status_code == 404

    def test_runs_endpoint(self, client):
        resp = client.get("/api/runs")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_documents_endpoint(self, client):
        resp = client.get("/api/documents")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_dashboard_endpoint(self, client):
        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_businesses" in data
        assert "pipeline_running" in data


class TestPipelineTrigger:
    def test_trigger_redirects(self, client):
        resp = client.post("/pipeline/run", data={"use_mock": "on", "dry_run": "on"})
        assert resp.status_code == 302

    def test_trigger_with_mock(self, client):
        resp = client.post("/pipeline/run", data={"use_mock": "on"}, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Pipeline started" in resp.data
