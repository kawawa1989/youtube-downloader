# 01. venv 構築と依存パッケージ導入

## 概要

プロジェクト専用の Python 仮想環境を作り、yt-dlp を導入する。
Homebrew の Python 環境を汚さず、依存バージョンを再現可能にすることが目的。
以降のすべてのタスクの前提となる最初の作業。

## 実施内容

- プロジェクトルートで `python3 -m venv .venv` を実行する
- `.venv/bin/activate` を有効化し、`pip install -U pip` で pip を更新する
- `pip install yt-dlp` で yt-dlp を導入する
- `pip freeze | grep yt-dlp > requirements.txt` で依存を固定する
- `ffmpeg -version` が通ることを確認する（未導入なら `brew install ffmpeg`）

## 完了条件

- `.venv/` が生成されている
- `requirements.txt` に `yt-dlp==<version>` が記載されている
- 仮想環境内で `python -c "import yt_dlp; print(yt_dlp.version.__version__)"` がバージョンを出力する
- `ffmpeg -version` が正常終了する
