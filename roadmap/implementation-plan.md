# YouTube → mp3 ダウンローダー 実装計画

## 概要

YouTube 動画の音声を mp3 として保存する CLI ツールを作成する。
Python + yt-dlp をコアに、音声変換は ffmpeg に任せる。

## 技術選定

| 項目 | 選択 | 理由 |
| --- | --- | --- |
| 言語 | Python 3.15 | 開発機に導入済み。yt-dlp が Python 製でライブラリとして直接利用できる |
| ダウンロード | yt-dlp | youtube-dl の後継。YouTube 側の仕様変更への追従が速い |
| 音声変換 | ffmpeg 9.0.2（導入済み） | yt-dlp の postprocessor 経由で mp3 化 |
| CLI | argparse | 標準ライブラリで要件を満たす |
| 環境隔離 | venv | Homebrew の Python 環境を汚さない |

## ディレクトリ構成

```
youtube-downloader/
├── README.md
├── requirements.txt        # yt-dlp
├── .gitignore              # .venv/, downloads/
├── ytmp3/
│   ├── __init__.py
│   ├── __main__.py         # python -m ytmp3 のエントリポイント
│   ├── cli.py              # 引数パース
│   ├── downloader.py       # yt-dlp ラッパー（中核）
│   └── progress.py         # 進捗フック表示
├── tests/
│   └── test_downloader.py  # オプション生成ロジックのテスト
├── roadmap/                # 本計画とタスク定義
└── downloads/              # 既定の出力先（git 管理外）
```

## フェーズ構成

### フェーズ1: MVP（まず動くものを）

単一 URL を渡したら mp3 が1つ出来上がる、という最小の経路を通す。

- venv 構築と yt-dlp 導入
- プロジェクト雛形の作成
- `download()` の実装（bestaudio 取得 → FFmpegExtractAudio で mp3 化）
- `python -m ytmp3 <URL>` が動く CLI
- 実 URL での動作確認

### フェーズ2: CLI オプション

実用に必要な入出力の制御を足す。

- `-o/--output`、`-b/--bitrate`、`--playlist/--no-playlist`
- `-f/--file` による URL 一括処理
- `--dry-run`

### フェーズ3: 品質まわり

音楽プレイヤーで扱って違和感のない mp3 にする。

- ID3 メタデータ埋め込み
- サムネイルのジャケット埋め込み
- ファイル名サニタイズ（macOS 対応）
- 進捗表示
- 重複スキップ

### フェーズ4: エラー処理と仕上げ

一括処理で止まらない、落ちても理由がわかるツールにする。

- エラー分類と日本語メッセージ
- リトライと継続処理
- ffmpeg 事前チェック
- 処理サマリと終了コード
- ユニットテスト
- README と git 初期化

## 検討ポイント

- **yt-dlp の更新**: YouTube 側の変更で突然動かなくなるため、README に `pip install -U yt-dlp` を明記する。起動時にバージョンの古さを警告する案もある。
- **GUI の要否**: 今回は CLI 前提。将来 Tkinter や FastAPI を上に載せられるよう、`downloader.py` は CLI に依存しない形で書く。
- **利用範囲**: 自分でアップロードした動画、権利処理済み音源、CC ライセンス素材など権利的に問題のない範囲での利用を想定する。YouTube の利用規約上、一般の動画のダウンロードには権利者の許諾が必要である旨を README に記載する。

## 見積もり

| フェーズ | 目安 |
| --- | --- |
| フェーズ1 | 10分 |
| フェーズ2 | 15分 |
| フェーズ3 | 20分 |
| フェーズ4 | 15分 |
