"""ダウンロード進捗の表示。

yt-dlp に渡すフック関数を組み立てるだけの表示専用モジュール。
downloader 側は表示方法を知らず、フックを受け取るだけにする。
"""

from __future__ import annotations

import sys
from typing import Any, Callable, TextIO

from ytmp3.downloader import format_duration

# 端末でない場合に進捗を出力する間隔
LINE_MODE_PERCENT_STEP = 10.0
LINE_MODE_BYTE_STEP = 1024 * 1024


def make_hook(quiet: bool = False, stream: TextIO | None = None) -> Callable[[dict], None]:
    """yt-dlp の progress_hooks に渡す関数を返す。"""
    out = stream if stream is not None else sys.stdout
    state: dict[str, Any] = {"percent": -LINE_MODE_PERCENT_STEP, "bytes": 0, "live": False}

    def hook(status: dict[str, Any]) -> None:
        if quiet:
            return
        if status.get("status") == "downloading":
            _show_downloading(status, out, state)
        elif status.get("status") == "finished":
            _show_converting(out, state)

    return hook


def make_postprocessor_hook(
    quiet: bool = False,
    stream: TextIO | None = None,
) -> Callable[[dict], None]:
    """yt-dlp の postprocessor_hooks に渡す関数を返す。

    mp3 への変換が終わった時点で進捗行を閉じ、呼び出し元が
    結果行を綺麗に出力できる状態にする。
    """
    out = stream if stream is not None else sys.stdout

    def hook(status: dict[str, Any]) -> None:
        if quiet:
            return
        if status.get("postprocessor") == "ExtractAudio" and status.get("status") == "finished":
            _close_line(out)

    return hook


def _show_downloading(status: dict[str, Any], out: TextIO, state: dict[str, Any]) -> None:
    downloaded = status.get("downloaded_bytes") or 0
    total = status.get("total_bytes") or status.get("total_bytes_estimate")
    percent = (downloaded / total * 100) if total else None

    head = f"{percent:5.1f}%" if percent is not None else format_bytes(downloaded)
    detail = []
    if status.get("speed"):
        detail.append(f"{format_bytes(status['speed'])}/s")
    if status.get("eta"):
        detail.append(f"残り {format_duration(status['eta'])}")

    text = f"ダウンロード中 {head}"
    if detail:
        text += " (" + ", ".join(detail) + ")"

    if _is_tty(out):
        print(f"\r\033[K{text}", end="", file=out, flush=True)
        state["live"] = True
        return

    # 端末でない場合は行更新が使えないため、間隔を空けて通常の行として出す
    if percent is not None:
        if percent - state["percent"] < LINE_MODE_PERCENT_STEP:
            return
        state["percent"] = percent
    else:
        if downloaded - state["bytes"] < LINE_MODE_BYTE_STEP:
            return
        state["bytes"] = downloaded
    print(text, file=out, flush=True)


def _show_converting(out: TextIO, state: dict[str, Any]) -> None:
    if _is_tty(out):
        print("\r\033[K変換中...", end="", file=out, flush=True)
        state["live"] = True
    else:
        print("変換中...", file=out, flush=True)


def _close_line(out: TextIO) -> None:
    """行更新で書いていた進捗行を閉じる。"""
    if _is_tty(out):
        print("\r\033[K", end="", file=out, flush=True)


def _is_tty(out: TextIO) -> bool:
    try:
        return out.isatty()
    except (AttributeError, ValueError):
        return False


def format_bytes(num: float) -> str:
    """バイト数を人間が読める単位に整形する。"""
    value = float(num)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}GiB"
