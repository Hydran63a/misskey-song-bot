# misskey-song-bot

プレイリストから楽曲をランダムに選び、Misskey に投稿する bot です。

- プレイリストの内容を SQLite に同期します。
- 1周するまで同じ曲を重複して投稿しません。全曲投稿し終えると次の周に進みます。
- プレイリストから外れた曲や、削除・非公開になった動画は投稿対象から外れます。

## 対応している楽曲ソース

| ソース | 状況 |
| --- | --- |
| YouTube プレイリスト | 対応 |
| Spotify プレイリスト | 対応予定 |

`.env` で設定したソースがすべて使われます。

## 必要なもの

- Python 3.9 以上
- Misskey のアクセストークン（「ノートを作成・削除する」権限）
- YouTube を使う場合: YouTube Data API v3 の API キーとプレイリスト ID

## セットアップ

```sh
git clone https://github.com/<your-name>/misskey-song-bot.git
cd misskey-song-bot

python -m venv .venv
. .venv/bin/activate          # Windows の場合: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env          # .env を編集してトークンなどを設定
```

## 使い方

```sh
python main.py test-post   # 接続確認用のノートを投稿
python main.py sync        # プレイリストを DB に同期
python main.py post        # ランダムに1曲選んで投稿
```

コマンドは失敗すると終了コード 1 を返します。

### 定期実行の例（cron）

```cron
# 毎日 8:50 にプレイリストを同期し、9:00 に投稿する
50 8 * * * cd /opt/misskey-song-bot && .venv/bin/python main.py sync >> sync.log 2>&1
0  9 * * * cd /opt/misskey-song-bot && .venv/bin/python main.py post >> post.log 2>&1
```

## ファイル構成

| ファイル | 役割 |
| --- | --- |
| `main.py` | コマンドの入口（sync / post / test-post） |
| `config.py` | `.env` から設定を読み込む |
| `database.py` | 楽曲・投稿履歴の SQLite 操作と選曲 |
| `misskey.py` | Misskey へのノート投稿 |
| `sources/` | 楽曲の取得元。ソースごとに1ファイル |
| `sources/youtube.py` | YouTube プレイリストから楽曲を取得 |

YouTube では、動画の説明欄にある `アーティスト:`、`Artist:`、`歌唱:`、`Vocal:` の行からアーティスト名を取り出します。

## 新しい楽曲ソースを追加するには

`sources/` にモジュールを作って次の3つを定義し、`sources/__init__.py` の `SOURCES` に追加します。

- `NAME`: ソース名（例: `"spotify"`）。DB 上の楽曲 ID は `spotify:<ID>` の形になります
- `is_configured()`: 必要な設定が `.env` にそろっていれば `True`
- `fetch_songs()`: `sources.base.Song` のリストを返す

## 旧バージョンからの移行

YouTube 専用だった旧形式の DB（`video_id` 列）は、初回実行時に自動で新しい形式に移行されます。
移行前の DB は `data/songs.db.v1.bak` に保存されます。
