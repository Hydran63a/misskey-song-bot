"""楽曲の取得元（ソース）をまとめるパッケージ。

新しいソース（例: Spotify）を追加するには:
  1. このフォルダにモジュールを作り、次の3つを定義する
       NAME            ソース名（例: "spotify"）。楽曲IDの接頭辞になる
       is_configured() 必要な設定が .env にそろっていれば True
       fetch_songs()   Song のリストを返す
  2. 下の SOURCES に追加する
"""

import logging

from . import youtube
from .base import Song

SOURCES = [youtube]

logger = logging.getLogger(__name__)

__all__ = ["Song", "SOURCES", "fetch_all_songs"]


def fetch_all_songs():
    """設定済みのすべてのソースから楽曲を取得する。

    1つでも失敗したら例外を投げる（中途半端な結果で DB を更新しないため）。
    """
    sources = [source for source in SOURCES if source.is_configured()]
    if not sources:
        raise ValueError("楽曲ソースが1つも設定されていません（.env を確認してください）")

    songs = []
    for source in sources:
        fetched = source.fetch_songs()
        logger.info("%s: %d曲取得", source.NAME, len(fetched))
        songs.extend(fetched)
    return songs
