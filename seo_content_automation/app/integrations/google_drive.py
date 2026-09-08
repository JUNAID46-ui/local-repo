from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.config import settings, PROJECT_ROOT

logger = logging.getLogger("seo_automation")


class GoogleDriveClient:
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
            scopes=["https://www.googleapis.com/auth/drive.file"],
        )
        self._service = build("drive", "v3", credentials=creds)
        return self._service

    def upload_file(self, local_path: Path, folder_id: str, filename: str | None = None) -> str:
        from googleapiclient.http import MediaFileUpload

        service = self._get_service()
        fname = filename or local_path.name
        file_metadata = {
            "name": fname,
            "parents": [folder_id],
        }
        media = MediaFileUpload(str(local_path), resumable=True)
        uploaded = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
        ).execute()
        file_id = uploaded.get("id", "")
        logger.info(f"Uploaded {fname} to Drive: {file_id}")
        return file_id

    def create_folder(self, name: str, parent_folder_id: str) -> str:
        service = self._get_service()
        file_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_folder_id],
        }
        folder = service.files().create(
            body=file_metadata,
            fields="id",
        ).execute()
        folder_id = folder.get("id", "")
        logger.info(f"Created Drive folder '{name}': {folder_id}")
        return folder_id


class MockDriveClient:
    def upload_file(self, local_path: Path, folder_id: str, filename: str | None = None) -> str:
        fname = filename or local_path.name
        logger.info(f"[MockDrive] Upload {fname} to folder {folder_id}")
        return "mock_file_id_12345"

    def create_folder(self, name: str, parent_folder_id: str) -> str:
        logger.info(f"[MockDrive] Create folder '{name}' in {parent_folder_id}")
        return "mock_folder_id_12345"
