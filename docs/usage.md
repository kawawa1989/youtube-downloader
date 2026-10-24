# ytmp3 利用手順

実際に手を動かす順に並べた手順書です。
オプションの一覧は [README](../README.md) を参照してください。

## 0. 前提

| 必要なもの | 確認コマンド | 無い場合 |
| --- | --- | --- |
| Python 3.10 以上 | `python3 --version` | [python.org](https://www.python.org/) または `brew install python` |
| ffmpeg | `ffmpeg -version` | `brew install ffmpeg` |

ffmpeg は mp3 への変換に必須です。入っていない場合、ツールはダウンロードを始める前に
導入手順を表示して終了します。

## 1. 初回セットアップ（最初の一度だけ）

```bash
cd ~/Projects/youtube-downloader

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

導入できたか確認します。

```bash
python -m ytmp3 --version
# => ytmp3 0.1.0
```

## 2. 毎回の実行手順

**このツールはプロジェクトルートから実行してください。** 別のディレクトリからは
`No module named ytmp3` になります。

```bash
cd ~/Projects/youtube-downloader
source .venv/bin/activate     # プロンプトに (.venv) が付けば有効
python -m ytmp3 "<URL>"
```

作業が終わったら `deactivate` で仮想環境を抜けます。

> [!IMPORTANT]
> **macOS には素の `python` コマンドがありません。** Homebrew の Python も `python3` しか
> 入れないため、`python` が使えるのは仮想環境を有効化したあとだけです。有効化せずに
> 実行すると `command not found: python` になります。
>
> 有効化が面倒な場合は、仮想環境の python を直接指定しても同じです。この場合は
> 有効化は不要ですが、プロジェクトルートにいる必要があります。
>
> ```bash
> cd ~/Projects/youtube-downloader
> .venv/bin/python -m ytmp3 "<URL>"
> ```

> URL は必ずダブルクォートで囲んでください。YouTube の URL には `&` が含まれることがあり、
> 囲まないとシェルがそこでコマンドを切ってしまいます。

## 3. 基本の流れ

### 動画を1本 mp3 にする

```bash
python -m ytmp3 "https://www.youtube.com/watch?v=xxxxxxxxxxx"
```

実行中はこのように表示されます。

```
ダウンロード中  40.3% (9.2MiB/s, 残り 00:08)
変換中...
完了: downloads/動画のタイトル.mp3
```

保存先を指定しなければ、プロジェクト直下の `downloads/` に保存されます。

### 先に中身を確認する

ダウンロードせず、取得対象と保存先だけを表示します。ファイルは一切作られません。

```bash
python -m ytmp3 "<URL>" --dry-run
```

```
動画のタイトル  [12:33]
  -> downloads/動画のタイトル.mp3
対象: 1件 (--dry-run のためダウンロードは行いません)
```

プレイリストや一括処理の前に、何件・どこへ保存されるかを確かめる用途に向いています。

### 音質と保存先を変える

```bash
# 320kbps で、音楽ライブラリへ直接保存する
python -m ytmp3 "<URL>" -b 320 -o ~/Music/mp3
```

ビットレートは `128` / `192` / `256` / `320` から選びます。既定は `192` です。
`-o` は `~` を展開し、ディレクトリが無ければ多階層でも自動で作成します。

## 4. まとめて処理する

### URL リストから一括ダウンロード

1行1 URL のテキストファイルを用意します。空行と `#` で始まる行は無視されます。

```text
# お気に入り
https://www.youtube.com/watch?v=aaaaaaaaaaa
https://www.youtube.com/watch?v=bbbbbbbbbbb

https://www.youtube.com/watch?v=ccccccccccc
```

```bash
python -m ytmp3 -f urls.txt
```

```
[1/3] https://www.youtube.com/watch?v=aaaaaaaaaaa
完了: downloads/1曲目.mp3
[2/3] https://www.youtube.com/watch?v=bbbbbbbbbbb
動画が見つかりません (404): https://www.youtube.com/watch?v=bbbbbbbbbbb
[3/3] https://www.youtube.com/watch?v=ccccccccccc
完了: downloads/3曲目.mp3
完了: 成功 2件 / スキップ 0件 / 失敗 1件
失敗した URL:
  https://www.youtube.com/watch?v=bbbbbbbbbbb: 動画が見つかりません (404)
```

**1件失敗しても残りは処理されます。**

### 失敗した分だけやり直す

```bash
# 失敗した URL を書き出しておく
python -m ytmp3 -f urls.txt --failed-output failed.txt

# 原因に対処してから、そのまま渡して再実行する
python -m ytmp3 -f failed.txt
```

`--failed-output` が書き出すファイルは `-f` の形式そのままなので、加工せず渡せます。
既に成功した分は次の「同じものを二度落とさない」の仕組みでスキップされます。

### プレイリストを処理する

数百件を意図せず落としてしまう事故を防ぐため、**プレイリストの取得には `--playlist` の
明示が必要**です。付けずに渡した場合の挙動は URL の形によって変わります。

| URL の形 | `--playlist` なしの挙動 |
| --- | --- |
| `playlist?list=...`（プレイリスト専用） | 何も保存せずに中断し、`--playlist` を促す |
| `watch?v=...&list=...`（動画が特定できる） | その動画1本だけを取得する |

中断した場合の表示:

```
プレイリストの URL です: https://www.youtube.com/playlist?list=...
  全件取得するには --playlist を付けてください
```

全件取得するには明示します。

```bash
# まず件数と中身を確認する
python -m ytmp3 "<プレイリストURL>" --playlist --dry-run

# 問題なければ実行する
python -m ytmp3 "<プレイリストURL>" --playlist
```

プレイリスト名のサブディレクトリに、連番付きで保存されます。

```
downloads/プレイリスト名/01 - 1曲目.mp3
downloads/プレイリスト名/02 - 2曲目.mp3
```

## 5. 保存先とファイル名の決まり

- **保存先**: 既定は `downloads/`。`-o` で変更できます。
- **ファイル名**: 動画タイトルをそのまま使います。日本語はそのまま残ります。
  macOS で扱いづらい `/` と `:` は全角に置き換え、150 文字で切り詰めます。
- **同じものを二度落とさない**: 保存先に同名の mp3 があるとスキップします。

  ```
  スキップ: 動画のタイトル.mp3 (既に存在)
  ```

  上書きしたいときは `--force` を付けます。サイズ 0 の壊れたファイルは残骸とみなし、
  自動で取り直します。
- **タイトルが重複したとき**: 同じ実行の中で別の動画が同じタイトルだった場合は
  ` (2)`, ` (3)` を付けて別ファイルにします。

## 6. メタデータ

mp3 には以下が自動で書き込まれます。音楽プレイヤーに取り込めばそのまま表示されます。

| タグ | 内容 |
| --- | --- |
| タイトル | 動画タイトル |
| アーティスト | 動画の artist 情報、無ければチャンネル名 |
| 日付 | 公開年 |
| カバーアート | 動画のサムネイル |

## 7. 終了コード

シェルスクリプトから呼ぶ場合に使えます。

| コード | 意味 |
| --- | --- |
| `0` | 全件成功（スキップのみの場合も含む） |
| `1` | 1件以上の失敗、または起動時のエラー |
| `2` | 引数の指定ミス |
| `130` | `Ctrl+C` による中断 |

```bash
python -m ytmp3 -f urls.txt || echo "失敗がありました"
```

## 8. 困ったとき

### 取得に失敗する

まず yt-dlp を更新してください。失敗の大半は、YouTube 側の変更に yt-dlp が
追従していないことが原因です。

```bash
pip install -U yt-dlp
```

本ツールは yt-dlp が半年以上古い場合、起動時に警告を出します。

### `No supported JavaScript runtime could be found` と出る

yt-dlp が YouTube の解析に JavaScript ランタイムを使うようになったためです。
現状は警告だけで動作しますが、一部のフォーマットが取得できない場合があります。
解消するには deno を導入します。

```bash
brew install deno
```

### `ffmpeg が見つかりません` と出る

```bash
brew install ffmpeg
```

### `command not found: python` と出る

仮想環境を有効化していません。`source .venv/bin/activate` を実行してください。

`python3` に書き換えても動きません。依存の yt-dlp は仮想環境の中にしか入っていないため、
`No module named 'yt_dlp'` になります。有効化せずに実行する場合は
`.venv/bin/python -m ytmp3 ...` と直接指定します。

### `No module named ytmp3` と出る

プロジェクトルート以外から実行しています。`cd ~/Projects/youtube-downloader` してから
実行してください。

### 途中で止めたい

`Ctrl+C` で中断できます。`.part` などの一時ファイルは自動で削除されます。

### エラーの意味がわからない

エラーは原因別に日本語で表示されます。`詳細:` の行に yt-dlp の原文も併記されるので、
分類に当てはまらないものはそちらを手がかりにしてください。

```
この動画は非公開です: https://www.youtube.com/watch?v=xxxxxxxxxxx
  詳細: ERROR: [youtube] xxxxxxxxxxx: Private video. Sign in if you've been granted access
```

## 9. 利用上の注意

自分がアップロードした動画、権利処理済みの音源、クリエイティブ・コモンズ等の
再利用が許諾された素材など、**権利的に問題のない範囲で利用してください**。
YouTube の利用規約上、一般の動画をダウンロードするには権利者の許諾が必要です。
