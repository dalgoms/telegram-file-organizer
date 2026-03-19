"""장기 근속 직원을 위한 파일 분석 도구.

수년간 쌓인 파일의 핵심 고통을 해결한다:
- 중복 파일 탐지
- "최종_수정_진짜최종" 버전 체인 분석
- 용량 먹는 파일 TOP N
- 오래된 파일 연도별 아카이브 제안
- 키워드 기반 파일 검색
"""

import hashlib
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field

from scanner import FileInfo, ScanResult


# ---------------------------------------------------------------------------
# 1. 중복 파일 탐지
# ---------------------------------------------------------------------------

@dataclass
class DuplicateGroup:
    hash_value: str
    size_bytes: int
    files: list[FileInfo] = field(default_factory=list)

    @property
    def wasted_bytes(self) -> int:
        return self.size_bytes * (len(self.files) - 1)

    @property
    def wasted_human(self) -> str:
        size = self.wasted_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"


def find_duplicates(scan: ScanResult) -> list[DuplicateGroup]:
    """파일 크기 → 해시 2단계로 중복을 탐지한다."""
    files = [f for f in scan.files if not f.is_dir and f.size_bytes > 0]

    size_groups: dict[int, list[FileInfo]] = defaultdict(list)
    for f in files:
        size_groups[f.size_bytes].append(f)

    candidates = {sz: fl for sz, fl in size_groups.items() if len(fl) > 1}

    hash_groups: dict[str, DuplicateGroup] = {}

    for size, file_list in candidates.items():
        for f in file_list:
            try:
                h = _file_hash(f.path)
                if h not in hash_groups:
                    hash_groups[h] = DuplicateGroup(hash_value=h, size_bytes=size)
                hash_groups[h].files.append(f)
            except (PermissionError, OSError):
                continue

    return [g for g in hash_groups.values() if len(g.files) > 1]


def _file_hash(path: str, chunk_size: int = 8192) -> str:
    """파일의 MD5 해시를 계산한다. 대용량 파일은 앞뒤 8KB만 사용."""
    h = hashlib.md5()
    fpath = Path(path)
    file_size = fpath.stat().st_size

    with open(fpath, "rb") as f:
        if file_size <= chunk_size * 2:
            h.update(f.read())
        else:
            h.update(f.read(chunk_size))
            f.seek(-chunk_size, 2)
            h.update(f.read(chunk_size))

    h.update(str(file_size).encode())
    return h.hexdigest()


def format_duplicates(groups: list[DuplicateGroup]) -> str:
    if not groups:
        return "[중복 파일 없음] 깔끔합니다!"

    total_wasted = sum(g.wasted_bytes for g in groups)
    total_human = _size_human(total_wasted)

    lines = [
        f"[중복 파일 발견] {len(groups)}그룹, 낭비 용량 {total_human}",
        "",
    ]

    for i, g in enumerate(sorted(groups, key=lambda x: -x.wasted_bytes)[:10], 1):
        lines.append(f"{i}. ({g.files[0].size_human}) x{len(g.files)}개 = 낭비 {g.wasted_human}")
        for f in g.files:
            lines.append(f"   {f.name}")
            lines.append(f"   @ {Path(f.path).parent}")
        lines.append("")

    if len(groups) > 10:
        lines.append(f"... 외 {len(groups) - 10}그룹")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. 버전 체인 분석 ("최종_수정_진짜최종" 문제)
# ---------------------------------------------------------------------------

VERSION_PATTERNS = [
    r"[_\-\s]?v(\d+)",
    r"[_\-\s]?(최종)",
    r"[_\-\s]?(수정)",
    r"[_\-\s]?(진짜최종|진짜_?최종)",
    r"[_\-\s]?(최최종)",
    r"[_\-\s]?(final)",
    r"[_\-\s]?(revised|rev)",
    r"[_\-\s]?(draft|초안)",
    r"[_\-\s]?(\d{8})",           # 20260318 형태 날짜
    r"[_\-\s]?\((\d+)\)",         # (1), (2) 형태
    r"[_\-\s]?copy\s*(\d*)",      # copy, copy 2
]

VERSION_COMPILED = [re.compile(p, re.IGNORECASE) for p in VERSION_PATTERNS]


@dataclass
class VersionChain:
    base_name: str
    extension: str
    versions: list[FileInfo] = field(default_factory=list)


def find_version_chains(scan: ScanResult) -> list[VersionChain]:
    """버전 관련 키워드가 포함된 파일을 그룹핑한다."""
    files = [f for f in scan.files if not f.is_dir]

    base_groups: dict[str, list[FileInfo]] = defaultdict(list)

    for f in files:
        base = _extract_base_name(f.name)
        key = f"{base}{f.extension}".lower()
        base_groups[key].append(f)

    chains = []
    for key, file_list in base_groups.items():
        if len(file_list) > 1:
            stem = Path(key).stem
            ext = Path(key).suffix
            chain = VersionChain(base_name=stem, extension=ext, versions=file_list)
            chain.versions.sort(key=lambda x: x.modified)
            chains.append(chain)

    return chains


