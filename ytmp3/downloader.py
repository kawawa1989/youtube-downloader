"""yt-dlp を用いた音声ダウンロードの中核処理。

CLI に依存しない純粋な関数として実装し、将来 GUI などから
同じ関数を呼び出せる状態を保つ。表示は呼び出し元が渡すフックに任せる。

処理の流れは「情報取得 → 出力パス確定 → 取得」の順。
先にパスを確定させることで、ファイル名の正規化と重複判定を
ダウンロードの前に行えるようにしている。
"""

from __future__ import annotations

import datetime
import os
import sys
from dataclasses import dataclass
from typing import Any, Callable, Iterable

import yt_dlp

DEFAULT_OUTDIR = "downloads"
DEFAULT_BITRATE = 192
BITRATE_CHOICES = (128, 192, 256, 320)

# macOS で扱いづらい文字の置換表。日本語を保つため restrictfilenames は使わない。
FILENAME_REPLACEMENTS = {"/": "／", ":": "："}
MAX_FILENAME_LENGTH = 150

# 一時的な通信エラーで処理全体が止まらないようにする
RETRIES = 3
SOCKET_TIMEOUT = 30

# これより古い yt-dlp は、YouTube 側の変更に追従できていない可能性がある
STALE_AFTER_DAYS = 180

UPDATE_HINT = "yt-dlp の更新が必要かもしれません: pip install -U yt-dlp"

# エラーメッセージの断片と、利用者向けの説明の対応表。上から順に判定する。
ERROR_PATTERNS: tuple[tuple[tuple[str, ...], str, str | None], ...] = (
    (
        ("private video", "video is private", "sign in if you've been granted access"),
        "この動画は非公開です",
        None,
    ),
    # 「Video unavailable.」は地域制限や年齢制限の前置きにも使われるため、
    # より具体的に判定できるものを先に並べる
    (
        ("available in your country", "geo restricted", "geo-restricted", "blocked it in your country",
         "not available from your location", "who has blocked it on copyright grounds"),
        "この動画はお住まいの地域では視聴できません",
        None,
    ),
    (
        ("confirm your age", "age-restricted", "age restricted", "inappropriate for some users"),
        "年齢制限付きの動画のため取得できません",
        None,
    ),
    (
        ("has been removed", "video unavailable", "video has been removed", "account associated"),
        "この動画は削除されているか、公開されていません",
        None,
    ),
    (
        ("http error 404", "not found"),
        "動画が見つかりません (404)",
        None,
    ),
    (
        ("is not a valid url", "unsupported url", "unable to download webpage: <urlopen error unknown url type"),
        "URL の形式が正しくありません",
        None,
    ),
    (
        ("failed to extract any player response", "unable to extract", "nsig extraction failed", "signature extraction failed"),
        "動画情報を読み取れませんでした",
        UPDATE_HINT,
    ),
    (
        ("timed out", "connection reset", "connection refused", "network is unreachable",
         "temporary failure in name resolution", "getaddrinfo", "name or service not known",
         "urlopen error", "connection aborted"),
        "ネットワークに接続できません",
        None,
    ),
    (
        ("sign in to confirm", "bot", "cookies"),
        "YouTube がアクセスを制限しています (サインインが必要です)",
        None,
    ),
)


class YtmpError(Exception):
    """利用者向けの説明を持つ、分類済みのエラー。"""

    def __init__(self, summary: str, url: str, detail: str = "", hint: str | None = None):
        super().__init__(summary)
        self.summary = summary
        self.url = url
        self.detail = detail
        self.hint = hint

    def describe(self) -> str:
        """1件分のエラー表示を組み立てる。"""
        lines = [f"{self.summary}: {self.url}"]
        if self.hint:
            lines.append(f"  {self.hint}")
        if self.detail:
            lines.append(f"  詳細: {self.detail}")
        return "\n".join(lines)


@dataclass
class PreviewItem:
    """ドライラン時に表示する、1件分の取得予定情報。"""

    title: str
    duration: float | None
    path: str


@dataclass
class TrackResult:
    """1件分の処理結果。"""

    title: str
    path: str
    skipped: bool


