import json
from pathlib import Path
from config import RULES_FILE


def load_rules() -> list[dict]:
    """커스텀 규칙을 로드한다.

    규칙 형식:
    {
        "pattern": "*.pptx",       # glob 패턴 또는 확장자
        "folder": "문서/프레젠테이션",  # 이동할 폴더
        "description": "PPT 파일"    # 설명
    }
    """
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_rules(rules: list[dict]):
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)


def add_rule(pattern: str, folder: str, description: str = "") -> str:
    rules = load_rules()
    for r in rules:
        if r["pattern"] == pattern:
            r["folder"] = folder
            r["description"] = description
            save_rules(rules)
            return f"규칙 업데이트: {pattern} -> {folder}"

    rules.append({
        "pattern": pattern,
        "folder": folder,
        "description": description,
    })
    save_rules(rules)
    return f"규칙 추가: {pattern} -> {folder}"


def remove_rule(pattern: str) -> str:
    rules = load_rules()
    before = len(rules)
    rules = [r for r in rules if r["pattern"] != pattern]
    if len(rules) == before:
        return f"해당 패턴의 규칙을 찾을 수 없습니다: {pattern}"
    save_rules(rules)
    return f"규칙 삭제: {pattern}"


def format_rules() -> str:
    rules = load_rules()
    if not rules:
        return "등록된 규칙이 없습니다.\n\n/rule 패턴 폴더명 으로 추가\n예: /rule *.pptx 문서/프레젠테이션"

    lines = ["[커스텀 규칙 목록]", ""]
    for r in rules:
        desc = f" ({r['description']})" if r.get("description") else ""
        lines.append(f"  {r['pattern']} -> {r['folder']}{desc}")

    lines.append("\n/rule 패턴 폴더명 으로 추가")
    lines.append("/delrule 패턴 으로 삭제")
    return "\n".join(lines)


def apply_rules(files: list, classification: dict) -> dict:
    """커스텀 규칙을 분류 결과에 우선 적용한다."""
    rules = load_rules()
    if not rules:
        return classification

    folders = classification.get("folders", {})
    assigned_files = set()
    for file_list in folders.values():
        assigned_files.update(file_list)

    for rule in rules:
        pattern = rule["pattern"]
        target = rule["folder"]

        for f in files:
            if f.is_dir:
                continue
            if f.name in assigned_files and _matches(f.name, pattern):
                for folder, flist in folders.items():
                    if f.name in flist:
                        flist.remove(f.name)
                        break
                folders.setdefault(target, [])
                if f.name not in folders[target]:
                    folders[target].append(f.name)

    folders = {k: v for k, v in folders.items() if v}
    classification["folders"] = folders
    return classification


def _matches(filename: str, pattern: str) -> bool:
    return Path(filename).match(pattern)
