import logging
import time
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters,
)
from config import TELEGRAM_BOT_TOKEN, DEVICE_NAME, BLOCKED_PATHS, QUICK_PATHS
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


def _build_quick_path_lines(prefix: str = "/scan") -> str:
    """현재 PC에 존재하는 폴더만 자동으로 경로 안내를 생성한다."""
    labels = {
        "desktop": "바탕화면", "downloads": "다운로드",
        "documents": "문서", "pictures": "사진",
    }
    lines = []
    for key, path in QUICK_PATHS.items():
        label = labels.get(key, key)
        lines.append(f"  {prefix} {path}  ({label})")
    return "\n".join(lines)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quick = _build_quick_path_lines()
    text = (
        f"{TAG} 안녕하세요!\n"
        "폴더 경로를 보내주시면,\n"
        "AI가 알아서 깔끔하게 정리해드려요.\n\n"
        "정리 전에 미리보기를 먼저 보여드리고,\n"
        "확인하신 후에만 실행돼요.\n"
        "실수해도 /undo 한 번이면 원래대로 돌아와요.\n\n"
        "--- 바로 시작하기 ---\n"
        "아래 경로를 복사해서 보내보세요.\n\n"
        f"{quick}\n\n"
        "--- 폴더 진단만 하기 ---\n"
        f"  /report {QUICK_PATHS.get('downloads', '경로')}  (종합 리포트)\n\n"
        "전체 명령어가 궁금하면 /help"
    )
    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quick = _build_quick_path_lines()
    text = (
        f"{TAG} 사용 가이드\n\n"
        "1. 폴더 정리하기\n"
        "  /scan 경로      폴더를 분석해요\n"
        "  /scan 경로 -r   하위 폴더까지 포함\n"
        "  → AI가 분류안을 보여드려요\n"
        "  → '정리 실행' 버튼 또는 /run\n"
        "  → 실수했다면 /undo\n\n"
        "2. 내 폴더 진단하기\n"
        "  /report 경로    한번에 종합 진단\n"
        "  /dup 경로       같은 파일 중복 찾기\n"
        "  /ver 경로       보고서_최종_수정 같은 버전 찾기\n"
        "  /size 경로      용량 많이 차지하는 파일\n"
        "  /old 경로       오래된 파일 연도별 정리 제안\n"
        "  /find 키워드    파일 이름으로 검색\n\n"
        "3. 나만의 규칙 만들기\n"
        "  /rule               등록된 규칙 보기\n"
        "  /rule *.pptx 문서   확장자별 폴더 지정\n"
        "  /delrule *.pptx     규칙 삭제\n\n"
        "4. 구글 드라이브\n"
        "  /gdrive 폴더ID  드라이브 폴더도 정리\n\n"
        "/history  정리한 이력 보기\n\n"
        "--- 이 PC 바로가기 ---\n"
        f"{quick}"
    )
    await update.message.reply_text(text)


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        quick = _build_quick_path_lines()
        await update.message.reply_text(
            "정리할 폴더 경로를 알려주세요.\n\n"
            f"--- 이 PC 바로가기 ---\n{quick}"
        )
        return

    recursive = False
    raw_args = list(context.args)
    if raw_args and raw_args[-1] == "-r":
        recursive = True
        raw_args.pop()
    args = " ".join(raw_args)

    resolved = str(Path(args).resolve())
    for blocked in BLOCKED_PATHS:
        if resolved.lower().startswith(blocked.lower()):
            await update.message.reply_text(
                f"{TAG} [차단] 시스템 폴더는 정리할 수 없습니다: {args}\n"
                "바탕화면, 다운로드, 문서, 사진 등 개인 폴더를 사용해주세요."
            )
            return

    folder_name = Path(args).name or args
    await update.message.reply_text(f"{TAG} '{folder_name}' 폴더를 살펴보고 있어요...")

    scan_result = scan_local(args, recursive=recursive)
    summary = format_scan_summary(scan_result)
    await safe_reply(update.message, summary)

    if scan_result.error or not scan_result.files:
        return

    file_count = len([f for f in scan_result.files if not f.is_dir])
    await update.message.reply_text(f"파일 {file_count}개를 AI가 분류하고 있어요...")

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
    scan_ts = int(time.time())
    LAST_SCANS[user_id] = scan_result
    PENDING_SCANS[user_id] = {
        "root_path": scan_result.root_path,
        "classification": classification,
        "type": "local",
        "scan_ts": scan_ts,
    }

    folder_count = len(classification.get("folders", {}))
    keyboard = [
        [
            InlineKeyboardButton(
                f"{folder_count}개 폴더로 정리하기",
                callback_data=f"run_organize:{scan_ts}",
            ),
            InlineKeyboardButton("그만두기", callback_data="cancel_organize"),
        ]
    ]
    await update.message.reply_text(
        "위 분류가 마음에 드시면 '정리하기'를 눌러주세요.\n"
        "잘못되면 /undo 로 바로 되돌릴 수 있어요.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------------------------------------------------------------------------
# 분석 명령어
# ---------------------------------------------------------------------------

async def _scan_for_analysis(update, context, recursive=False):
    """분석 명령어 공통: 경로로 스캔하거나 마지막 스캔 재사용."""
    user_id = update.effective_user.id

    if context.args:
        raw_args = list(context.args)
        if raw_args and raw_args[-1] == "-r":
            recursive = True
            raw_args.pop()
        path = " ".join(raw_args)

        resolved = str(Path(path).resolve())
        for blocked in BLOCKED_PATHS:
            if resolved.lower().startswith(blocked.lower()):
                await update.message.reply_text(
                    f"{TAG} [차단] 시스템 폴더는 분석할 수 없습니다: {path}"
                )
                return None

        folder_name = Path(path).name or path
        await update.message.reply_text(f"{TAG} '{folder_name}' 폴더를 살펴보고 있어요...")
        scan_result = scan_local(path, recursive=recursive)
        if scan_result.error:
            await update.message.reply_text(f"{TAG} [스캔 실패] {scan_result.error}")
            return None
        LAST_SCANS[user_id] = scan_result
        return scan_result

    if user_id in LAST_SCANS:
        return LAST_SCANS[user_id]

    await update.message.reply_text(
        f"{TAG} 분석할 폴더 경로를 함께 보내주세요.\n"
        "예: /dup C:\\Users\\이름\\Downloads"
    )
    return None


async def dup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scan = await _scan_for_analysis(update, context)
    if not scan:
        return
    await update.message.reply_text(f"{TAG} 같은 파일이 여러 곳에 있는지 찾고 있어요...")
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
        await update.message.reply_text(
            "어떤 파일을 찾으시나요?\n"
            "예: /find 보고서\n"
            "예: /find KOBA"
        )
        return

    user_id = update.effective_user.id
    keyword = " ".join(context.args)

    if user_id not in LAST_SCANS:
        await update.message.reply_text(
            f"{TAG} 먼저 /scan 으로 폴더를 스캔해주세요.\n"
            "스캔한 결과 안에서 파일을 검색해드려요."
        )
        return

    results = search_files(LAST_SCANS[user_id], keyword)
    await safe_reply(update.message, f"{TAG}\n{format_search_results(results, keyword)}")


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """폴더 종합 리포트: 스캔 + 중복 + 버전 + 용량 + 아카이브를 한 번에."""
    scan = await _scan_for_analysis(update, context)
    if not scan:
        return

    folder_name = Path(scan.root_path).name or scan.root_path
    await update.message.reply_text(f"{TAG} '{folder_name}' 폴더를 종합 진단하고 있어요...")

    summary = format_scan_summary(scan)
    await safe_reply(update.message, f"{TAG}\n{summary}")

    size_text = analyze_size(scan)
    await safe_reply(update.message, f"{TAG}\n{size_text}")

    await update.message.reply_text(f"{TAG} 중복 파일을 찾고 있어요...")
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
        await update.message.reply_text(
            "정리할 내용이 없어요.\n"
            "먼저 /scan 으로 폴더를 스캔해주세요."
        )
        return

    elapsed = time.time() - pending.get("scan_ts", time.time())
    if elapsed > STALE_SCAN_THRESHOLD:
        mins = int(elapsed // 60)
        PENDING_SCANS.pop(user_id, None)
        await update.message.reply_text(
            f"{mins}분이 지나서 파일이 바뀌었을 수 있어요.\n"
            "안전하게 /scan 으로 다시 스캔해주세요."
        )
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


STALE_SCAN_THRESHOLD = 300  # 5분 경과 시 경고

async def organize_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if query.data.startswith("run_organize"):
        parts = query.data.split(":")
        btn_ts = int(parts[1]) if len(parts) > 1 else 0

        pending = PENDING_SCANS.get(user_id)
        if not pending:
            await query.edit_message_text(
                "스캔 결과가 만료되었어요.\n"
                "다시 /scan 으로 폴더를 스캔해주세요."
            )
            return

        if btn_ts and pending.get("scan_ts") != btn_ts:
            await query.edit_message_text(
                "이 버튼은 이전 스캔 결과예요.\n"
                "아래쪽에 최신 버튼이 있어요."
            )
            return

        elapsed = time.time() - pending.get("scan_ts", time.time())
        if elapsed > STALE_SCAN_THRESHOLD:
            mins = int(elapsed // 60)
            await query.edit_message_text(
                f"{mins}분이 지나서 파일이 바뀌었을 수 있어요.\n"
                "안전하게 /scan 으로 다시 스캔해주세요."
            )
            PENDING_SCANS.pop(user_id, None)
            return

        await query.edit_message_text("정리하고 있어요...")
        await _execute_pending(query, user_id)
    elif query.data == "cancel_organize":
        PENDING_SCANS.pop(user_id, None)
        await query.edit_message_text("취소했어요. 파일은 그대로예요.")


async def undo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("원래대로 되돌리고 있어요...")
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

    file_count = len([f for f in scan_result.files if not f.is_dir])
    await update.message.reply_text(f"파일 {file_count}개를 AI가 분류하고 있어요...")
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
    scan_ts = int(time.time())
    PENDING_SCANS[user_id] = {
        "root_path": scan_result.root_path,
        "classification": classification,
        "type": "gdrive",
        "scan_ts": scan_ts,
    }

    keyboard = [
        [
            InlineKeyboardButton("정리 실행", callback_data=f"run_organize:{scan_ts}"),
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
        quick = _build_quick_path_lines()
        await update.message.reply_text(
            "정리할 폴더 경로를 보내주세요.\n\n"
            f"--- 이 PC 바로가기 ---\n{quick}\n\n"
            "사용법이 궁금하면 /help"
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
