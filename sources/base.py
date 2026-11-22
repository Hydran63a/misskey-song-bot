"""各ソース共通の楽曲データ型。"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Song:
    source: str             # ソース名（例: "youtube"）
    source_id: str          # ソース内での ID（例: YouTube の動画ID）
    title: str
    url: str                # 投稿に載せるリンク
    artist: Optional[str] = None
    description: Optional[str] = None

    @property
    def id(self):
        """DB 上の楽曲ID。ソースをまたいでも重複しないよう「ソース名:ID」にする。"""
        return f"{self.source}:{self.source_id}"
