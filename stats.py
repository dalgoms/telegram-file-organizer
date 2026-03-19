"""정리 통계 + 업적 시스템.
정리할수록 레벨업하고 칭호가 바뀐다.
"""

import json
import os
from datetime import datetime, date
from config import STATS_FILE


def _load() -> dict:
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "total_moved": 0,
            "total_sessions": 0,
            "total_undo": 0,
            "total_duplicates_found": 0,
            "streak_days": [],
            "achievements": [],
            "first_use": None,
        }


def _save(data: dict):
    tmp = STATS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATS_FILE)


TITLES = [
    (0,    "정리 새내기"),
    (10,   "정리 입문자"),
    (50,   "정리 습관러"),
    (100,  "폴더 관리사"),
    (300,  "정리 장인"),
    (500,  "파일 마스터"),
    (1000, "전설의 정리왕"),
]

ACHIEVEMENTS = {
    "first_clean":      ("첫 정리 완료", "첫 번째 파일 정리를 완료했어요!"),
    "clean_10":         ("정리 10회", "10번이나 정리했어요! 습관이 되고 있네요."),
    "clean_50":         ("정리 50회", "50회 달성! 이제 프로 정리러에요."),
    "files_100":        ("100개 파일 정리", "파일 100개를 정리했어요!"),
    "files_500":        ("500개 파일 정리", "500개 파일 정돈! 놀라워요."),
    "files_1000":       ("1000개 파일 정리", "1000개 돌파! 전설이에요."),
    "streak_3":         ("3일 연속 정리", "3일 연속으로 정리했어요!"),
    "streak_7":         ("7일 연속 정리", "1주일 연속 정리! 대단해요."),
    "streak_30":        ("30일 연속 정리", "한 달 연속?! 정리의 신이에요."),
    "undo_first":       ("첫 되돌리기", "실수해도 괜찮아요. 되돌리기 사용!"),
    "night_owl":        ("야행성 정리러", "밤 11시 이후에 정리했어요."),
    "early_bird":       ("얼리버드 정리러", "아침 7시 전에 정리했어요!"),
    "monday_warrior":   ("월요전사", "월요일에도 정리하다니! 존경해요."),
    "friday_cleanup":   ("금요 대청소", "금요일에 정리, 깔끔한 주말 시작!"),
}


def record_organize(moved_count: int) -> list[str]:
    """정리 실행 후 통계 기록. 새 업적 리스트 반환."""
    data = _load()
    now = datetime.now()
    new_achievements = []

    if not data["first_use"]:
        data["first_use"] = now.isoformat()

    data["total_moved"] += moved_count
    data["total_sessions"] += 1

    today_str = date.today().isoformat()
    if today_str not in data["streak_days"]:
        data["streak_days"].append(today_str)
    data["streak_days"] = sorted(data["streak_days"])[-60:]

    earned = set(data["achievements"])

    if "first_clean" not in earned:
        new_achievements.append("first_clean")

    session_milestones = {"clean_10": 10, "clean_50": 50}
    for key, threshold in session_milestones.items():
        if key not in earned and data["total_sessions"] >= threshold:
            new_achievements.append(key)

    file_milestones = {"files_100": 100, "files_500": 500, "files_1000": 1000}
    for key, threshold in file_milestones.items():
        if key not in earned and data["total_moved"] >= threshold:
            new_achievements.append(key)

    streak = _calc_streak(data["streak_days"])
    streak_milestones = {"streak_3": 3, "streak_7": 7, "streak_30": 30}
    for key, threshold in streak_milestones.items():
        if key not in earned and streak >= threshold:
            new_achievements.append(key)

    hour = now.hour
    if "night_owl" not in earned and hour >= 23:
        new_achievements.append("night_owl")
    if "early_bird" not in earned and hour < 7:
        new_achievements.append("early_bird")

    weekday = now.weekday()
    if "monday_warrior" not in earned and weekday == 0:
        new_achievements.append("monday_warrior")
    if "friday_cleanup" not in earned and weekday == 4:
        new_achievements.append("friday_cleanup")

    data["achievements"].extend(new_achievements)
    _save(data)
    return new_achievements


def record_undo() -> list[str]:
    data = _load()
    data["total_undo"] += 1
    new = []
    if "undo_first" not in data["achievements"]:
        new.append("undo_first")
        data["achievements"].append("undo_first")
    _save(data)
    return new


def record_duplicates(count: int):
    data = _load()
    data["total_duplicates_found"] += count
    _save(data)


def _calc_streak(days: list[str]) -> int:
    if not days:
        return 0
    today = date.today()
    streak = 0
    for i in range(60):
        check = (today - __import__("datetime").timedelta(days=i)).isoformat()
        if check in days:
            streak += 1
        else:
            break
    return streak


def get_title(total_moved: int) -> str:
    title = TITLES[0][1]
    for threshold, t in TITLES:
        if total_moved >= threshold:
            title = t
    return title


def format_achievement(key: str) -> str:
    name, desc = ACHIEVEMENTS.get(key, ("???", "???"))
    return f"--- 업적 달성! ---\n{name}\n{desc}"


def format_stats() -> str:
    data = _load()
    total = data["total_moved"]
    sessions = data["total_sessions"]
    undos = data["total_undo"]
    title = get_title(total)
    streak = _calc_streak(data["streak_days"])

    next_title = "최고 등급!"
    for threshold, t in TITLES:
        if total < threshold:
            next_title = f"{t} ({threshold - total}개 파일 더)"
            break

    lines = [
        f"--- 나의 정리 기록 ---",
        "",
        f"  칭호: {title}",
        f"  정리한 파일: {total}개",
        f"  정리 횟수: {sessions}회",
        f"  되돌리기: {undos}회",
        f"  연속 정리: {streak}일",
        "",
        f"  다음 칭호: {next_title}",
        "",
    ]

    earned = data["achievements"]
    if earned:
        lines.append(f"--- 달성한 업적 ({len(earned)}개) ---")
        for key in earned:
            name, _ = ACHIEVEMENTS.get(key, ("???", ""))
            lines.append(f"  {name}")
    else:
        lines.append("아직 업적이 없어요. 첫 정리를 시작해보세요!")

    not_earned = [k for k in ACHIEVEMENTS if k not in earned]
    if not_earned:
        lines.append(f"\n--- 미달성 업적 ({len(not_earned)}개) ---")
        for key in not_earned[:5]:
            name, desc = ACHIEVEMENTS[key]
            lines.append(f"  {name} — {desc}")
        if len(not_earned) > 5:
            lines.append(f"  ... 외 {len(not_earned) - 5}개")

    return "\n".join(lines)
