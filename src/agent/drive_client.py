from __future__ import annotations

import io
import json
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

import httplib2
from google.auth.transport.requests import Request
from google_auth_httplib2 import AuthorizedHttp
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
        request_timeout_seconds: int = 300,
        max_attempts: int = 6,
        execute_retries: int = 5,
    ) -> None:
        self._request_timeout_seconds = request_timeout_seconds
        self._max_attempts = max_attempts
        self._execute_retries = execute_retries
        credentials = self._build_credentials(
            oauth_token_json,
            oauth_client_json_path,
            service_account_json_path,
        )
        authed_http = AuthorizedHttp(
            credentials,
            http=httplib2.Http(timeout=self._request_timeout_seconds),
        )
        self._service = build(
            "drive",
            "v3",
            http=authed_http,
            cache_discovery=False,
        )
        self._slides_service = build(
            "slides",
            "v1",
            http=authed_http,
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
                self._refresh_with_retries(creds)
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

    def _refresh_with_retries(self, creds) -> None:
        base_request = Request()

        def timeout_request(url, method="GET", body=None, headers=None, timeout=None, **kwargs):
            return base_request(
                url=url,
                method=method,
                body=body,
                headers=headers,
                timeout=self._request_timeout_seconds,
                **kwargs,
            )

        last_exc = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                creds.refresh(timeout_request)
                return
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if not self._is_transient_error(exc) or attempt == self._max_attempts:
                    break
                delay = self._compute_backoff_delay(attempt)
                logger.warning(
                    "Token refresh failed (%s/%s). Retrying in %.1fs: %s",
                    attempt,
                    self._max_attempts,
                    delay,
                    exc,
                )
                time.sleep(delay)
        if last_exc:
            raise last_exc

    def _execute(self, request_builder, op_name: str):
        return self._with_retries(
            lambda: request_builder.execute(num_retries=self._execute_retries),
            op_name=op_name,
        )

    def _with_retries(self, fn: Callable[[], Any], op_name: str) -> Any:
        last_exc = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if not self._is_transient_error(exc) or attempt == self._max_attempts:
                    break
                delay = self._compute_backoff_delay(attempt)
                logger.warning(
                    "%s failed (%s/%s). Retrying in %.1fs: %s",
                    op_name,
                    attempt,
                    self._max_attempts,
                    delay,
                    exc,
                )
                time.sleep(delay)
        if last_exc:
            raise last_exc
        raise RuntimeError(f"{op_name} failed without a captured exception.")

    @staticmethod
    def _compute_backoff_delay(attempt: int) -> float:
        base = min(60.0, float(2 ** attempt))
        jitter = random.uniform(0.0, 0.75)
        return base + jitter

    @staticmethod
    def _is_transient_error(exc: Exception) -> bool:
        text = str(exc).lower()
        transient_tokens = [
            "timeout",
            "timed out",
            "connection reset",
            "temporarily unavailable",
            "ssl",
            "winerror 10054",
            "winerror 10060",
            "too many requests",
            "429",
            "500",
            "502",
            "503",
            "504",
        ]
        return any(token in text for token in transient_tokens)

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
            )
            response = self._execute(response, "Drive list_files")
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
        folder = self._execute(
            self._service.files().create(body=metadata, fields="id"),
            "Drive create folder",
        )
        return folder["id"]

    def move_file(self, file_id: str, new_parent_id: str) -> None:
        file = self._execute(
            self._service.files().get(fileId=file_id, fields="parents"),
            "Drive get file parents",
        )
        previous_parents = ",".join(file.get("parents", []))
        self._execute(
            self._service.files().update(
                fileId=file_id,
                addParents=new_parent_id,
                removeParents=previous_parents,
                fields="id, parents",
            ),
            "Drive move file",
        )

    def download_file(self, file_id: str) -> bytes:
        request = self._service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = self._with_retries(
                lambda: downloader.next_chunk(),
                op_name="Drive download chunk",
            )
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
        )
        created = self._execute(created, "Drive upload file")
        return created["id"]

    def update_file_content(
        self, file_id: str, content: bytes, mime_type: str = "application/json"
    ) -> str:
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False)
        updated = (
            self._service.files()
            .update(fileId=file_id, media_body=media, fields="id")
        )
        updated = self._execute(updated, "Drive update file")
        return updated["id"]

    def get_start_page_token(self) -> str:
        response = self._execute(
            self._service.changes().getStartPageToken(),
            "Drive get start page token",
        )
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
        return self._execute(
            self._service.changes().watch(pageToken=page_token, body=body),
            "Drive watch changes",
        )

    def list_changes(self, page_token: str) -> Dict[str, Any]:
        return self._execute(
            self._service.changes().list(
                pageToken=page_token,
                fields="newStartPageToken, changes(fileId, file(name, mimeType, parents), time)",
            ),
            "Drive list changes",
        )

    def create_presentation(self, title: str) -> Dict[str, Any]:
        created = self._execute(
            self._slides_service.presentations().create(body={"title": title}),
            "Slides create presentation",
        )
        return {
            "id": created["presentationId"],
            "title": created.get("title", title),
            "url": f"https://docs.google.com/presentation/d/{created['presentationId']}/edit",
        }

    def slides_batch_update(self, presentation_id: str, requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._execute(
            self._slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={"requests": requests},
            ),
            "Slides batch update",
        )

    def get_presentation(self, presentation_id: str) -> Dict[str, Any]:
        return self._execute(
            self._slides_service.presentations().get(presentationId=presentation_id),
            "Slides get presentation",
        )
