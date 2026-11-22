"""Misskey へノートを投稿するモジュール。"""

import requests

from config import MISSKEY_HOST, MISSKEY_TOKEN, MISSKEY_VISIBILITY, require


def create_note(text, visibility=MISSKEY_VISIBILITY):
    """ノートを投稿し、作成されたノートの ID を返す。"""
    host = require("MISSKEY_HOST", MISSKEY_HOST)
    token = require("MISSKEY_TOKEN", MISSKEY_TOKEN)

    response = requests.post(
        f"{host}/api/notes/create",
        json={"i": token, "text": text, "visibility": visibility},
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()

    if result.get("error"):
        raise RuntimeError(f"Misskey APIエラー: {result['error']}")

    note_id = (result.get("createdNote") or {}).get("id")
    if not note_id:
        raise RuntimeError("投稿結果からノートIDを取得できませんでした")

    return note_id


def format_song_note(song):
    """楽曲紹介ノートの本文を作る。"""
    return (
        "🎵 **本日の楽曲セレクト！**\n\n"
        f"{song['title']}\n"
        f"{song['url']}"
    )
