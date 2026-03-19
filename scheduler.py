"""예약 스캔 관리.
지정 시간에 자동으로 폴더를 스캔하고 미리보기를 알림으로 보낸다.
"""

import json
import os
from config import STATS_FILE

SCHEDULE_FILE = os.path.join(os.path.dirname(__file__), "schedules.json")

WEEKDAY_MAP = {
    "월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6,
    "월요일": 0, "화요일": 1, "수요일": 2, "목요일": 3,
    "금요일": 4, "토요일": 5, "일요일": 6,
    "매일": -1,
}

WEEKDAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]


def load_schedules() -> list[dict]:
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_schedules(schedules: list[dict]):
    tmp = SCHEDULE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SCHEDULE_FILE)


def add_schedule(user_id: int, path: str, day: str, hour: int, minute: int) -> str:
    day_lower = day.strip()
    if day_lower not in WEEKDAY_MAP:
        return f"'{day}'는 알 수 없는 요일이에요.\n사용 가능: 월, 화, 수, 목, 금, 토, 일, 매일"

    weekday = WEEKDAY_MAP[day_lower]
    schedules = load_schedules()

    schedules.append({
        "user_id": user_id,
        "path": path,
        "weekday": weekday,
        "hour": hour,
        "minute": minute,
    })
    save_schedules(schedules)

    day_label = "매일" if weekday == -1 else f"{WEEKDAY_NAMES[weekday]}요일"
    return (
        f"예약 등록 완료!\n"
        f"  폴더: {path}\n"
        f"  시간: {day_label} {hour:02d}:{minute:02d}\n\n"
        f"해당 시간에 자동으로 스캔 결과를 알려드려요."
    )


def remove_schedule(user_id: int, index: int) -> str:
    schedules = load_schedules()
    user_schedules = [s for s in schedules if s["user_id"] == user_id]

    if index < 1 or index > len(user_schedules):
        return f"1~{len(user_schedules)} 사이 번호를 입력해주세요."

    target = user_schedules[index - 1]
    schedules.remove(target)
    save_schedules(schedules)
    return "예약을 삭제했어요."


def format_schedules(user_id: int) -> str:
    schedules = load_schedules()
    user_schedules = [s for s in schedules if s["user_id"] == user_id]

    if not user_schedules:
        return (
            "등록된 예약이 없어요.\n\n"
            "예약 추가: /schedule 경로 요일 시:분\n"
            "예: /schedule 다운로드 금 17:00\n"
            "예: /schedule D:\\Downloads 매일 09:00"
        )

    lines = ["--- 예약 스캔 목록 ---", ""]
    for i, s in enumerate(user_schedules, 1):
        day = "매일" if s["weekday"] == -1 else f"{WEEKDAY_NAMES[s['weekday']]}요일"
        lines.append(f"  {i}. {s['path']}")
        lines.append(f"     {day} {s['hour']:02d}:{s['minute']:02d}")
    lines.append(f"\n예약 삭제: /unschedule 번호")
    return "\n".join(lines)


def get_due_schedules(weekday: int, hour: int, minute: int) -> list[dict]:
    """현재 시간에 실행해야 할 스케줄을 반환."""
    schedules = load_schedules()
    due = []
    for s in schedules:
        if s["hour"] == hour and s["minute"] == minute:
            if s["weekday"] == -1 or s["weekday"] == weekday:
                due.append(s)
    return due
