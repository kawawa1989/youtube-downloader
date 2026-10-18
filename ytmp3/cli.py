"""コマンドライン引数の解析とエントリポイント。"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass, field

from ytmp3 import __version__
from ytmp3.downloader import (
    BITRATE_CHOICES,
    DEFAULT_BITRATE,
    DEFAULT_OUTDIR,
    YtmpError,
    classify_error,
    cleanup_partials,
    count_entries,
    download,
    format_duration,
    preview,
    stale_version_warning,
)
from ytmp3.progress import make_hook, make_postprocessor_hook

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_INTERRUPTED = 130


@dataclass
class RunSummary:
    """1回の実行の処理結果。"""

    succeeded: int = 0
    skipped: int = 0
    failures: list[YtmpError] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.succeeded + self.skipped + len(self.failures)


def build_parser() -> argparse.ArgumentParser:
    """コマンドライン引数のパーサを組み立てる。"""
    parser = argparse.ArgumentParser(
        prog="ytmp3",
        description="YouTube 動画の音声を mp3 として保存します。",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="ダウンロードする動画の URL",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTDIR,
        metavar="DIR",
        help=f"mp3 の保存先ディレクトリ (既定: {DEFAULT_OUTDIR})",
    )
    parser.add_argument(
        "-b",
        "--bitrate",
        type=int,
        choices=list(BITRATE_CHOICES),
        default=DEFAULT_BITRATE,
        help=f"mp3 のビットレート(kbps) (既定: {DEFAULT_BITRATE})",
    )
    parser.add_argument(
        "--playlist",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="プレイリスト全体を処理する (既定: 単一動画のみ)",
    )
    parser.add_argument(
        "-f",
        "--file",
        metavar="FILE",
        help="URL を1行ずつ列挙したテキストファイル",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ダウンロードせず、取得予定の一覧だけ表示する",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="既に同名ファイルがあっても上書きする",
    )
    parser.add_argument(
        "--failed-output",
        metavar="PATH",
        help="失敗した URL をこのファイルへ書き出す (-f で再実行できる)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="進捗表示を抑制し、結果だけ出力する",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ytmp3 {__version__}",
    )
    return parser


def _warn(*args: object) -> None:
    """標準出力を吐き出してから標準エラーへ書く。

    パイプへ出力する場合、標準出力はブロックバッファされるため、
    先に flush しないと結果行とエラー行の順序が入れ替わる。
    """
    sys.stdout.flush()
    print(*args, file=sys.stderr)
    sys.stderr.flush()


def read_url_file(path: str) -> list[str]:
    """URL リストのファイルを読み込む。空行と # で始まる行は無視する。"""
    urls = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                urls.append(stripped)
    return urls


