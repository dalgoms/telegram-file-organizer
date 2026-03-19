"""즐겨찾기 경로 별칭 관리.
/scan 다운로드 만으로 긴 경로를 대체한다.
"""

import json
import os
from config import PATHS_FILE, QUICK_PATHS


def load_paths() -> dict[str, str]:
    try:
        with open(PATHS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_paths(paths: dict[str, str]):
    tmp = PATHS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(paths, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PATHS_FILE)


def add_path(alias: str, full_path: str) -> str:
    paths = load_paths()
    paths[alias] = full_path
    save_paths(paths)
    return f"'{alias}' 등록 완료!\n이제 /scan {alias} 로 바로 사용할 수 있어요."


def remove_path(alias: str) -> str:
    paths = load_paths()
    if alias not in paths:
        return f"'{alias}' 별칭을 찾을 수 없어요."
    del paths[alias]
    save_paths(paths)
    return f"'{alias}' 삭제했어요."


def resolve_alias(text: str) -> str:
    """별칭이면 실제 경로로, 아니면 그대로 반환."""
    paths = load_paths()
    lower = text.lower().strip()

    if lower in paths:
        return paths[lower]

    builtin = {
        "바탕화면": "desktop", "desktop": "desktop",
        "다운로드": "downloads", "downloads": "downloads",
        "문서": "documents", "documents": "documents",
        "사진": "pictures", "pictures": "pictures",
    }
    if lower in builtin and builtin[lower] in QUICK_PATHS:
        return QUICK_PATHS[builtin[lower]]

    return text


def format_paths() -> str:
    paths = load_paths()
    builtin_labels = {"desktop": "바탕화면", "downloads": "다운로드",
                      "documents": "문서", "pictures": "사진"}

    lines = ["--- 등록된 바로가기 ---", ""]

    if QUICK_PATHS:
        lines.append("[기본 (자동 감지)]")
        for key, full in QUICK_PATHS.items():
            label = builtin_labels.get(key, key)
            lines.append(f"  {label}  ->  {full}")
        lines.append("")

    if paths:
        lines.append("[내가 등록한 별칭]")
        for alias, full in paths.items():
            lines.append(f"  {alias}  ->  {full}")
        lines.append("")
    elif not QUICK_PATHS:
        lines.append("등록된 바로가기가 없어요.")
        lines.append("")

    lines.append("별칭 추가: /path 이름 경로")
    lines.append("별칭 삭제: /delpath 이름")
    lines.append("\n예: /path 프로젝트 D:\\작업\\2026프로젝트")
    lines.append("    → /scan 프로젝트 로 바로 사용")
    return "\n".join(lines)
