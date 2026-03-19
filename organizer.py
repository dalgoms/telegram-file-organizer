import json
import shutil
from pathlib import Path
from datetime import datetime
from config import HISTORY_FILE


def load_history() -> list[dict]:
    """정리 이력을 로드한다."""
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_history(history: list[dict]):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def execute_organization(root_path: str, classification: dict) -> dict:
    """분류 결과에 따라 파일을 실제로 이동한다.

    Returns:
        {
            "moved": [{"from": str, "to": str, "name": str}],
            "failed": [{"name": str, "error": str}],
            "session_id": str
        }
    """
    root = Path(root_path)
    folders = classification.get("folders", {})
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    moved = []
    failed = []

    for folder_name, file_list in folders.items():
        target_dir = root / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        for fname in file_list:
            src = root / fname
            dst = target_dir / fname

            if not src.exists():
                failed.append({"name": fname, "error": "파일을 찾을 수 없음"})
                continue

            if src == dst:
                continue

            if dst.exists():
                stem = dst.stem
                suffix = dst.suffix
                counter = 1
                while dst.exists():
                    dst = target_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

            try:
                shutil.move(str(src), str(dst))
                moved.append({
                    "from": str(src),
                    "to": str(dst),
                    "name": fname,
                })
            except Exception as e:
                failed.append({"name": fname, "error": str(e)})

    result = {
        "session_id": session_id,
        "root_path": root_path,
        "timestamp": datetime.now().isoformat(),
        "moved": moved,
        "failed": failed,
    }

    history = load_history()
    history.append(result)
    if len(history) > 50:
        history = history[-50:]
    save_history(history)

    return result


def undo_last() -> dict:
    """마지막 정리를 되돌린다."""
    history = load_history()
    if not history:
        return {"error": "되돌릴 이력이 없습니다."}

    last = history.pop()
    restored = []
    failed = []

    for item in reversed(last.get("moved", [])):
        src = Path(item["to"])
        dst = Path(item["from"])

        if not src.exists():
            failed.append({"name": item["name"], "error": "이동된 파일을 찾을 수 없음"})
            continue

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            restored.append(item["name"])
        except Exception as e:
            failed.append({"name": item["name"], "error": str(e)})

    _cleanup_empty_dirs(last.get("root_path", ""))

    save_history(history)
    return {"restored": restored, "failed": failed, "session_id": last["session_id"]}


def _cleanup_empty_dirs(root_path: str):
    """정리 후 빈 폴더를 삭제한다."""
    if not root_path:
        return
    root = Path(root_path)
    for d in sorted(root.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            try:
                d.rmdir()
            except OSError:
                pass


def format_result(result: dict) -> str:
    """정리 결과를 텔레그램 메시지로 포맷한다."""
    if "error" in result:
        return f"[실패] {result['error']}"

    moved = result.get("moved", [])
    failed = result.get("failed", [])

    lines = [f"[정리 완료] {len(moved)}개 파일 이동"]

    if moved:
        lines.append("")
        for item in moved[:20]:
            rel_to = Path(item["to"]).relative_to(result.get("root_path", ""))
            lines.append(f"  {item['name']} -> {rel_to.parent}/")
        if len(moved) > 20:
            lines.append(f"  ... 외 {len(moved) - 20}개")

    if failed:
        lines.append(f"\n[실패] {len(failed)}개:")
        for item in failed[:5]:
            lines.append(f"  {item['name']}: {item['error']}")

    lines.append("\n되돌리려면 /undo")
    return "\n".join(lines)


def format_undo_result(result: dict) -> str:
    if "error" in result:
        return f"[실패] {result['error']}"

    restored = result.get("restored", [])
    failed = result.get("failed", [])

    lines = [f"[되돌리기 완료] {len(restored)}개 파일 원위치"]

    if failed:
        lines.append(f"[실패] {len(failed)}개:")
        for item in failed:
            lines.append(f"  {item['name']}: {item['error']}")

    return "\n".join(lines)


def format_history() -> str:
    history = load_history()
    if not history:
        return "정리 이력이 없습니다."

    lines = ["[정리 이력]", ""]
    for h in reversed(history[-10:]):
        ts = h.get("timestamp", "")[:16].replace("T", " ")
        moved_count = len(h.get("moved", []))
        lines.append(f"  {ts} | {h.get('root_path', '')} | {moved_count}개 이동")

    return "\n".join(lines)
