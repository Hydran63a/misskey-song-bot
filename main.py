"""misskey-song-bot のエントリーポイント。

使い方:
    python main.py sync       プレイリスト（YouTube など）と楽曲DBを同期する
    python main.py post       ランダムに1曲選んで Misskey に投稿する
    python main.py test-post  接続確認用のノートを投稿する
    python main.py spotify-auth  Spotify のリフレッシュトークンを取得する
"""

import argparse
import logging
import sys

import database
import misskey
import sources

logger = logging.getLogger("misskey-song-bot")


def cmd_sync():
    database.initialize()
    logger.info("同期開始")
    songs = sources.fetch_all_songs()
    database.upsert_songs(songs)
    for song in songs:
        logger.info("登録: %s / %s", song.title, song.artist or "アーティスト情報なし")
    logger.info("同期完了: 有効な楽曲 %d本", len(songs))


def cmd_post():
    database.initialize()
    song = database.get_random_song()
    if song is None:
        logger.warning("投稿できる楽曲がありません（先に sync を実行してください）")
        return 1

    logger.info("選曲: %s", song["title"])
    note_id = misskey.create_note(misskey.format_song_note(song))

    # 投稿に成功したときだけ履歴に記録する
    database.record_success(song["song_id"], note_id)
    logger.info("投稿成功: Note ID %s（サイクル %d: %d曲目）",
                note_id, database.get_cycle(), database.get_history_count())
    return 0


def cmd_test_post():
    note_id = misskey.create_note(
        "misskey-song-bot 接続テストです！\n\nこの投稿は動作確認用です。"
    )
    logger.info("テスト投稿成功: Note ID %s", note_id)
    return 0


def cmd_spotify_auth():
    from sources import spotify
    spotify.authorize()
    return 0


COMMANDS = {
    "sync": cmd_sync,
    "post": cmd_post,
    "test-post": cmd_test_post,
    "spotify-auth": cmd_spotify_auth,
}


def main(argv=None):
    parser = argparse.ArgumentParser(description="楽曲を Misskey に投稿する bot")
    parser.add_argument("command", choices=COMMANDS.keys())
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    try:
        return COMMANDS[args.command]() or 0
    except Exception:
        logger.exception("%s の実行に失敗しました", args.command)
        return 1


if __name__ == "__main__":
    sys.exit(main())
