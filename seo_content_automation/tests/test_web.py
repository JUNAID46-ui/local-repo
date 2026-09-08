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


class TestAPI:
    def test_status_endpoint(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["running"] is False


class TestPipelineTrigger:
    def test_trigger_redirects(self, client):
        resp = client.post("/pipeline/run", data={"use_mock": "on", "dry_run": "on"})
        assert resp.status_code == 302

    def test_trigger_with_mock(self, client):
        resp = client.post("/pipeline/run", data={"use_mock": "on"}, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Pipeline started" in resp.data
