from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Protocol

from app.config import settings, PROJECT_ROOT
from app.models.business import BusinessProfile

logger = logging.getLogger("seo_automation")

EXPECTED_COLUMNS = [
    "Business_ID", "Business_Name", "Website", "Location", "Country",
    "Industry", "Services", "Primary_Service", "Target_Audience",
    "Business_Description", "Business_Facts", "Brand_Voice",
    "Primary_Keywords", "Commercial_Keywords", "Service_Areas",
    "Existing_Content_URL", "Internal_Link_Base", "Content_Status",
    "Last_Run", "Generated_Topics", "Output_Folder", "Active",
]


class SheetClient(Protocol):
    def read_all_rows(self, sheet_id: str, range_name: str) -> list[dict[str, str]]: ...
    def update_cell(self, sheet_id: str, range_name: str, value: str) -> None: ...
    def append_row(self, sheet_id: str, range_name: str, values: list[str]) -> None: ...


class GoogleSheetsClient:
    def __init__(self) -> None:
        self._service = None

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service

        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        sa_file = PROJECT_ROOT / settings.google.service_account_file
        creds = service_account.Credentials.from_service_account_file(
            str(sa_file),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        self._service = build("sheets", "v4", credentials=creds)
        return self._service

    def read_all_rows(self, sheet_id: str, range_name: str = "Businesses!A:V") -> list[dict[str, str]]:
        service = self._get_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name,
        ).execute()
        rows = result.get("values", [])
        if len(rows) < 2:
            return []
        headers = rows[0]
        data = []
        for row in rows[1:]:
            padded = row + [""] * (len(headers) - len(row))
            data.append(dict(zip(headers, padded)))
        return data

    def update_cell(self, sheet_id: str, range_name: str, value: str) -> None:
        service = self._get_service()
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=range_name,
            valueInputOption="RAW",
            body={"values": [[value]]},
        ).execute()

    def append_row(self, sheet_id: str, range_name: str, values: list[str]) -> None:
        service = self._get_service()
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=range_name,
            valueInputOption="RAW",
            body={"values": [values]},
        ).execute()


class MockSheetClient:
    def __init__(self, data_path: Path | None = None) -> None:
        self._data: list[dict[str, str]] = []
        if data_path and data_path.exists():
            with open(data_path) as f:
                self._data = json.load(f)

    def read_all_rows(self, sheet_id: str, range_name: str = "") -> list[dict[str, str]]:
        return self._data

    def update_cell(self, sheet_id: str, range_name: str, value: str) -> None:
        logger.info(f"[MockSheet] Update {range_name} = {value}")

    def append_row(self, sheet_id: str, range_name: str, values: list[str]) -> None:
        logger.info(f"[MockSheet] Append to {range_name}: {values}")


def parse_business_from_row(row: dict[str, str]) -> BusinessProfile | None:
    if not row.get("Business_ID") or not row.get("Business_Name"):
        return None
    active = row.get("Active", "true").lower() in ("true", "yes", "1", "")
    if not active:
        return None

    def split_field(val: str) -> list[str]:
        if not val:
            return []
        return [v.strip() for v in val.split(",") if v.strip()]

    return BusinessProfile(
        business_id=row["Business_ID"],
        business_name=row["Business_Name"],
        website=row.get("Website", ""),
        location=row.get("Location", ""),
        country=row.get("Country", ""),
        industry=row.get("Industry", ""),
        services=split_field(row.get("Services", "")),
        primary_service=row.get("Primary_Service", ""),
        target_audience=row.get("Target_Audience", ""),
        business_description=row.get("Business_Description", ""),
        business_facts=split_field(row.get("Business_Facts", "")),
        brand_voice=row.get("Brand_Voice", "professional, helpful, knowledgeable"),
        primary_keywords=split_field(row.get("Primary_Keywords", "")),
        commercial_keywords=split_field(row.get("Commercial_Keywords", "")),
        service_areas=split_field(row.get("Service_Areas", "")),
        existing_content_urls=split_field(row.get("Existing_Content_URL", "")),
        internal_link_base=row.get("Internal_Link_Base", ""),
        output_folder=row.get("Output_Folder", ""),
        active=active,
    )


def load_active_businesses(client: SheetClient | None = None) -> list[BusinessProfile]:
    if client is None:
        client = GoogleSheetsClient()
    rows = client.read_all_rows(settings.google.sheet_id)
    businesses = []
    for row in rows:
        biz = parse_business_from_row(row)
        if biz:
            businesses.append(biz)
    return businesses
