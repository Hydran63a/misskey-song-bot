"""YouTube プレイリストから楽曲を取得するソース。

必要な設定: YOUTUBE_API_KEY, YOUTUBE_PLAYLIST_ID
"""

import logging
import re

from googleapiclient.discovery import build

from config import YOUTUBE_API_KEY, YOUTUBE_PLAYLIST_ID
from .base import Song

NAME = "youtube"

logger = logging.getLogger(__name__)

# 説明欄からアーティスト名を探すパターン（上から順に試す）
ARTIST_PATTERNS = [
    re.compile(rf"^\s*{label}\s*[:：]\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
    for label in ("アーティスト", "Artist", "歌唱", "Vocal")
]


def is_configured():
    return bool(YOUTUBE_API_KEY and YOUTUBE_PLAYLIST_ID)


def extract_artist(description):
    """YouTube の説明欄からアーティスト名を抽出する。見つからなければ None。"""
    for pattern in ARTIST_PATTERNS:
        match = pattern.search(description or "")
        if match:
            return match.group(1).strip()
    return None


def _get_playlist_video_ids(youtube, playlist_id):
    """プレイリスト内の動画IDを重複なく、並び順のまま取得する。"""
    video_ids = []
    page_token = None

    while True:
        response = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=page_token,
        ).execute()

        for item in response.get("items", []):
            video_id = item.get("snippet", {}).get("resourceId", {}).get("videoId")
            if video_id and video_id not in video_ids:
                video_ids.append(video_id)

        page_token = response.get("nextPageToken")
        if not page_token:
            return video_ids


def _get_video_snippets(youtube, video_ids):
    """動画情報を50件ずつ取得し、{video_id: snippet} で返す。"""
    snippets = {}
    for i in range(0, len(video_ids), 50):
        response = youtube.videos().list(
            part="snippet",
            id=",".join(video_ids[i:i + 50]),
            maxResults=50,
        ).execute()
        for video in response.get("items", []):
            snippets[video["id"]] = video["snippet"]
    return snippets


def fetch_songs():
    """プレイリストの楽曲を取得する。削除・非公開などで情報が取れない動画は除外する。"""
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY, cache_discovery=False)

    video_ids = _get_playlist_video_ids(youtube, YOUTUBE_PLAYLIST_ID)
    snippets = _get_video_snippets(youtube, video_ids)

    songs = []
    for video_id in video_ids:
        snippet = snippets.get(video_id)
        if not snippet:
            logger.warning("取得不可（削除・非公開の可能性）: %s", video_id)
            continue

        description = snippet.get("description", "")
        songs.append(Song(
            source=NAME,
            source_id=video_id,
            title=snippet.get("title", "タイトル不明"),
            url=f"https://www.youtube.com/watch?v={video_id}",
            artist=extract_artist(description),
            description=description,
        ))

    return songs
