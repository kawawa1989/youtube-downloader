"""ネットワークに接続しない範囲のロジックを検証する。"""

from __future__ import annotations

import datetime
import os

import pytest

from ytmp3 import cli, downloader


# --- build_options ---------------------------------------------------------


def _postprocessor(key: str, **kwargs) -> dict:
    """指定したキーの postprocessor 設定を返す。並び順には依存しない。"""
    for pp in downloader.build_options(**kwargs)["postprocessors"]:
        if pp["key"] == key:
            return pp
    raise AssertionError(f"postprocessor {key} が見つかりません")


def test_bitrate_is_passed_to_postprocessor():
    assert _postprocessor("FFmpegExtractAudio", bitrate=320)["preferredquality"] == "320"


def test_noplaylist_is_true_by_default():
    assert downloader.build_options()["noplaylist"] is True


def test_noplaylist_is_false_in_playlist_mode():
    assert downloader.build_options(playlist=True)["noplaylist"] is False


def test_postprocessor_order_puts_metadata_and_thumbnail_after_extraction():
    keys = [pp["key"] for pp in downloader.build_options()["postprocessors"]]
    assert keys == ["MetadataParser", "FFmpegExtractAudio", "FFmpegMetadata", "EmbedThumbnail"]


def test_playlist_mode_keeps_the_same_postprocessor_order():
    keys = [pp["key"] for pp in downloader.build_options(playlist=True)["postprocessors"]]
    assert keys == ["MetadataParser", "FFmpegExtractAudio", "FFmpegMetadata", "EmbedThumbnail"]


def _parser_actions(playlist: bool = False) -> list[tuple[str, str]]:
    """MetadataParser のアクションを (対象フィールド, 正規表現) の組で返す。"""
    parser = downloader.build_options(playlist=playlist)["postprocessors"][0]
    assert parser["key"] == "MetadataParser"
    assert parser["when"] == "pre_process"
    return [(action[1], action[2]) for action in parser["actions"]]


def test_description_is_blanked_before_metadata_is_written():
    assert ("description", "(?P<description>)") in _parser_actions()


def test_description_is_blanked_in_playlist_mode_too():
    assert ("description", "(?P<description>)") in _parser_actions(playlist=True)


def test_album_is_filled_from_playlist_title_only_in_playlist_mode():
    assert (downloader.ALBUM_TEMPLATE, "(?P<album>.+)") in _parser_actions(playlist=True)
    assert (downloader.ALBUM_TEMPLATE, "(?P<album>.+)") not in _parser_actions()


def _run_metadata_parser(info: dict, playlist: bool = False) -> dict:
    """build_options が組み立てた MetadataParser を、実際に info へ適用する。

    設定の形ではなく挙動そのものを確かめるための補助。ネットワークには接続しない。
    """
    from yt_dlp import YoutubeDL
    from yt_dlp.postprocessor import MetadataParserPP

    actions = downloader.build_options(playlist=playlist)["postprocessors"][0]["actions"]
    parser = MetadataParserPP(YoutubeDL({"quiet": True, "no_warnings": True}), actions)
    parser.run(info)
    return info


def test_existing_album_is_kept_in_playlist_mode():
    info = _run_metadata_parser(
        {"album": "公式アルバム", "playlist_title": "マイリスト"}, playlist=True
    )
    assert info["album"] == "公式アルバム"


def test_playlist_title_fills_a_missing_album():
    info = _run_metadata_parser({"playlist_title": "マイリスト"}, playlist=True)
    assert info["album"] == "マイリスト"


def test_album_is_left_alone_when_neither_field_exists():
    info = _run_metadata_parser({}, playlist=True)
    assert info.get("album") in (None, "")


def test_album_is_untouched_in_single_video_mode():
    info = _run_metadata_parser({"playlist_title": "マイリスト"})
    assert "album" not in info


def test_description_is_emptied_by_the_parser():
    info = _run_metadata_parser({"description": "長い説明文" * 50})
    assert info["description"] == ""


def test_empty_capture_matches_any_value_and_yields_an_empty_string():
    """説明文の有無にかかわらず、空文字が代入されることを確かめる。"""
    import re

    from yt_dlp.postprocessor.metadataparser import MetadataParserPP

    pattern = re.compile(
        MetadataParserPP.format_to_regex(downloader.EMPTY_CAPTURE.format("description"))
    )
    for value in ("長い説明文" * 50, "", "NA"):
        match = pattern.search(value)
        assert match is not None
        assert match.groupdict() == {"description": ""}


