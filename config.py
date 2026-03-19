import os
import socket
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 기기 식별 — .env에 DEVICE_NAME을 설정하면 해당 이름 사용, 없으면 PC 이름 자동 감지
DEVICE_NAME = os.getenv("DEVICE_NAME", socket.gethostname())

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".vscode", ".cursor",
    ".idea", ".DS_Store", "$RECYCLE.BIN", "System Volume Information",
}

SKIP_FILES = {
    ".env", ".gitignore", "Thumbs.db", "desktop.ini", ".DS_Store",
}

MAX_FILES_PER_SCAN = 500

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "history.json")
RULES_FILE = os.path.join(os.path.dirname(__file__), "rules.json")
