import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters,
)
from config import TELEGRAM_BOT_TOKEN, DEVICE_NAME
from scanner import scan_local, format_scan_summary
from classifier import classify_files, format_classification
from organizer import (
    execute_organization, undo_last, format_result,
    format_undo_result, format_history,
)
from rules import add_rule, remove_rule, format_rules, apply_rules
from cloud.gdrive import (
    is_available as gdrive_available, scan_drive_folder,
    execute_drive_organization,
)
from analyzer import (
    find_duplicates, format_duplicates,
    find_version_chains, format_version_chains,
    analyze_size,
    suggest_archive, format_archive_suggestion,
    search_files, format_search_results,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

MAX_MSG_LEN = 4000  # 텔레그램 제한 4096, 여유분 확보


async def safe_reply(message, text: str):
    """텔레그램 4096자 제한을 초과하면 자동으로 분할 전송한다."""
    if len(text) <= MAX_MSG_LEN:
        await message.reply_text(text)
        return
    lines = text.split("\n")
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > MAX_MSG_LEN:
            if chunk:
                await message.reply_text(chunk)
            chunk = line
        else:
            chunk = f"{chunk}\n{line}" if chunk else line
    if chunk:
        await message.reply_text(chunk)

PENDING_SCANS: dict[int, dict] = {}
LAST_SCANS: dict[int, "ScanResult"] = {}

TAG = f"[{DEVICE_NAME}]"  # 모든 응답 앞에 기기 표시


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"{TAG} File Organizer Bot\n"
        "텔레그램에서 폴더 경로를 보내면 AI가 정리해드립니다.\n\n"
        "[기본]\n"
        "/scan 경로 — 폴더 스캔 + AI 분류\n"
        "/run — 분류안대로 정리 실행\n"
        "/undo — 되돌리기\n\n"
        "[분석 (장기 근속자 필수)]\n"
        "/dup 경로 — 중복 파일 찾기\n"
        "/ver 경로 — 최종_수정_진짜최종 탐지\n"
        "/size 경로 — 용량 먹는 파일 분석\n"
        "/old 경로 — 연도별 아카이브 제안\n"
        "/find 키워드 — 파일 검색\n"
        "/report 경로 — 종합 리포트\n\n"
        "[기타]\n"
        "/rule — 커스텀 규칙\n"
        "/history — 정리 이력\n"
        "/gdrive — 구글 드라이브\n\n"
        f"현재 연결된 기기: {DEVICE_NAME}\n\n"
        "[자주 쓰는 경로]\n"
        "/scan C:\\Users\\Windows11 Pro\\Desktop — 바탕화면\n"
        "/scan C:\\Users\\Windows11 Pro\\Downloads — 다운로드\n"
        "/scan C:\\Users\\Windows11 Pro\\Documents — 문서\n"
        "/scan C:\\Users\\Windows11 Pro\\Pictures — 사진\n"
        "/report 경로 — 한번에 종합 진단"
    )
    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "[명령어 가이드]\n\n"
        "--- 정리 ---\n"
        "/scan 경로 — AI 분류 미리보기\n"
        "/scan 경로 -r — 하위 폴더 포함\n"
        "/run — 분류안 실행\n"
        "/undo — 되돌리기\n"
        "/history — 정리 이력\n\n"
        "--- 분석 ---\n"
        "/dup 경로 — 중복 파일 탐지\n"
        "  같은 파일이 여러 곳에 있는지 찾습니다\n"
        "/ver 경로 — 버전 체인 분석\n"
        "  보고서_최종, 보고서_수정, 보고서_v2 등 탐지\n"
        "/size 경로 — 용량 분석\n"
        "  용량 TOP 파일 + 확장자별 통계\n"
        "/old 경로 — 아카이브 제안\n"
        "  올해가 아닌 파일을 연도별로 정리 제안\n"
        "/find 키워드 — 파일 검색\n"
        "  마지막 스캔 결과에서 파일명 검색\n\n"
        "--- 설정 ---\n"
        "/rule — 커스텀 규칙 목록\n"
        "/rule 패턴 폴더 — 규칙 추가\n"
        "/delrule 패턴 — 규칙 삭제\n"
        "/gdrive 폴더ID — 드라이브 정리\n\n"
        "폴더 경로만 보내도 /scan 으로 동작합니다.\n\n"
        "[자주 쓰는 경로]\n"
        "/scan C:\\Users\\Windows11 Pro\\Desktop — 바탕화면\n"
        "/scan C:\\Users\\Windows11 Pro\\Downloads — 다운로드\n"
        "/scan C:\\Users\\Windows11 Pro\\Documents — 문서\n"
        "/scan C:\\Users\\Windows11 Pro\\Pictures — 사진\n"
        "/report 경로 — 한번에 종합 진단"
    )
    await update.message.reply_text(text)


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("경로를 입력해주세요.\n예: /scan D:\\Downloads")
        return

    recursive = False
    raw_args = list(context.args)
    if raw_args and raw_args[-1] == "-r":
        recursive = True
        raw_args.pop()
    args = " ".join(raw_args)

    await update.message.reply_text(f"{TAG} 스캔 중... {args}")

    scan_result = scan_local(args, recursive=recursive)
    summary = format_scan_summary(scan_result)
    await safe_reply(update.message, summary)

    if scan_result.error or not scan_result.files:
        return

    await update.message.reply_text("AI 분류 분석 중...")

    files = scan_result.files
    classification = classify_files(files)

    if not classification or "error" in (classification or {}):
        await update.message.reply_text(
            format_classification(classification, scan_result.root_path)
        )
        return

    classification = apply_rules(files, classification)

    preview = format_classification(classification, scan_result.root_path)
    await safe_reply(update.message, preview)

    user_id = update.effective_user.id
    LAST_SCANS[user_id] = scan_result
    PENDING_SCANS[user_id] = {
        "root_path": scan_result.root_path,
        "classification": classification,
        "type": "local",
    }

    keyboard = [
        [
            InlineKeyboardButton("정리 실행", callback_data="run_organize"),
            InlineKeyboardButton("취소", callback_data="cancel_organize"),
        ]
    ]
    await update.message.reply_text(
        "위 분류대로 정리할까요?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------------------------------------------------------------------------
# 분석 명령어 (장기 근속자를 위한 핵심 기능)
# ---------------------------------------------------------------------------

async def _scan_for_analysis(update, context, recursive=False):
    """분석 명령어 공통: 경로로 스캔하거나 마지막 스캔 재사용."""
    user_id = update.effective_user.id

    if context.args:
        path = " ".join(context.args)
        await update.message.reply_text(f"{TAG} 스캔 중... {path}")
        scan_result = scan_local(path, recursive=recursive)
        if scan_result.error:
            await update.message.reply_text(f"{TAG} [스캔 실패] {scan_result.error}")
            return None
        LAST_SCANS[user_id] = scan_result
        return scan_result

    if user_id in LAST_SCANS:
        return LAST_SCANS[user_id]

    await update.message.reply_text(f"{TAG} 경로를 입력하거나 먼저 /scan 을 실행해주세요.")
    return None


async def dup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scan = await _scan_for_analysis(update, context)
    if not scan:
        return
    await update.message.reply_text(f"{TAG} 중복 파일 분석 중...")
    groups = find_duplicates(scan)
    await safe_reply(update.message, f"{TAG}\n{format_duplicates(groups)}")


async def ver_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scan = await _scan_for_analysis(update, context)
    if not scan:
        return
    chains = find_version_chains(scan)
    await safe_reply(update.message, f"{TAG}\n{format_version_chains(chains)}")


async def size_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scan = await _scan_for_analysis(update, context)
    if not scan:
        return
    await safe_reply(update.message, f"{TAG}\n{analyze_size(scan)}")


async def old_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scan = await _scan_for_analysis(update, context)
    if not scan:
        return
    yearly = suggest_archive(scan)
    await safe_reply(update.message, f"{TAG}\n{format_archive_suggestion(yearly)}")


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("검색어를 입력하세요.\n예: /find 보고서")
        return

    user_id = update.effective_user.id
    keyword = " ".join(context.args)

    if user_id not in LAST_SCANS:
        await update.message.reply_text(f"{TAG} 먼저 /scan 으로 폴더를 스캔해주세요.")
        return

    results = search_files(LAST_SCANS[user_id], keyword)
    await safe_reply(update.message, f"{TAG}\n{format_search_results(results, keyword)}")


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """폴더 종합 리포트: 스캔 + 중복 + 버전 + 용량 + 아카이브를 한 번에."""
    scan = await _scan_for_analysis(update, context)
    if not scan:
        return

    await update.message.reply_text(f"{TAG} [종합 리포트] {scan.root_path}\n분석 중...")

    summary = format_scan_summary(scan)
    await safe_reply(update.message, f"{TAG}\n{summary}")

    size_text = analyze_size(scan)
    await safe_reply(update.message, f"{TAG}\n{size_text}")

    await update.message.reply_text(f"{TAG} 중복 파일 검사 중...")
    groups = find_duplicates(scan)
    await safe_reply(update.message, f"{TAG}\n{format_duplicates(groups)}")

    chains = find_version_chains(scan)
    await safe_reply(update.message, f"{TAG}\n{format_version_chains(chains)}")

    yearly = suggest_archive(scan)
    await safe_reply(update.message, f"{TAG}\n{format_archive_suggestion(yearly)}")


async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pending = PENDING_SCANS.get(user_id)

    if not pending:
        await update.message.reply_text("먼저 /scan 으로 폴더를 스캔해주세요.")
        return

    await _execute_pending(update.message, user_id)


async def _execute_pending(message_or_query, user_id: int):
    pending = PENDING_SCANS.pop(user_id, None)
    if not pending:
        return

    if pending["type"] == "gdrive":
        result = execute_drive_organization(
            pending["root_path"].replace("gdrive://", ""),
            pending["classification"],
        )
        moved = len(result.get("moved", []))
        failed = len(result.get("failed", []))
        text = f"[드라이브 정리 완료] {moved}개 이동"
        if failed:
            text += f", {failed}개 실패"
    else:
        result = execute_organization(pending["root_path"], pending["classification"])
        text = format_result(result)

    if hasattr(message_or_query, "reply_text"):
        await message_or_query.reply_text(text)
    else:
        await message_or_query.edit_message_text(text)


async def organize_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if query.data == "run_organize":
        await query.edit_message_text("정리 실행 중...")
        await _execute_pending(query, user_id)
    elif query.data == "cancel_organize":
        PENDING_SCANS.pop(user_id, None)
        await query.edit_message_text("정리를 취소했습니다.")


async def undo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("되돌리는 중...")
    result = undo_last()
    await update.message.reply_text(format_undo_result(result))


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(format_history())


async def rule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(format_rules())
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "형식: /rule 패턴 폴더명 [설명]\n예: /rule *.pptx 문서/프레젠테이션"
        )
        return

    pattern = context.args[0]
    folder = context.args[1]
    desc = " ".join(context.args[2:]) if len(context.args) > 2 else ""
    result = add_rule(pattern, folder, desc)
    await update.message.reply_text(result)