def test_retry_settings_are_present():
    options = downloader.build_options()
    assert options["retries"] == downloader.RETRIES
    assert options["fragment_retries"] == downloader.RETRIES
    assert options["socket_timeout"] == downloader.SOCKET_TIMEOUT


# --- 出力パスの組み立て -----------------------------------------------------


def test_target_path_contains_output_directory():
    path = downloader._target_path({"title": "曲"}, "/tmp/out", False, 1, set())
    assert path == os.path.join("/tmp/out", "曲.mp3")


def test_target_path_uses_playlist_subdirectory_and_index():
    entry = {"title": "曲", "playlist_title": "アルバム"}
    path = downloader._target_path(entry, "/tmp/out", True, 7, set())
    assert path == os.path.join("/tmp/out", "アルバム", "07 - 曲.mp3")


def test_claim_appends_number_on_collision():
    claimed: set[str] = set()
    first = downloader._claim("/x/a.mp3", claimed)
    claimed.add(first)
    second = downloader._claim("/x/a.mp3", claimed)
    claimed.add(second)
    third = downloader._claim("/x/a.mp3", claimed)
    assert (first, second, third) == ("/x/a.mp3", "/x/a (2).mp3", "/x/a (3).mp3")


# --- sanitize_filename -----------------------------------------------------


def test_slash_and_colon_are_replaced():
    assert downloader.sanitize_filename("AC/DC: Live") == "AC／DC： Live"


def test_japanese_is_preserved():
    assert downloader.sanitize_filename("【公式】テスト動画") == "【公式】テスト動画"


def test_control_characters_are_removed():
    assert downloader.sanitize_filename("a\tb\nc") == "abc"


def test_long_title_is_truncated():
    assert len(downloader.sanitize_filename("あ" * 300)) == downloader.MAX_FILENAME_LENGTH


def test_empty_result_falls_back():
    assert downloader.sanitize_filename("   ...   ", fallback="dQw4w9") == "dQw4w9"


def test_leading_and_trailing_dots_are_stripped():
    assert downloader.sanitize_filename("..hidden..") == "hidden"


# --- format_duration -------------------------------------------------------


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(None, "--:--"), (0, "--:--"), (95, "01:35"), (3725, "1:02:05")],
)
def test_format_duration(seconds, expected):
    assert downloader.format_duration(seconds) == expected


# --- エラー分類 -------------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("ERROR: [youtube] a: Private video. Sign in if you have been granted access",
         "この動画は非公開です"),
        ("ERROR: [youtube] a: The uploader has not made this video available in your country",
         "この動画はお住まいの地域では視聴できません"),
        ("ERROR: [youtube] a: Video unavailable. Sign in to confirm your age",
         "年齢制限付きの動画のため取得できません"),
        ("ERROR: [youtube] a: Video unavailable. This video has been removed by the uploader",
         "この動画は削除されているか、公開されていません"),
        ("ERROR: [generic] m: Unable to download webpage: HTTP Error 404: File not found",
         "動画が見つかりません (404)"),
        ("ERROR: [generic] not-a-url is not a valid URL",
         "URL の形式が正しくありません"),
        ("ERROR: unable to download webpage: <urlopen error [Errno 8] nodename nor servname>",
         "ネットワークに接続できません"),
        ("ERROR: 未知のなにか", "取得に失敗しました"),
    ],
)
def test_classify_error(message, expected):
    assert downloader.classify_error(Exception(message), "u").summary == expected


def test_extraction_failure_suggests_update():
    error = downloader.classify_error(
        Exception("ERROR: [youtube] a: Failed to extract any player response"), "u"
    )
    assert error.hint == downloader.UPDATE_HINT


def test_classify_error_keeps_original_message():
    error = downloader.classify_error(Exception("ERROR: 未知のなにか"), "u")
    assert "未知のなにか" in error.detail


def test_classify_error_passes_through_ytmp_error():
    original = downloader.YtmpError("既に分類済み", "u")
    assert downloader.classify_error(original, "u") is original


def test_describe_includes_url_and_hint():
    text = downloader.YtmpError("要約", "https://x/y", detail="詳しい話", hint="ヒント").describe()
    assert "https://x/y" in text and "ヒント" in text and "詳しい話" in text


