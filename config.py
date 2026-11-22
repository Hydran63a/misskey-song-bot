"""環境変数（.env）から設定を読み込むモジュール。"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

# Misskey
MISSKEY_HOST = os.getenv("MISSKEY_HOST", "").rstrip("/")
MISSKEY_TOKEN = os.getenv("MISSKEY_TOKEN", "")
MISSKEY_VISIBILITY = os.getenv("MISSKEY_VISIBILITY", "public")

# YouTube
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_PLAYLIST_ID = os.getenv("YOUTUBE_PLAYLIST_ID", "")

# データベース
DB_PATH = Path(os.getenv("DB_PATH") or BASE_DIR / "data" / "songs.db")


def require(name, value):
    """必須の設定値が空なら例外を投げる。"""
    if not value:
        raise ValueError(f"{name} が設定されていません（.env を確認してください）")
    return value
