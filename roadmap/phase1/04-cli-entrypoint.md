# 04. CLI エントリポイントの実装

## 概要

`ytmp3/cli.py` に argparse ベースのコマンドライン入口を実装する。
`python -m ytmp3 <URL>` で動く状態にし、ツールとして起動できるようにする。
オプションの拡充はフェーズ2で行うため、ここでは URL 1個を受け取る最小構成にとどめる。

## 実施内容

- `build_parser()` を実装し、位置引数 `url` を1つ受け取る `ArgumentParser` を返す
  - `prog` は `ytmp3`、`description` にツールの説明を日本語で記載する
- `main(argv=None)` を実装する
  - 引数をパースし、`downloader.download()` を呼ぶ
  - 完了時に出力先パスを標準出力に表示する
  - 戻り値として終了コード（成功時 0）を返す
- `__main__.py` から `sys.exit(main())` を呼ぶ形にする

## 完了条件

- `python -m ytmp3 <URL>` で mp3 が生成され、出力先パスが表示される
- `python -m ytmp3 --help` で使い方が日本語で表示される
- 引数なしで実行するとエラーメッセージと終了コード 2 が返る