def main(argv: list[str] | None = None) -> int:
    """引数を解析してダウンロードを実行し、終了コードを返す。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    urls: list[str] = []
    if args.url:
        urls.append(args.url)
    if args.file:
        try:
            urls.extend(read_url_file(args.file))
        except OSError as exc:
            _warn(f"エラー: URL リストを読み込めません: {args.file} ({exc.strerror})")
            return EXIT_FAILED
    if not urls:
        parser.error("URL または -f/--file のいずれかを指定してください")

    outdir = os.path.expanduser(args.output)

    # ドライランは変換もファイル作成も行わないため、ffmpeg も出力先も要らない
    if args.dry_run:
        return _run_dry_run(urls, outdir, args)

    if shutil.which("ffmpeg") is None:
        _warn("エラー: ffmpeg が見つかりません。mp3 への変換に必要です。")
        _warn("導入方法: brew install ffmpeg")
        return EXIT_FAILED

    warning = stale_version_warning()
    if warning and not args.quiet:
        _warn(warning)

    problem = _ensure_writable(outdir)
    if problem is not None:
        _warn(problem)
        return EXIT_FAILED

    try:
        summary = _run_downloads(urls, outdir, args)
    except KeyboardInterrupt:
        removed = cleanup_partials(outdir)
        suffix = f" (一時ファイル {removed} 件を削除しました)" if removed else ""
        _warn(f"\n中断しました{suffix}")
        return EXIT_INTERRUPTED

    _report_summary(summary)
    if summary.failures and args.failed_output:
        _write_failed_urls(summary, args.failed_output)

    return EXIT_FAILED if summary.failures else EXIT_OK


def _ensure_writable(outdir: str) -> str | None:
    """出力先を用意する。問題があればエラーメッセージを返す。"""
    try:
        os.makedirs(outdir, exist_ok=True)
    except OSError as exc:
        return f"エラー: 出力先を作成できません: {outdir} ({exc.strerror})"
    if not os.access(outdir, os.W_OK):
        return f"エラー: 出力先に書き込めません: {outdir}"
    return None


def _run_dry_run(urls: list[str], outdir: str, args: argparse.Namespace) -> int:
    """取得予定の一覧だけを表示する。"""
    total = 0
    claimed: set[str] = set()
    for url in urls:
        try:
            items = preview(
                url,
                outdir=outdir,
                bitrate=args.bitrate,
                playlist=args.playlist,
                claimed=claimed,
                quiet=args.quiet,
            )
        except Exception as exc:
            _warn(classify_error(exc, url).describe())
            continue
        for item in items:
            print(f"{item.title}  [{format_duration(item.duration)}]")
            print(f"  -> {item.path}")
            total += 1
    print(f"対象: {total}件 (--dry-run のためダウンロードは行いません)")
    return EXIT_OK


def _run_downloads(urls: list[str], outdir: str, args: argparse.Namespace) -> RunSummary:
    """URL を順に処理する。1件の失敗では中断しない。"""
    hooks = {
        "progress_hooks": [make_hook(quiet=args.quiet)],
        "postprocessor_hooks": [make_postprocessor_hook(quiet=args.quiet)],
    }
    summary = RunSummary()
    total = len(urls)
    # 実行全体で共有し、URL をまたいでタイトルが重複しても連番を振れるようにする
    claimed: set[str] = set()

    for index, url in enumerate(urls, start=1):
        if total > 1:
            print(f"[{index}/{total}] {url}")
        if args.playlist:
            _report_entry_count(url)

        try:
            results = download(
                url,
                outdir=outdir,
                bitrate=args.bitrate,
                playlist=args.playlist,
                force=args.force,
                hooks=hooks,
                claimed=claimed,
                quiet=args.quiet,
            )
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            error = classify_error(exc, url)
            summary.failures.append(error)
            cleanup_partials(outdir)
            _warn(error.describe())
            continue

        for result in results:
            if result.skipped:
                summary.skipped += 1
                print(f"スキップ: {os.path.basename(result.path)} (既に存在)")
            else:
                summary.succeeded += 1
                print(f"完了: {result.path}")

    return summary


def _report_summary(summary: RunSummary) -> None:
    """処理件数のサマリを表示する。単一件のときは冗長なので省く。"""
    if summary.total <= 1:
        return

    print(
        f"完了: 成功 {summary.succeeded}件 / "
        f"スキップ {summary.skipped}件 / 失敗 {len(summary.failures)}件"
    )
    if summary.failures:
        _warn("失敗した URL:")
        for error in summary.failures:
            _warn(f"  {error.url}: {error.summary}")


def _write_failed_urls(summary: RunSummary, path: str) -> None:
    """失敗した URL を、そのまま -f に渡せる形式で書き出す。"""
    target = os.path.expanduser(path)
    try:
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("# ytmp3: 失敗した URL\n")
            for error in summary.failures:
                handle.write(f"# {error.summary}\n{error.url}\n")
    except OSError as exc:
        _warn(f"エラー: 失敗 URL を書き出せません: {target} ({exc.strerror})")
        return
    print(f"失敗した URL を書き出しました: {target}")


def _report_entry_count(url: str) -> None:
    """プレイリストの総件数を表示する。数えられない場合は何も出さない。"""
    try:
        print(f"{count_entries(url, playlist=True)}件の動画を処理します")
    except Exception:
        pass
