import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from battlecode2026.runner import EpisodeError
from battlecode2026.service import run_hosted, seats_request


class HostedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        upload = self.root / "player.zip"
        upload.write_bytes(b"uploaded bytes")
        self.seats = {
            "schema": "coworld-player-seats/1",
            "seats": [
                {
                    "slot": slot,
                    "file_uri": upload.as_uri(),
                    "size_bytes": upload.stat().st_size,
                    "content_hash": "sha256:"
                    + hashlib.sha256(upload.read_bytes()).hexdigest(),
                    "log_uri": (self.root / f"log-{slot}").as_uri(),
                }
                for slot in range(2)
            ],
        }
        self.config = {"tokens": ["a", "b"], "map": "DefaultSmall"}
        (self.root / "config.json").write_text(json.dumps(self.config))
        (self.root / "seats.json").write_text(json.dumps(self.seats))
        env = patch.dict(
            os.environ,
            {
                "COGAME_CONFIG_URI": (self.root / "config.json").as_uri(),
                "COGAME_PLAYER_SEATS_URI": (self.root / "seats.json").as_uri(),
                "COGAME_RESULTS_URI": (self.root / "results.json").as_uri(),
                "COGAME_SAVE_REPLAY_URI": (self.root / "replay").as_uri(),
                "COGAME_PLAYER_FAILURE_URI": (self.root / "failure.json").as_uri(),
            },
        )
        env.start()
        self.addCleanup(env.stop)

    def test_staged_seats_use_declared_digests(self):
        request = seats_request(self.config, self.seats)
        self.assertEqual(
            request["players"][1]["sha256"], self.seats["seats"][1]["content_hash"][7:]
        )

    def test_submission_preferences_follow_seat_order(self):
        self.config["player_options"] = [{"package": "SPAARK"}, {"package": "Delta"}]
        request = seats_request(self.config, self.seats)
        self.assertEqual(
            [p["package"] for p in request["players"]], ["SPAARK", "Delta"]
        )
        self.config["player_options"].reverse()
        request = seats_request(self.config, self.seats)
        self.assertEqual(
            [p["package"] for p in request["players"]], ["Delta", "SPAARK"]
        )

    def test_incomplete_submission_preferences_rejected(self):
        self.config["player_options"] = [{"package": "SPAARK"}]
        with self.assertRaisesRegex(EpisodeError, "per seat"):
            seats_request(self.config, self.seats)

    def test_bad_slot_order(self):
        self.seats["seats"].reverse()
        with self.assertRaisesRegex(EpisodeError, "ordered"):
            seats_request(self.config, self.seats)

    def test_size_mismatch_attributes_player(self):
        self.seats["seats"][1]["size_bytes"] += 1
        with self.assertRaises(EpisodeError) as error:
            seats_request(self.config, self.seats)
        self.assertEqual(error.exception.slot, 1)

    def test_compile_failure_writes_typed_failure_and_private_logs(self):
        def fail(request, output, engine):
            (output / "compile-1.log").write_text("Private source diagnostic")
            raise EpisodeError("Compilation failed", "player_error", 1)

        with patch("battlecode2026.service.run_episode", side_effect=fail):
            run_hosted({})
        self.assertEqual(
            json.loads((self.root / "failure.json").read_text()),
            {"message": "Compilation failed", "failed_policy_index": 1},
        )
        self.assertEqual((self.root / "log-1").read_text(), "Private source diagnostic")
        self.assertTrue((self.root / "log-0").is_file())
        self.assertFalse((self.root / "results.json").exists())

    def test_results_written_after_logs_and_replay(self):
        from battlecode2026.service import write_atomic

        def success(request, output, engine):
            (output / "replay.bc26").write_bytes(b"replay")
            (output / "compile-0.log").write_text("compiled")
            return {"scores": [1, 0]}

        def observe(path, data):
            if path.name == "results.json":
                self.assertEqual((self.root / "replay").read_bytes(), b"replay")
                self.assertEqual((self.root / "log-0").read_text(), "compiled")
                self.assertTrue((self.root / "log-1").exists())
            write_atomic(path, data)

        with (
            patch("battlecode2026.service.run_episode", side_effect=success),
            patch("battlecode2026.service.write_atomic", side_effect=observe),
        ):
            run_hosted({})
        self.assertEqual(
            json.loads((self.root / "results.json").read_text()), {"scores": [1, 0]}
        )
