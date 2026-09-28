import hashlib
import io
import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from battlecode2026.runner import (
    EpisodeError,
    copy_bounded,
    extract_sources,
    fetch,
    pack,
    validate_request,
)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def extract(self, entries, package=None):
        archive = self.root / "player.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for name, value in entries:
                zf.writestr(name, value)
        target = self.root / "source"
        target.mkdir()
        return extract_sources(archive, target, package)

    def test_scaffold_src(self):
        self.assertEqual(
            self.extract([("src/example/RobotPlayer.java", "package example;")]),
            "example",
        )

    def test_original_scaffold_submission_zip(self):
        self.assertEqual(
            self.extract([("example/RobotPlayer.java", "package example;")]), "example"
        )

    def test_github_archive_and_ignored_build_script(self):
        self.assertEqual(
            self.extract(
                [
                    ("repo/src/SPAARK/RobotPlayer.java", ""),
                    ("repo/build.gradle", "throw new Exception()"),
                ]
            ),
            "SPAARK",
        )
        self.assertFalse((self.root / "source/build.gradle").exists())

    def test_multiple_historical_players_need_selection(self):
        with self.assertRaisesRegex(EpisodeError, "Specify package"):
            self.extract(
                [("src/old/RobotPlayer.java", ""), ("src/current/RobotPlayer.java", "")]
            )

    def test_explicit_historical_package(self):
        self.assertEqual(
            self.extract(
                [
                    ("src/old/RobotPlayer.java", ""),
                    ("src/current/RobotPlayer.java", ""),
                ],
                "current",
            ),
            "current",
        )

    def test_uploaded_metadata_selects_historical_package(self):
        self.assertEqual(
            self.extract(
                [
                    ("src/old/RobotPlayer.java", ""),
                    ("src/SPAARK/RobotPlayer.java", ""),
                    ("battlecode.json", json.dumps({"package": "SPAARK"})),
                ]
            ),
            "SPAARK",
        )

    def test_invalid_metadata(self):
        with self.assertRaisesRegex(EpisodeError, "package string"):
            self.extract(
                [
                    ("src/bot/RobotPlayer.java", ""),
                    ("battlecode.json", '{"package":12}'),
                ]
            )

    def test_traversal_even_for_non_source(self):
        with self.assertRaisesRegex(EpisodeError, "Unsafe"):
            self.extract([("../escape.txt", ""), ("src/bot/RobotPlayer.java", "")])

    def test_symlink(self):
        info = zipfile.ZipInfo("src/bot/RobotPlayer.java")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaisesRegex(EpisodeError, "Unsafe"):
            self.extract([(info, "/etc/passwd")])

    def test_duplicate_names(self):
        with (
            self.assertWarns(UserWarning),
            self.assertRaisesRegex(EpisodeError, "Duplicate"),
        ):
            self.extract(
                [("src/bot/RobotPlayer.java", ""), ("src/bot/RobotPlayer.java", "")]
            )

    def test_reserved_namespace(self):
        with self.assertRaisesRegex(EpisodeError, "reserved"):
            self.extract([("src/battlecode/common/RobotPlayer.java", "")])

    def test_size_limits(self):
        with (
            patch("battlecode2026.runner.MAX_SOURCE", 3),
            self.assertRaisesRegex(EpisodeError, "limits"),
        ):
            self.extract([("src/bot/RobotPlayer.java", "four")])

    def test_bounded_download(self):
        with self.assertRaises(EpisodeError):
            copy_bounded(io.BytesIO(b"1234"), io.BytesIO(), 3)

    def test_pack_and_fetch_roundtrip(self):
        src = self.root / "repo/src/bot"
        src.mkdir(parents=True)
        (src / "RobotPlayer.java").write_text("package bot;")
        archive = self.root / "upload.zip"
        pack(self.root / "repo", "bot", archive)
        downloaded = self.root / "downloaded.zip"
        fetch(archive.as_uri(), downloaded)
        self.assertEqual(
            hashlib.sha256(archive.read_bytes()).digest(),
            hashlib.sha256(downloaded.read_bytes()).digest(),
        )
        self.assertEqual(extract_sources(downloaded, self.root / "out", None), "bot")
        second = self.root / "second.zip"
        pack(self.root / "repo", "bot", second)
        self.assertEqual(archive.read_bytes(), second.read_bytes())

    def test_unknown_config_is_not_silently_ignored(self):
        with self.assertRaisesRegex(EpisodeError, "Only map"):
            validate_request(
                {
                    "version": 1,
                    "players": [{"uri": "a"}, {"uri": "b"}],
                    "game_config": {"seed": 42},
                }
            )

    def test_two_seats_required(self):
        with self.assertRaisesRegex(EpisodeError, "exactly two"):
            validate_request({"version": 1, "players": [{"uri": "a"}]})


if __name__ == "__main__":
    unittest.main()
