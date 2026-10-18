# ytmp3

YouTube 動画の音声を mp3 として保存する CLI ツールです。
ダウンロードは [yt-dlp](https://github.com/yt-dlp/yt-dlp)、音声変換は ffmpeg が担当します。

## 前提

- Python 3.10 以上（開発と動作確認は 3.15 で実施）
- ffmpeg（mp3 への変換に必須）

## セットアップ

```bash
# ffmpeg を導入する
brew install ffmpeg

# 仮想環境を作って依存を入れる
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 使い方

手順を順に追った詳しい説明は [docs/usage.md](docs/usage.md) にあります。

**プロジェクトルートから実行してください。** 別のディレクトリからは
`No module named ytmp3` になります。また URL は `&` を含むことがあるため、
ダブルクォートで囲んでください。

```bash
# 単一動画を mp3 にする（既定: 192kbps、downloads/ に保存）
python -m ytmp3 "https://www.youtube.com/watch?v=..."

# 音質と保存先を指定する
python -m ytmp3 "<URL>" -b 320 -o ~/Music/mp3

# プレイリスト全体を取得する（既定は単一動画のみ）
python -m ytmp3 "<プレイリストURL>" --playlist

# URL をファイルから一括処理する
python -m ytmp3 -f urls.txt

# 取得対象だけ確認する（ファイルは作られない）
python -m ytmp3 -f urls.txt --dry-run

# 失敗した URL を書き出し、あとで再実行する
python -m ytmp3 -f urls.txt --failed-output failed.txt
python -m ytmp3 -f failed.txt
```

`-f` に渡すファイルは1行1 URL です。空行と `#` で始まる行は無視されるため、
`--failed-output` が書き出したファイルをそのまま渡せます。

## オプション

| オプション | 既定値 | 説明 |
| --- | --- | --- |
| `url` | — | ダウンロードする動画の URL（`-f` と併用可） |
| `-o`, `--output DIR` | `downloads` | mp3 の保存先。`~` を展開し、無ければ作成する |
| `-b`, `--bitrate` | `192` | ビットレート(kbps)。`128` / `192` / `256` / `320` |
| `--playlist` / `--no-playlist` | `--no-playlist` | プレイリスト全体を処理するか |
| `-f`, `--file FILE` | — | URL を列挙したテキストファイル |
| `--dry-run` | 無効 | 取得予定の一覧だけ表示し、何も保存しない |
| `--force` | 無効 | 既存の同名ファイルを上書きする |
| `--failed-output PATH` | — | 失敗した URL を書き出す |
| `-q`, `--quiet` | 無効 | 進捗表示を抑制する |
| `--version` | — | バージョンを表示する |

## 動作の約束事

- **保存先**: 指定しなければプロジェクト直下の `downloads/` に保存します。
  このディレクトリの中身は git の追跡対象外です。
- **ファイル名**: 動画タイトルをそのまま使います。macOS で扱いづらい `/` と `:` は全角へ置換し、
  150 文字で切り詰めます。日本語はそのまま残ります。
- **重複**: 保存先に同名の mp3 が既にあるとスキップします。上書きしたい場合は `--force` を使います。
  サイズ 0 の壊れたファイルは残骸とみなし、取り直します。
  同じ実行の中でタイトルが重複した場合は ` (2)`, ` (3)` を付けて別ファイルにします。
- **メタデータ**: タイトル・アーティスト・日付を ID3 タグに書き込み、サムネイルをカバーアートとして埋め込みます。
- **終了コード**: `0` 全件成功（スキップのみを含む）、`1` 1件以上の失敗または起動時エラー、
  `2` 引数エラー、`130` `Ctrl+C` による中断。

## 開発

```bash
pip install -r requirements-dev.txt
pytest
```

テストはネットワークに接続しません。

## トラブルシューティング

- **取得に失敗する**: まず `pip install -U yt-dlp` を試してください。YouTube 側の変更に
  yt-dlp が追従していないことが原因の大半です。本ツールは yt-dlp が半年以上古い場合に警告を出します。
- **`No supported JavaScript runtime could be found`**: yt-dlp が YouTube の解析に
  JavaScript ランタイムを使うようになったためです。警告だけで動作しますが、一部のフォーマットが
  取得できない場合があります。解消するには `brew install deno` を実行してください。
- **`ffmpeg が見つかりません`**: `brew install ffmpeg` を実行してください。
- **`No module named ytmp3`**: プロジェクトルート以外から実行しています。
- **途中で中断した**: `Ctrl+C` で止めた場合、`.part` などの一時ファイルは自動的に削除されます。

## 利用上の注意

自分がアップロードした動画、権利処理済みの音源、クリエイティブ・コモンズ等の
再利用が許諾された素材など、**権利的に問題のない範囲で利用してください**。
YouTube の利用規約上、一般の動画をダウンロードするには権利者の許諾が必要です。
本ツールの利用によって生じた責任は利用者が負うものとします。
