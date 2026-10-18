# 05. ユニットテスト

## 概要

ネットワークアクセスを伴わない純粋なロジックにテストを書く。
yt-dlp や YouTube 側の変化に左右されず、自前のコードの退行を検出できるようにする。

## 実施内容

- `tests/test_downloader.py` を作成する
- `build_options()` のテスト
  - ビットレート指定が `preferredquality` に反映される
  - `--no-playlist` 時に `noplaylist: True` になる
  - `outtmpl` に出力ディレクトリが含まれる
- `sanitize_filename()` のテスト
  - `/` と `:` が置換される
  - 日本語が保持される
  - 長いタイトルが切り詰められる
  - 空になる入力でフォールバックが働く
- `cli.build_parser()` のテスト
  - 既定値が期待どおり
  - 不正なビットレートで `SystemExit` が送出される
  - URL と `--file` の両方が未指定の場合にエラーになる
- エラー分類関数のテスト（代表的な yt-dlp エラーメッセージ文字列を入力に使う）
- `requirements.txt` とは別に `requirements-dev.txt` に pytest を記載する

## 完了条件

- `pytest` が全件成功する
- テストがネットワークに接続せず、数秒以内に完了する
- 上記4領域それぞれにテストケースが存在する