# --- バージョン警告と後片付け -----------------------------------------------


def test_stale_version_warning_is_silent_when_fresh():
    import yt_dlp

    released = datetime.datetime.strptime(yt_dlp.version.__version__[:10], "%Y.%m.%d").date()
    assert downloader.stale_version_warning(released + datetime.timedelta(days=1)) is None


def test_stale_version_warning_fires_when_old():
    import yt_dlp

    released = datetime.datetime.strptime(yt_dlp.version.__version__[:10], "%Y.%m.%d").date()
    old = released + datetime.timedelta(days=downloader.STALE_AFTER_DAYS + 1)
    assert downloader.UPDATE_HINT in downloader.stale_version_warning(old)


def test_cleanup_partials_removes_temporary_files(tmp_path):
    (tmp_path / "keep.mp3").write_text("x")
    (tmp_path / "a.part").write_text("x")
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "b.ytdl").write_text("x")

    assert downloader.cleanup_partials(str(tmp_path)) == 2
    assert (tmp_path / "keep.mp3").exists()


def test_already_downloaded_ignores_empty_file(tmp_path):
    empty = tmp_path / "empty.mp3"
    empty.write_bytes(b"")
    filled = tmp_path / "filled.mp3"
    filled.write_bytes(b"xyz")

    assert downloader._already_downloaded(str(empty)) is False
    assert downloader._already_downloaded(str(filled)) is True


# --- CLI パーサ -------------------------------------------------------------


def test_parser_defaults():
    args = cli.build_parser().parse_args(["https://example.com/v"])
    assert args.url == "https://example.com/v"
    assert args.output == downloader.DEFAULT_OUTDIR
    assert args.bitrate == downloader.DEFAULT_BITRATE
    assert args.playlist is False
    assert args.dry_run is False
    assert args.force is False
    assert args.quiet is False


def test_parser_rejects_unknown_bitrate():
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["https://example.com/v", "-b", "999"])
    assert exc.value.code == 2


def test_parser_accepts_no_playlist_flag():
    assert cli.build_parser().parse_args(["u", "--playlist"]).playlist is True
    assert cli.build_parser().parse_args(["u", "--no-playlist"]).playlist is False


def test_main_errors_without_url_or_file():
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 2


def test_main_reports_missing_url_file(tmp_path, capsys):
    missing = str(tmp_path / "absent.txt")
    assert cli.main(["-f", missing]) == cli.EXIT_FAILED
    assert missing in capsys.readouterr().err


# --- URL リストの読み込み ---------------------------------------------------


def test_read_url_file_skips_blanks_and_comments(tmp_path):
    path = tmp_path / "urls.txt"
    path.write_text(
        "# コメント\n\nhttps://example.com/a\n   https://example.com/b   \n",
        encoding="utf-8",
    )
    assert cli.read_url_file(str(path)) == ["https://example.com/a", "https://example.com/b"]


# --- サマリ -----------------------------------------------------------------


def test_summary_is_omitted_for_single_item(capsys):
    summary = cli.RunSummary(succeeded=1)
    cli._report_summary(summary)
    assert capsys.readouterr().out == ""


def test_summary_counts_are_reported(capsys):
    summary = cli.RunSummary(
        succeeded=8,
        skipped=1,
        failures=[downloader.YtmpError("この動画は非公開です", "https://x/1")],
    )
    cli._report_summary(summary)
    captured = capsys.readouterr()
    assert "成功 8件" in captured.out
    assert "スキップ 1件" in captured.out
    assert "失敗 1件" in captured.out
    assert "https://x/1" in captured.err


def test_failed_urls_file_can_be_fed_back(tmp_path):
    summary = cli.RunSummary(
        failures=[
            downloader.YtmpError("この動画は非公開です", "https://x/1"),
            downloader.YtmpError("動画が見つかりません (404)", "https://x/2"),
        ]
    )
    out = tmp_path / "failed.txt"
    cli._write_failed_urls(summary, str(out))
    assert cli.read_url_file(str(out)) == ["https://x/1", "https://x/2"]


# --- 取得前の計画（_Planner） -----------------------------------------------


