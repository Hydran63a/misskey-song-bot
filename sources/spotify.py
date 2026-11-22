"""Spotify プレイリストから楽曲を取得するソース。

必要な設定: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN, SPOTIFY_PLAYLIST_ID

Spotify の仕様（2026年2月の変更以降）:
  - プレイリストの曲は、認証したユーザーが所有または共同編集しているプレイリストしか取得できない
  - そのため Client Credentials ではなく、ユーザー認証で得たリフレッシュトークンを使う
  - 開発モードのアプリは、アプリ所有者が Spotify Premium に加入している必要がある
リフレッシュトークンは `python main.py spotify-auth` で取得できる。
"""

import base64
import logging
import re
import secrets
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

from config import (
    DB_PATH,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_PLAYLIST_ID,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_REFRESH_TOKEN,
    require,
)
from .base import Song

NAME = "spotify"

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_URL = "https://api.spotify.com/v1"
SCOPES = "playlist-read-private playlist-read-collaborative"

# Spotify がリフレッシュトークンを更新して返したときの保存先（.env より優先）
TOKEN_CACHE = DB_PATH.parent / "spotify_refresh_token"

logger = logging.getLogger(__name__)


def is_configured():
    return bool(
        SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET
        and SPOTIFY_REFRESH_TOKEN and SPOTIFY_PLAYLIST_ID
    )


def parse_playlist_id(value):
    """プレイリストの URL・URI・ID のどれを渡されても ID を返す。"""
    match = re.search(r"playlist[/:]([A-Za-z0-9]+)", value)
    return match.group(1) if match else value.strip()


def _basic_auth():
    raw = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode()}


def _request_token(data):
    response = requests.post(TOKEN_URL, data=data, headers=_basic_auth(), timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"Spotify の認証に失敗しました: {response.status_code} {response.text}")
    return response.json()


def _load_refresh_token():
    if TOKEN_CACHE.exists():
        cached = TOKEN_CACHE.read_text(encoding="utf-8").strip()
        if cached:
            return cached
    return SPOTIFY_REFRESH_TOKEN


def _get_access_token():
    refresh_token = _load_refresh_token()
    token = _request_token({"grant_type": "refresh_token", "refresh_token": refresh_token})

    new_refresh_token = token.get("refresh_token")
    if new_refresh_token and new_refresh_token != refresh_token:
        TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE.write_text(new_refresh_token, encoding="utf-8")
        TOKEN_CACHE.chmod(0o600)
        logger.info("Spotify のリフレッシュトークンが更新されたので保存しました")

    return token["access_token"]


def _to_song(entry):
    """プレイリストの1項目を Song に変換する。曲でないもの・ローカル曲は None。"""
    item = entry.get("item")
    if not isinstance(item, dict) or item.get("type") != "track":
        return None
    if entry.get("is_local") or item.get("is_local") or not item.get("id"):
        return None

    track_id = item["id"]
    artists = ", ".join(a["name"] for a in item.get("artists", []) if a.get("name"))
    return Song(
        source=NAME,
        source_id=track_id,
        title=item.get("name") or "タイトル不明",
        url=(item.get("external_urls") or {}).get("spotify")
            or f"https://open.spotify.com/track/{track_id}",
        artist=artists or None,
    )


def fetch_songs():
    """プレイリストの曲を取得する。ポッドキャストのエピソードとローカル曲は除外する。"""
    headers = {"Authorization": f"Bearer {_get_access_token()}"}
    playlist_id = parse_playlist_id(SPOTIFY_PLAYLIST_ID)

    url = f"{API_URL}/playlists/{playlist_id}/items"
    params = {"limit": 50}
    songs, seen = [], set()

    while url:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code == 403:
            raise RuntimeError(
                "Spotify プレイリストを読めません。認証したアカウントが所有または"
                "共同編集しているプレイリストか確認してください"
            )
        response.raise_for_status()
        data = response.json()

        for entry in data.get("items", []):
            song = _to_song(entry)
            if song and song.source_id not in seen:
                seen.add(song.source_id)
                songs.append(song)

        url = data.get("next")  # next には limit などが含まれている
        params = None

    return songs


def authorize():
    """ブラウザで Spotify にログインし、リフレッシュトークンを取得して表示する。"""
    require("SPOTIFY_CLIENT_ID", SPOTIFY_CLIENT_ID)
    require("SPOTIFY_CLIENT_SECRET", SPOTIFY_CLIENT_SECRET)

    redirect = urllib.parse.urlparse(SPOTIFY_REDIRECT_URI)
    state = secrets.token_urlsafe(16)
    result = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if query.get("state", [None])[0] == state:
                result.update({k: v[0] for k, v in query.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("認証が完了しました。このタブは閉じて構いません。".encode())

        def log_message(self, *args):
            pass

    auth_url = AUTHORIZE_URL + "?" + urllib.parse.urlencode({
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
    })

    print("ブラウザで次の URL を開き、Spotify にログインしてください:\n")
    print(auth_url + "\n")
    webbrowser.open(auth_url)

    with HTTPServer((redirect.hostname, redirect.port), CallbackHandler) as server:
        while not result:
            server.handle_request()

    if "error" in result:
        raise RuntimeError(f"Spotify の認証が拒否されました: {result['error']}")

    token = _request_token({
        "grant_type": "authorization_code",
        "code": result["code"],
        "redirect_uri": SPOTIFY_REDIRECT_URI,
    })

    print("認証に成功しました。次の行を .env に追加してください:\n")
    print(f"SPOTIFY_REFRESH_TOKEN={token['refresh_token']}")
