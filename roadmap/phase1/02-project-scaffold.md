# 02. プロジェクト雛形の作成

## 概要

パッケージのディレクトリ構成と git 管理の初期設定を行う。
後続タスクがファイルを置く場所を先に確定させ、生成物を誤ってコミットしないようにする。

## 実施内容

- `ytmp3/` パッケージを作成し、空の `__init__.py` を置く
- `ytmp3/cli.py`、`ytmp3/downloader.py`、`ytmp3/progress.py` を空ファイルとして作成する
- `ytmp3/__main__.py` を作成し、`from ytmp3.cli import main` して `main()` を呼ぶだけの内容にする
- `tests/` ディレクトリを作成する
- `.gitignore` を作成し、`.venv/`、`downloads/`、`__pycache__/`、`*.pyc`、`.DS_Store` を記載する
- `git init` を実行する

## 完了条件

- 上記ファイル・ディレクトリがすべて存在する
- `python -c "import ytmp3"` がエラーなく通る
- `git status` で `.venv/` と `downloads/` が未追跡ファイルとして表示されない