class _Logger:
    """yt-dlp の出力を制御する。

    エラー行は呼び出し元が分類して表示するため、ここでは捨てる。
    そうしないと yt-dlp の ERROR 行と分類済みメッセージが二重に出る。
    """

    def __init__(self, quiet: bool = False):
        self.quiet = quiet

    def debug(self, message: str) -> None:
        pass

    def info(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        if not self.quiet:
            print(message, file=sys.stderr)

    def error(self, message: str) -> None:
        pass


def classify_error(exc: Exception, url: str) -> YtmpError:
    """yt-dlp の例外を、原因別の利用者向けメッセージへ変換する。"""
    if isinstance(exc, YtmpError):
        return exc

    raw = str(exc)
    lowered = raw.lower()
    for needles, summary, hint in ERROR_PATTERNS:
        if any(needle in lowered for needle in needles):
            return YtmpError(summary, url, detail=_shorten(raw), hint=hint)

    # 分類できないものは原文を添えて、原因調査ができるようにする
    return YtmpError("取得に失敗しました", url, detail=_shorten(raw))


def build_options(
    bitrate: int = DEFAULT_BITRATE,
    playlist: bool = False,
    hooks: dict[str, list[Callable[[dict], None]]] | None = None,
    quiet: bool = False,
) -> dict[str, Any]:
    """yt-dlp に渡すオプション辞書を組み立てる。

    outtmpl は呼び出し元が確定済みのパスで上書きする前提のため、ここでは設定しない。
    """
    postprocessors: list[dict[str, Any]] = [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": str(bitrate),
        },
        {"key": "FFmpegMetadata", "add_metadata": True},
        {"key": "EmbedThumbnail", "already_have_thumbnail": False},
    ]

    if playlist:
        # album が無い動画では、プレイリスト名をアルバム名として扱う
        from yt_dlp.postprocessor import MetadataParserPP

        postprocessors.insert(
            0,
            {
                "key": "MetadataParser",
                "when": "pre_process",
                "actions": [
                    (MetadataParserPP.interpretter, "playlist_title", "(?P<album>.+)"),
                ],
            },
        )

    options: dict[str, Any] = {
        "format": "bestaudio/best",
        "noplaylist": not playlist,
        "writethumbnail": True,
        "postprocessors": postprocessors,
        "retries": RETRIES,
        "fragment_retries": RETRIES,
        "socket_timeout": SOCKET_TIMEOUT,
        "quiet": True,
        "no_warnings": False,
        "noprogress": True,
        "logger": _Logger(quiet),
    }
    if hooks:
        options.update(hooks)
    return options


def download(
    url: str,
    outdir: str = DEFAULT_OUTDIR,
    bitrate: int = DEFAULT_BITRATE,
    playlist: bool = False,
    force: bool = False,
    hooks: dict[str, list[Callable[[dict], None]]] | None = None,
    claimed: set[str] | None = None,
    quiet: bool = False,
) -> list[TrackResult]:
    """URL の音声を mp3 として保存し、1件ごとの処理結果を返す。

    claimed には、同じ実行の中で既に割り当て済みの出力パスを渡す。
    複数 URL をまとめて処理する場合に呼び出し元が1つの集合を共有することで、
    タイトルが重複しても連番で別ファイルとして保存できる。

    失敗時は分類済みの YtmpError を送出する。
    """
    os.makedirs(outdir, exist_ok=True)
    results = []
    if claimed is None:
        claimed = set()

    try:
        entries = _probe(url, playlist, quiet)
    except Exception as exc:
        raise classify_error(exc, url) from exc

    for index, entry in enumerate(entries, start=1):
        target = _target_path(entry, outdir, playlist, index, claimed)
        claimed.add(target)
        title = entry.get("title") or entry.get("id") or "(タイトル不明)"

        if not force and _already_downloaded(target):
            results.append(TrackResult(title=title, path=target, skipped=True))
            continue

        entry_url = entry.get("webpage_url") or entry.get("original_url") or url
        try:
            _download_one(entry_url, target, bitrate, playlist, hooks, quiet)
        except Exception as exc:
            raise classify_error(exc, entry_url) from exc
        results.append(TrackResult(title=title, path=target, skipped=False))

    return results


def preview(
    url: str,
    outdir: str = DEFAULT_OUTDIR,
    bitrate: int = DEFAULT_BITRATE,
    playlist: bool = False,
    claimed: set[str] | None = None,
    quiet: bool = False,
) -> list[PreviewItem]:
    """ダウンロードを行わず、取得予定の動画情報だけを取り出す。

    出力予定パスは download() と同じ関数で組み立てるため、両者は必ず一致する。
    """
    items = []
    if claimed is None:
        claimed = set()

    try:
        entries = _probe(url, playlist, quiet)
    except Exception as exc:
        raise classify_error(exc, url) from exc

    for index, entry in enumerate(entries, start=1):
        target = _target_path(entry, outdir, playlist, index, claimed)
        claimed.add(target)
        items.append(
            PreviewItem(
                title=entry.get("title") or entry.get("id") or "(タイトル不明)",
                duration=entry.get("duration"),
                path=target,
            )
        )
    return items


def count_entries(url: str, playlist: bool = False) -> int:
    """処理対象の件数を数える。

    件数表示のためだけの呼び出しなので、個々の動画の詳細取得は省く。
    """
    options = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": not playlist,
        "extract_flat": "in_playlist",
        "logger": _Logger(quiet=True),
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
    return len(_iter_entries(info))


