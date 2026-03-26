from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from google.auth.transport.requests import Request
from google.oauth2 import credentials as oauth_credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from .logger import get_logger

logger = get_logger(__name__)


SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations",
]


@dataclass
class DriveFile:
    id: str
    name: str
    mime_type: str
    modified_time: Optional[str] = None


class DriveService:
    def __init__(
        self,
        oauth_token_json: Optional[Dict[str, Any]] = None,
        oauth_client_json_path: Optional[str] = None,
        service_account_json_path: Optional[str] = None,
    ) -> None:
        self._service = build(
            "drive",
            "v3",
            credentials=self._build_credentials(
                oauth_token_json,
                oauth_client_json_path,
                service_account_json_path,
            ),
            cache_discovery=False,
        )

    def _build_credentials(
        self,
        oauth_token_json: Optional[Dict[str, Any]],
        oauth_client_json_path: Optional[str],
        service_account_json_path: Optional[str],
    ):
        if service_account_json_path:
            logger.info("Using service account credentials.")
            return service_account.Credentials.from_service_account_file(
                service_account_json_path, scopes=SCOPES
            )

        if oauth_token_json:
            logger.info("Using OAuth token JSON credentials.")
            creds = oauth_credentials.Credentials.from_authorized_user_info(
                oauth_token_json, scopes=SCOPES
            )
            if creds.expired and creds.refresh_token:
                logger.info("Refreshing expired OAuth token.")
                creds.refresh(Request())
            return creds

        if oauth_client_json_path:
            logger.warning(
                "OAuth client JSON path provided without token JSON. "
                "Interactive flow is not implemented in this agent."
            )

        raise RuntimeError(
            "No valid Google credentials found. Provide service account JSON or "
            "GOOGLE_TOKEN_JSON."
        )

    def list_files(
        self,
        folder_id: str,
        query_extra: Optional[str] = None,
        page_size: int = 100,
    ) -> List[DriveFile]:
        query = f"'{folder_id}' in parents and trashed = false"
        if query_extra:
            query = f"{query} and {query_extra}"
        results: List[DriveFile] = []
        page_token = None
        while True:
            response = (
                self._service.files()
                .list(
                    q=query,
                    pageSize=page_size,
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
                    pageToken=page_token,
                )
                .execute()
            )
            for item in response.get("files", []):
                results.append(
                    DriveFile(
                        id=item["id"],
                        name=item["name"],
                        mime_type=item.get("mimeType", ""),
                        modified_time=item.get("modifiedTime"),
                    )
                )
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return results

    def find_file_by_name(self, folder_id: str, name: str) -> Optional[DriveFile]:
        query = f"name = '{name}'"
        files = self.list_files(folder_id, query_extra=query)
        return files[0] if files else None

    def find_or_create_subfolder(self, parent_id: str, name: str) -> str:
        query = (
            "mimeType = 'application/vnd.google-apps.folder' and "
            f"name = '{name}'"
        )
        existing = self.list_files(parent_id, query_extra=query)
        if existing:
            return existing[0].id
        metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
        folder = self._service.files().create(body=metadata, fields="id").execute()
        return folder["id"]

    def move_file(self, file_id: str, new_parent_id: str) -> None:
        file = self._service.files().get(fileId=file_id, fields="parents").execute()
        previous_parents = ",".join(file.get("parents", []))
        self._service.files().update(
            fileId=file_id,
            addParents=new_parent_id,
            removeParents=previous_parents,
            fields="id, parents",
        ).execute()

    def download_file(self, file_id: str) -> bytes:
        request = self._service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()

    def upload_file(
        self,
        folder_id: str,
        filename: str,
        content: bytes,
        mime_type: str = "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ) -> str:
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False)
        metadata = {"name": filename, "parents": [folder_id]}
        created = (
            self._service.files()
            .create(body=metadata, media_body=media, fields="id")
            .execute()
        )
        return created["id"]

    def update_file_content(
        self, file_id: str, content: bytes, mime_type: str = "application/json"
    ) -> str:
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False)
        updated = (
            self._service.files()
            .update(fileId=file_id, media_body=media, fields="id")
            .execute()
        )
        return updated["id"]

    def get_start_page_token(self) -> str:
        response = self._service.changes().getStartPageToken().execute()
        return response["startPageToken"]

    def watch_changes(
        self,
        page_token: str,
        webhook_url: str,
        channel_id: str,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = {
            "id": channel_id,
            "type": "web_hook",
            "address": webhook_url,
        }
        if token:
            body["token"] = token
        return self._service.changes().watch(pageToken=page_token, body=body).execute()