async def delrule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("형식: /delrule 패턴\n예: /delrule *.pptx")
        return
    result = remove_rule(context.args[0])
    await update.message.reply_text(result)


async def gdrive_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not gdrive_available():
        await update.message.reply_text(
            "Google Drive가 연결되지 않았습니다.\n"
            "credentials.json 파일을 프로젝트 폴더에 넣어주세요."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "폴더 ID를 입력해주세요.\n"
            "예: /gdrive 1abc2def3ghi\n\n"
            "폴더 ID는 구글 드라이브 URL에서 확인:\n"
            "drive.google.com/drive/folders/[여기가 ID]"
        )
        return

    folder_id = context.args[0]
    await update.message.reply_text(f"드라이브 스캔 중... {folder_id}")

    scan_result = scan_drive_folder(folder_id)
    if scan_result.error:
        await update.message.reply_text(f"[스캔 실패] {scan_result.error}")
        return

    summary = format_scan_summary(scan_result)
    await update.message.reply_text(summary)

    await update.message.reply_text("AI 분류 분석 중...")
    classification = classify_files(scan_result.files)

    if not classification or "error" in (classification or {}):
        await update.message.reply_text(
            format_classification(classification, scan_result.root_path)
        )
        return

    classification = apply_rules(scan_result.files, classification)
    preview = format_classification(classification, scan_result.root_path)
    await update.message.reply_text(preview)

    user_id = update.effective_user.id
    PENDING_SCANS[user_id] = {
        "root_path": scan_result.root_path,
        "classification": classification,
        "type": "gdrive",
    }

    keyboard = [
        [
            InlineKeyboardButton("정리 실행", callback_data="run_organize"),
            InlineKeyboardButton("취소", callback_data="cancel_organize"),
        ]
    ]
    await update.message.reply_text(
        "위 분류대로 정리할까요?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """일반 메시지로 경로를 보내면 /scan과 동일하게 처리한다."""
    text = update.message.text.strip()

    looks_like_path = (
        text.startswith("~") or
        (len(text) > 2 and text[1] == ":" and text[2] in "/\\") or  # D:\... or D:/...
        text.startswith("\\\\") or
        (text.startswith("/") and len(text) > 3 and "/" in text[1:])  # /home/user/... (Unix 경로만)
    )

    if looks_like_path:
        context.args = text.split()
        await scan_command(update, context)
    else:
        await update.message.reply_text(
            "폴더 경로를 입력하거나 /scan 명령어를 사용해주세요.\n"
            "도움말: /help"
        )


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다. .env 파일을 확인하세요.")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("scan", scan_command))
    app.add_handler(CommandHandler("run", run_command))
    app.add_handler(CommandHandler("undo", undo_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("rule", rule_command))
    app.add_handler(CommandHandler("delrule", delrule_command))
    app.add_handler(CommandHandler("gdrive", gdrive_command))
    app.add_handler(CommandHandler("dup", dup_command))
    app.add_handler(CommandHandler("ver", ver_command))
    app.add_handler(CommandHandler("size", size_command))
    app.add_handler(CommandHandler("old", old_command))
    app.add_handler(CommandHandler("find", find_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CallbackQueryHandler(organize_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f"File Organizer Bot 시작... [{DEVICE_NAME}]")
    app.run_polling()


if __name__ == "__main__":
    main()