def cleanup_partials(outdir: str) -> int:
    """中断や失敗で残った一時ファイルを削除し、削除した件数を返す。"""
    removed = 0
    for root, _dirs, files in os.walk(outdir):
        for name in files:
            if name.endswith((".part", ".ytdl")):
                try:
                    os.remove(os.path.join(root, name))
                    removed += 1
                except OSError:
                    pass
    return removed


def stale_version_warning(today: datetime.date | None = None) -> str | None:
    """yt-dlp が古い場合に、更新を促すメッセージを返す。"""
    raw = yt_dlp.version.__version__
    try:
        released = datetime.datetime.strptime(raw[:10], "%Y.%m.%d").date()
    except ValueError:
        return None

    age = ((today or datetime.date.today()) - released).days
    if age > STALE_AFTER_DAYS:
        return f"警告: yt-dlp {raw} は約 {age} 日前の版です。{UPDATE_HINT}"
    return None


def sanitize_filename(name: str, fallback: str = "audio") -> str:
    """動画タイトルを、macOS で安全に扱えるファイル名へ正規化する。

    日本語は読める形のまま残す。結果が空になる場合は fallback を使う。
    """
    cleaned = "".join(FILENAME_REPLACEMENTS.get(ch, ch) for ch in name if ch.isprintable())
    cleaned = cleaned.strip().strip(".").strip()
    if len(cleaned) > MAX_FILENAME_LENGTH:
        cleaned = cleaned[:MAX_FILENAME_LENGTH].rstrip()
    return cleaned or fallback


def format_duration(seconds: float | None) -> str:
    """秒数を MM:SS もしくは H:MM:SS に整形する。"""
    if not seconds:
        return "--:--"
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _shorten(message: str, limit: int = 200) -> str:
    """原文メッセージを1行に収める。"""
    collapsed = " ".join(message.split())
    if len(collapsed) > limit:
        return collapsed[:limit] + "..."
    return collapsed


def _probe(url: str, playlist: bool, quiet: bool) -> list[dict[str, Any]]:
    """ダウンロードせずに動画情報を取得する。"""
    options = {
        "quiet": True,
        "no_warnings": False,
        "noprogress": True,
        "noplaylist": not playlist,
        "retries": RETRIES,
        "socket_timeout": SOCKET_TIMEOUT,
        "logger": _Logger(quiet),
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        return _iter_entries(ydl.extract_info(url, download=False))


def _download_one(
    url: str,
    target: str,
    bitrate: int,
    playlist: bool,
    hooks: dict[str, list[Callable[[dict], None]]] | None,
    quiet: bool,
) -> None:
    """1件を、確定済みのパスへダウンロードする。"""
    options = build_options(bitrate, playlist, hooks, quiet)
    base, _ = os.path.splitext(target)
    # outtmpl 内では % が書式指定の開始として解釈されるため退避する
    options["outtmpl"] = base.replace("%", "%%") + ".%(ext)s"

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])


def _target_path(
    entry: dict[str, Any],
    outdir: str,
    playlist: bool,
    index: int,
    claimed: set[str],
) -> str:
    """1件分の出力先パスを確定する。"""
    title = sanitize_filename(entry.get("title") or "", fallback=entry.get("id") or "audio")

    if playlist:
        album = sanitize_filename(entry.get("playlist_title") or "", fallback="playlist")
        return _claim(os.path.join(outdir, album, f"{index:02d} - {title}.mp3"), claimed)
    return _claim(os.path.join(outdir, f"{title}.mp3"), claimed)


def _claim(path: str, claimed: set[str]) -> str:
    """同じ実行内でパスが衝突した場合に ' (2)', ' (3)' を付与する。

    既存ファイルとの衝突はスキップ判定で扱うため、ここでは見ない。
    """
    if path not in claimed:
        return path
    base, ext = os.path.splitext(path)
    index = 2
    while f"{base} ({index}){ext}" in claimed:
        index += 1
    return f"{base} ({index}){ext}"


def _already_downloaded(path: str) -> bool:
    """取得済みとみなせるか。サイズ 0 の壊れた残骸は対象外とする。"""
    return os.path.exists(path) and os.path.getsize(path) > 0


def _iter_entries(info: dict[str, Any] | None) -> list[dict[str, Any]]:
    """単一動画／プレイリストのどちらでも、動画単位の情報リストを返す。"""
    if info is None:
        return []

    entries: Iterable[dict[str, Any]] | None = info.get("entries")
    if entries is None:
        return [info]

    collected: list[dict[str, Any]] = []
    for entry in entries:
        if entry is None:  # 取得できなかった要素は飛ばす
            continue
        if entry.get("entries") is not None:  # ネストしたプレイリスト
            collected.extend(_iter_entries(entry))
        else:
            collected.append(entry)
    return collected
