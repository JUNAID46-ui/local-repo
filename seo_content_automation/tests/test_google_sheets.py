import pytest
from app.integrations.google_sheets import MockSheetClient, parse_business_from_row


class TestParseBusinessFromRow:
    def test_valid_row(self):
        row = {
            "Business_ID": "test_123",
            "Business_Name": "Test Biz",
            "Website": "https://test.com",
            "Location": "City, State",
            "Services": "Service A, Service B, Service C",
            "Active": "true",
        }
        biz = parse_business_from_row(row)
        assert biz is not None
        assert biz.business_id == "test_123"
        assert biz.business_name == "Test Biz"
        assert len(biz.services) == 3

    def test_missing_id_returns_none(self):
        row = {"Business_Name": "Test"}
        assert parse_business_from_row(row) is None

    def test_missing_name_returns_none(self):
        row = {"Business_ID": "123"}
        assert parse_business_from_row(row) is None

    def test_inactive_returns_none(self):
        row = {
            "Business_ID": "123",
            "Business_Name": "Test",
            "Active": "false",
        }
        assert parse_business_from_row(row) is None

    def test_empty_active_is_active(self):
        row = {
            "Business_ID": "123",
            "Business_Name": "Test",
            "Active": "",
        }
        biz = parse_business_from_row(row)
        assert biz is not None
        assert biz.active

    def test_services_splitting(self):
        row = {
            "Business_ID": "123",
            "Business_Name": "Test",
            "Services": "A, B, C, D",
        }
        biz = parse_business_from_row(row)
        assert len(biz.services) == 4


class TestMockSheetClient:
    def test_read_empty(self):
        client = MockSheetClient()
        rows = client.read_all_rows("fake_sheet_id")
        assert rows == []

    def test_update_cell(self):
        client = MockSheetClient()
        client.update_cell("fake_id", "A1", "test")

    def test_append_row(self):
        client = MockSheetClient()
        client.append_row("fake_id", "Sheet1", ["a", "b", "c"])
