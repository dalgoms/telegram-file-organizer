import json
import os
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
    """원자적 쓰기: 임시파일에 쓴 뒤 rename하여 중간 크래시에도 데이터 보존."""
    tmp = HISTORY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    os.replace(tmp, HISTORY_FILE)


def execute_organization(root_path: str, classification: dict) -> dict:
    """분류 결과에 따라 파일을 실제로 이동한다.
    매 파일 이동마다 history를 저장하여 크래시 시에도 undo 가능.
    """
    root = Path(root_path)
    folders = classification.get("folders", {})
    now = datetime.now()
    session_id = now.strftime("%Y%m%d_%H%M%S")
    date_prefix = f"정리_{now.strftime('%Y-%m-%d')}"

    moved = []
    failed = []

    stamped_folders = [f"{date_prefix}/{k}" for k in folders.keys()]
    result = {
        "session_id": session_id,
        "root_path": root_path,
        "timestamp": now.isoformat(),
        "moved": moved,
        "failed": failed,
        "classification_folders": stamped_folders,
        "date_prefix": date_prefix,
    }

    history = load_history()
    history.append(result)
    if len(history) > 50:
        history = history[-50:]

    for folder_name, file_list in folders.items():
        safe_name = _sanitize_folder_name(folder_name)
        if not safe_name:
            for fname in file_list:
                failed.append({"name": fname, "error": "잘못된 폴더명"})
            continue

        target_dir = root / date_prefix / safe_name
        target_dir.mkdir(parents=True, exist_ok=True)

        for fname in file_list:
            src = root / fname
            dst = target_dir / fname

            if not src.exists():
                failed.append({"name": fname, "error": "파일을 찾을 수 없음"})
                continue

            if src.is_symlink():
                failed.append({"name": fname, "error": "심볼릭 링크는 건너뜁니다"})
                continue

            if not str(src.resolve()).startswith(str(root.resolve())):
                failed.append({"name": fname, "error": "루트 폴더 외부 파일 차단"})
                continue

            if src == dst:
                continue

            try:
                if os.path.getsize(str(src)) == 0:
                    pass  # 빈 파일도 정리 허용
            except OSError:
                failed.append({"name": fname, "error": "파일 접근 불가 (잠금?)"})
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
                save_history(history)
            except PermissionError:
                failed.append({"name": fname, "error": "파일이 사용 중 (다른 프로그램이 열고 있음)"})
            except OSError as e:
                if "too long" in str(e).lower() or len(str(dst)) > 250:
                    failed.append({"name": fname, "error": "경로가 너무 깁니다 (260자 초과)"})
                else:
                    failed.append({"name": fname, "error": str(e)})
            except Exception as e:
                failed.append({"name": fname, "error": str(e)})

    save_history(history)
    return result


def _sanitize_folder_name(name: str) -> str:
    """GPT가 반환한 폴더명에서 위험한 경로 패턴을 제거한다."""
    name = name.replace("\\", "/")
    parts = [p for p in name.split("/") if p and p != ".." and p != "."]
    if not parts:
        return ""
    return str(Path(*parts))


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

    created_dirs = set()
    classification_folders = last.get("classification_folders", [])
    root = Path(last.get("root_path", ""))
    for folder_name in classification_folders:
        created_dirs.add(root / folder_name)
        for parent in (root / folder_name).parents:
            if parent == root:
                break
            created_dirs.add(parent)

    _cleanup_created_dirs(created_dirs)

    save_history(history)
    return {"restored": restored, "failed": failed, "session_id": last["session_id"]}


def _cleanup_created_dirs(dirs: set):
    """봇이 만든 폴더 중 비어있는 것만 삭제한다. 원래 있던 폴더는 건드리지 않는다."""
    for d in sorted(dirs, key=lambda x: len(str(x)), reverse=True):
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass


def format_result(result: dict) -> str:
    """정리 결과를 텔레그램 메시지로 포맷한다."""
    if "error" in result:
        return f"[실패] {result['error']}"

    moved = result.get("moved", [])
    failed = result.get("failed", [])

    folders_used = set()
    for item in moved:
        try:
            rel = Path(item["to"]).relative_to(result.get("root_path", ""))
            folders_used.add(str(rel.parent))
        except ValueError:
            folders_used.add(Path(item["to"]).parent.name)

    date_prefix = result.get("date_prefix", "")
    lines = [
        f"깔끔하게 정리했어요!",
        "",
        f"  {date_prefix}/" if date_prefix else "",
        f"  파일 {len(moved)}개  ->  폴더 {len(folders_used)}개로 정돈",
    ]
    lines = [l for l in lines if l or l == ""]

    if moved:
        lines.append("")
        for item in moved[:15]:
            try:
                rel_to = Path(item["to"]).relative_to(result.get("root_path", ""))
                lines.append(f"  {item['name']}  ->  {rel_to.parent}/")
            except ValueError:
                lines.append(f"  {item['name']}  ->  {Path(item['to']).parent.name}/")
        if len(moved) > 15:
            lines.append(f"  ... 외 {len(moved) - 15}개")

    if failed:
        lines.append(f"\n일부 파일은 옮기지 못했어요 ({len(failed)}개):")
        for item in failed[:5]:
            lines.append(f"  {item['name']}: {item['error']}")

    lines.append("\n되돌리고 싶으면 /undo")
    lines.append("/stats 로 누적 기록을 확인해보세요!")
    return "\n".join(lines)


def format_undo_result(result: dict) -> str:
    if "error" in result:
        return f"{result['error']}"

    restored = result.get("restored", [])
    failed = result.get("failed", [])

    lines = [f"원래대로 돌려놨어요. ({len(restored)}개 파일)"]

    if failed:
        lines.append(f"\n일부 파일은 되돌리지 못했어요 ({len(failed)}개):")
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
