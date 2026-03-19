import os
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from config import SKIP_DIRS, SKIP_FILES, MAX_FILES_PER_SCAN


@dataclass
class FileInfo:
    name: str
    path: str
    extension: str
    size_bytes: int
    modified: datetime
    is_dir: bool = False

    @property
    def size_human(self) -> str:
        size = self.size_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    @property
    def modified_str(self) -> str:
        return self.modified.strftime("%Y-%m-%d")


@dataclass
class ScanResult:
    root_path: str
    files: list[FileInfo] = field(default_factory=list)
    skipped: int = 0
    error: Optional[str] = None

    @property
    def total_size(self) -> int:
        return sum(f.size_bytes for f in self.files if not f.is_dir)

    @property
    def total_size_human(self) -> str:
        size = self.total_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"


def scan_local(path_str: str, recursive: bool = False) -> ScanResult:
    """로컬 폴더를 스캔하여 파일 목록을 반환한다."""
    path = Path(path_str).resolve()
    result = ScanResult(root_path=str(path))

    if not path.exists():
        result.error = f"경로를 찾을 수 없습니다: {path}"
        return result

    if not path.is_dir():
        result.error = f"폴더가 아닙니다: {path}"
        return result

    try:
        entries = path.rglob("*") if recursive else path.iterdir()

        for entry in entries:
            if len(result.files) >= MAX_FILES_PER_SCAN:
                result.skipped += 1
                continue

            if entry.name in SKIP_FILES:
                result.skipped += 1
                continue

            if entry.is_dir():
                if entry.name in SKIP_DIRS:
                    result.skipped += 1
                    continue
                if not recursive:
                    result.files.append(FileInfo(
                        name=entry.name,
                        path=str(entry),
                        extension="",
                        size_bytes=0,
                        modified=datetime.fromtimestamp(entry.stat().st_mtime),
                        is_dir=True,
                    ))
                continue

            try:
                stat = entry.stat()
                result.files.append(FileInfo(
                    name=entry.name,
                    path=str(entry),
                    extension=entry.suffix.lower(),
                    size_bytes=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime),
                ))
            except (PermissionError, OSError):
                result.skipped += 1

    except PermissionError:
        result.error = f"접근 권한이 없습니다: {path}"

    return result


def format_scan_summary(result: ScanResult) -> str:
    """스캔 결과를 텔레그램 메시지용 텍스트로 포맷한다."""
    if result.error:
        return f"[스캔 실패] {result.error}"

    dirs = [f for f in result.files if f.is_dir]
    files = [f for f in result.files if not f.is_dir]

    ext_counts: dict[str, int] = {}
    for f in files:
        ext = f.extension if f.extension else "(확장자 없음)"
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    lines = [
        f"[스캔 완료] {result.root_path}",
        f"  폴더 {len(dirs)}개 | 파일 {len(files)}개 | 총 {result.total_size_human}",
        "",
        "확장자별 현황:",
    ]

    for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {ext}: {count}개")

    if result.skipped > 0:
        lines.append(f"\n(건너뛴 항목: {result.skipped}개)")

    return "\n".join(lines)