def _make_planner(tmp_path, playlist=False, force=False, claimed=None):
    """テスト用に、prepare_filename が使える状態の _Planner を組み立てる。"""
    import yt_dlp

    outdir = str(tmp_path)
    planner = downloader._Planner(
        outdir, playlist, force, set() if claimed is None else claimed
    )
    planner.ydl = yt_dlp.YoutubeDL(
        {"quiet": True, "no_warnings": True, "outtmpl": downloader._temp_outtmpl(outdir)}
    )
    return planner


ENTRY = {"id": "abc123", "ext": "webm", "title": "曲"}


def test_temp_outtmpl_escapes_percent_in_the_output_directory():
    assert downloader._temp_outtmpl("/tmp/100%_music") == os.path.join(
        "/tmp/100%%_music", downloader.TEMP_OUTTMPL
    )


@pytest.mark.parametrize("incomplete", [True, {"ext", "url"}])
def test_planner_defers_while_information_is_incomplete(tmp_path, incomplete):
    planner = _make_planner(tmp_path)
    assert planner.match_filter(dict(ENTRY), incomplete=incomplete) is None
    assert planner.results() == []


def test_planner_plans_each_video_only_once(tmp_path):
    claimed: set[str] = set()
    planner = _make_planner(tmp_path, claimed=claimed)
    planner.match_filter(dict(ENTRY))
    planner.match_filter(dict(ENTRY))
    assert len(claimed) == 1
    assert len(planner.results()) == 1


def test_planner_lets_a_new_video_through(tmp_path):
    planner = _make_planner(tmp_path)
    assert planner.match_filter(dict(ENTRY)) is None
    assert planner.results() == [
        downloader.TrackResult(title="曲", path=str(tmp_path / "曲.mp3"), skipped=False)
    ]


def test_planner_skips_an_already_downloaded_file(tmp_path):
    (tmp_path / "曲.mp3").write_bytes(b"xyz")
    planner = _make_planner(tmp_path)
    assert planner.match_filter(dict(ENTRY)) is not None
    assert planner.results()[0].skipped is True


def test_planner_ignores_an_empty_file(tmp_path):
    (tmp_path / "曲.mp3").write_bytes(b"")
    planner = _make_planner(tmp_path)
    assert planner.match_filter(dict(ENTRY)) is None
    assert planner.results()[0].skipped is False


def test_planner_does_not_skip_when_forced(tmp_path):
    (tmp_path / "曲.mp3").write_bytes(b"xyz")
    planner = _make_planner(tmp_path, force=True)
    assert planner.match_filter(dict(ENTRY)) is None
    assert planner.results()[0].skipped is False


def test_planner_numbers_a_colliding_title(tmp_path):
    claimed: set[str] = set()
    planner = _make_planner(tmp_path, claimed=claimed)
    planner.match_filter({"id": "one", "ext": "webm", "title": "同名"})
    planner.match_filter({"id": "two", "ext": "webm", "title": "同名"})
    assert [os.path.basename(r.path) for r in planner.results()] == [
        "同名.mp3",
        "同名 (2).mp3",
    ]


def test_planner_uses_playlist_subdirectory_and_index(tmp_path):
    planner = _make_planner(tmp_path, playlist=True)
    planner.match_filter(
        {"id": "x", "ext": "webm", "title": "曲", "playlist_title": "リスト", "playlist_index": 3}
    )
    assert planner.results()[0].path == str(tmp_path / "リスト" / "03 - 曲.mp3")


def test_planner_moves_the_produced_file_into_place(tmp_path):
    planner = _make_planner(tmp_path, playlist=True)
    planner.match_filter(
        {"id": "abc123", "ext": "webm", "title": "曲", "playlist_title": "リスト", "playlist_index": 1}
    )
    produced = tmp_path / "abc123.mp3"
    produced.write_bytes(b"audio")

    planner.on_file_done(str(produced))

    final = tmp_path / "リスト" / "01 - 曲.mp3"
    assert final.read_bytes() == b"audio"
    assert not produced.exists()


def test_planner_leaves_unplanned_files_alone(tmp_path):
    planner = _make_planner(tmp_path)
    stray = tmp_path / "無関係.mp3"
    stray.write_bytes(b"keep")
    planner.on_file_done(str(stray))
    assert stray.read_bytes() == b"keep"


def test_entry_index_prefers_the_playlist_index():
    assert downloader._entry_index({"playlist_index": 7}, 1) == 7
    assert downloader._entry_index({}, 4) == 4
    assert downloader._entry_index({"playlist_index": None}, 2) == 2
