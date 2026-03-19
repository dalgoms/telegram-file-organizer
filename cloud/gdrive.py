import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from scanner import FileInfo, ScanResult

SCOPES = ["https://www.googleapis.com/auth/drive"]
CREDENTIALS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json")
TOKEN_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "token.json")

_service = None


def _get_service():
    global _service
    if _service:
        return _service

    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        return None

    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                return None
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    _service = build("drive", "v3", credentials=creds)
    return _service


def is_available() -> bool:
    return os.path.exists(CREDENTIALS_PATH) or os.path.exists(TOKEN_PATH)


def scan_drive_folder(folder_id: str) -> ScanResult:
    """구글 드라이브 폴더를 스캔한다."""
    service = _get_service()
    result = ScanResult(root_path=f"gdrive://{folder_id}")

    if not service:
        result.error = "Google Drive가 연결되지 않았습니다. credentials.json을 설정해주세요."
        return result

    try:
        query = f"'{folder_id}' in parents and trashed = false"
        response = service.files().list(
            q=query,
            fields="files(id, name, mimeType, size, modifiedTime)",
            pageSize=500,
        ).execute()

        for item in response.get("files", []):
            is_folder = item["mimeType"] == "application/vnd.google-apps.folder"
            ext = Path(item["name"]).suffix.lower() if not is_folder else ""
            modified = datetime.fromisoformat(item["modifiedTime"].replace("Z", "+00:00"))

            result.files.append(FileInfo(
                name=item["name"],
                path=item["id"],
                extension=ext,
                size_bytes=int(item.get("size", 0)),
                modified=modified,
                is_dir=is_folder,
            ))

    except Exception as e:
        result.error = f"드라이브 스캔 실패: {str(e)}"

    return result


def move_drive_file(file_id: str, target_folder_id: str) -> bool:
    """드라이브 파일을 다른 폴더로 이동한다."""
    service = _get_service()
    if not service:
        return False

    try:
        file = service.files().get(fileId=file_id, fields="parents").execute()
        prev_parents = ",".join(file.get("parents", []))
        service.files().update(
            fileId=file_id,
            addParents=target_folder_id,
            removeParents=prev_parents,
            fields="id, parents",
        ).execute()
        return True
    except Exception:
        return False


def create_drive_folder(parent_id: str, name: str) -> Optional[str]:
    """드라이브에 폴더를 생성하고 ID를 반환한다."""
    service = _get_service()
    if not service:
        return None

    try:
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = service.files().create(body=metadata, fields="id").execute()
        return folder.get("id")
    except Exception:
        return None


def execute_drive_organization(folder_id: str, classification: dict) -> dict:
    """분류 결과에 따라 드라이브 파일을 이동한다."""
    service = _get_service()
    if not service:
        return {"error": "Google Drive 미연결"}

    scan = scan_drive_folder(folder_id)
    name_to_id = {f.name: f.path for f in scan.files}

    moved = []
    failed = []
    folder_cache: dict[str, str] = {}

    folders = classification.get("folders", {})

    for folder_name, file_list in folders.items():
        parts = folder_name.split("/")
        current_parent = folder_id

        for part in parts:
            cache_key = f"{current_parent}/{part}"
            if cache_key in folder_cache:
                current_parent = folder_cache[cache_key]
            else:
                new_id = create_drive_folder(current_parent, part)
                if new_id:
                    folder_cache[cache_key] = new_id
                    current_parent = new_id
                else:
                    break

        for fname in file_list:
            fid = name_to_id.get(fname)
            if not fid:
                failed.append({"name": fname, "error": "파일을 찾을 수 없음"})
                continue

            if move_drive_file(fid, current_parent):
                moved.append({"name": fname, "to_folder": folder_name})
            else:
                failed.append({"name": fname, "error": "이동 실패"})

    return {"moved": moved, "failed": failed}
