import os
import socket
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

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

BLOCKED_PATHS = {
    "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)",
    "C:\\ProgramData", "C:\\Recovery", "C:\\System Volume Information",
    "/usr", "/bin", "/sbin", "/etc", "/var", "/boot", "/sys", "/proc",
    "/System", "/Library",
}

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "history.json")
RULES_FILE = os.path.join(os.path.dirname(__file__), "rules.json")
PATHS_FILE = os.path.join(os.path.dirname(__file__), "paths.json")
STATS_FILE = os.path.join(os.path.dirname(__file__), "stats.json")

HOME_DIR = os.path.expanduser("~")
QUICK_PATHS = {
    "desktop": os.path.join(HOME_DIR, "Desktop"),
    "downloads": os.path.join(HOME_DIR, "Downloads"),
    "documents": os.path.join(HOME_DIR, "Documents"),
    "pictures": os.path.join(HOME_DIR, "Pictures"),
    "music": os.path.join(HOME_DIR, "Music"),
    "videos": os.path.join(HOME_DIR, "Videos"),
}
for _alias, _path in list(QUICK_PATHS.items()):
    if not os.path.isdir(_path):
        QUICK_PATHS.pop(_alias)