def _extract_base_name(filename: str) -> str:
    """버전 표시를 제거하고 기본 파일명을 추출한다."""
    stem = Path(filename).stem
    for pattern in VERSION_COMPILED:
        stem = pattern.sub("", stem)
    stem = re.sub(r"[_\-\s]+$", "", stem)
    stem = re.sub(r"^\s+", "", stem)
    return stem if stem else Path(filename).stem


def format_version_chains(chains: list[VersionChain]) -> str:
    if not chains:
        return "[버전 체인 없음] 파일명이 깔끔합니다!"

    lines = [
        f"[버전 체인 발견] {len(chains)}그룹",
        "같은 파일의 여러 버전이 발견되었습니다.",
        "",
    ]

    for i, chain in enumerate(sorted(chains, key=lambda c: -len(c.versions))[:10], 1):
        lines.append(f"{i}. \"{chain.base_name}{chain.extension}\" ({len(chain.versions)}개 버전)")
        for v in chain.versions:
            age = (datetime.now() - v.modified).days
            age_str = f"{age}일 전" if age > 0 else "오늘"
            lines.append(f"   {v.name} ({v.size_human}, {age_str})")
        lines.append("")

    if len(chains) > 10:
        lines.append(f"... 외 {len(chains) - 10}그룹")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3. 용량 분석
# ---------------------------------------------------------------------------

def analyze_size(scan: ScanResult, top_n: int = 15) -> str:
    """용량 TOP N 파일과 확장자별 용량을 분석한다."""
    files = [f for f in scan.files if not f.is_dir]
    if not files:
        return "[용량 분석] 파일이 없습니다."

    total = sum(f.size_bytes for f in files)

    files_sorted = sorted(files, key=lambda f: -f.size_bytes)

    ext_size: dict[str, int] = defaultdict(int)
    ext_count: dict[str, int] = defaultdict(int)
    for f in files:
        ext = f.extension if f.extension else "(없음)"
        ext_size[ext] += f.size_bytes
        ext_count[ext] += 1

    lines = [
        f"[용량 분석] 총 {_size_human(total)}, {len(files)}개 파일",
        "",
        "-- 용량 TOP 파일 --",
    ]

    for i, f in enumerate(files_sorted[:top_n], 1):
        pct = (f.size_bytes / total * 100) if total else 0
        lines.append(f"{i:2d}. {f.name}")
        lines.append(f"    {f.size_human} ({pct:.1f}%) | {f.modified_str}")

    lines.append("")
    lines.append("-- 확장자별 용량 --")

    for ext, size in sorted(ext_size.items(), key=lambda x: -x[1])[:10]:
        pct = (size / total * 100) if total else 0
        cnt = ext_count[ext]
        lines.append(f"  {ext}: {_size_human(size)} ({pct:.1f}%) | {cnt}개")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. 연도별 아카이브 제안
# ---------------------------------------------------------------------------

def suggest_archive(scan: ScanResult) -> dict[str, list[FileInfo]]:
    """올해가 아닌 파일을 연도별로 분류한다."""
    current_year = datetime.now().year
    files = [f for f in scan.files if not f.is_dir]

    yearly: dict[str, list[FileInfo]] = defaultdict(list)
    for f in files:
        year = f.modified.year
        if year < current_year:
            yearly[str(year)].append(f)

    return dict(sorted(yearly.items()))


def format_archive_suggestion(yearly: dict[str, list[FileInfo]]) -> str:
    if not yearly:
        return "[아카이브 제안] 모든 파일이 올해 파일입니다. 정리 불필요!"

    total = sum(len(fl) for fl in yearly.values())
    total_size = sum(f.size_bytes for fl in yearly.values() for f in fl)

    lines = [
        f"[아카이브 제안] {total}개 파일을 연도별로 정리할 수 있습니다.",
        f"총 {_size_human(total_size)}",
        "",
    ]

    for year, file_list in yearly.items():
        size = sum(f.size_bytes for f in file_list)
        lines.append(f"  {year}년: {len(file_list)}개 ({_size_human(size)})")
        for f in file_list[:3]:
            lines.append(f"    {f.name}")
        if len(file_list) > 3:
            lines.append(f"    ... 외 {len(file_list) - 3}개")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5. 키워드 검색
# ---------------------------------------------------------------------------

def search_files(scan: ScanResult, keyword: str) -> list[FileInfo]:
    """파일명에 키워드가 포함된 파일을 검색한다."""
    keyword_lower = keyword.lower()
    return [
        f for f in scan.files
        if not f.is_dir and keyword_lower in f.name.lower()
    ]


def format_search_results(files: list[FileInfo], keyword: str) -> str:
    if not files:
        return f"[검색 결과] \"{keyword}\" — 일치하는 파일이 없습니다."

    lines = [f"[검색 결과] \"{keyword}\" — {len(files)}개 발견", ""]

    for i, f in enumerate(files[:20], 1):
        lines.append(f"{i}. {f.name} ({f.size_human}, {f.modified_str})")
        lines.append(f"   @ {Path(f.path).parent}")

    if len(files) > 20:
        lines.append(f"\n... 외 {len(files) - 20}개")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _size_human(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"
