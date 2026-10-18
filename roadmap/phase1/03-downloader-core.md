# 03. ダウンロード処理の中核実装

## 概要

`ytmp3/downloader.py` に yt-dlp のラッパーを実装する。
URL を受け取って mp3 を1ファイル出力する、本ツールの中心となる処理。
CLI に依存しない純粋な関数として作り、将来 GUI から呼べる形を保つ。

## 実施内容

- `build_options(outdir, bitrate)` を実装し、yt-dlp のオプション辞書を返す
  - `format`: `"bestaudio/best"`
  - `outtmpl`: `f"{outdir}/%(title)s.%(ext)s"`
  - `postprocessors`: `FFmpegExtractAudio`（`preferredcodec="mp3"`, `preferredquality=str(bitrate)`）
  - `quiet`: `True`、`no_warnings`: `False`
- `download(url, outdir="downloads", bitrate=192)` を実装する
  - 出力ディレクトリを `os.makedirs(outdir, exist_ok=True)` で用意する
  - `yt_dlp.YoutubeDL(opts)` のコンテキスト内で `ydl.download([url])` を呼ぶ
  - 生成された mp3 のパスを戻り値として返す
- この段階では例外はそのまま呼び出し元へ送出する（整形はフェーズ4で行う）

## 完了条件

- `python -c "from ytmp3.downloader import download; download('<テスト用URL>')"` で `downloads/` に mp3 が生成される
- 生成された mp3 が `ffprobe` でコーデック `mp3`、ビットレート約 192kbps と確認できる
- `downloader.py` が `argparse` や標準出力への表示に依存していない
