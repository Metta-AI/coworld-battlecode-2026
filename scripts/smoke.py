#!/usr/bin/env python3
"""Run original scaffold, archived SPAARK, and a non-yielding player in Docker."""

import argparse
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path

from battlecode2026.runner import pack

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--scaffold", type=Path, required=True)
parser.add_argument("--spaark", type=Path, required=True)
parser.add_argument("--image", default="coworld-battlecode-2026:dev")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="bc26-smoke-") as temporary:
    inputs = Path(temporary)
    pack(args.scaffold, "examplefuncsplayer", inputs / "example.zip")
    pack(args.spaark, "SPAARK", inputs / "spaark.zip")
    with zipfile.ZipFile(inputs / "spin.zip", "w") as archive:
        archive.writestr(
            "src/spin/RobotPlayer.java",
            """package spin;
import battlecode.common.*;
public class RobotPlayer {
    public static void run(RobotController rc) {
        while (true) { /* Deliberately never call Clock.yield(). */ }
    }
}
""",
        )
    with zipfile.ZipFile(inputs / "broken.zip", "w") as archive:
        archive.writestr("src/broken/RobotPlayer.java", "this is not Java")
    for name, a, b, package_a, package_b in [
        (
            "same-package",
            "example",
            "example",
            "examplefuncsplayer",
            "examplefuncsplayer",
        ),
        ("historical", "spaark", "example", "SPAARK", "examplefuncsplayer"),
        ("bytecode-enforcement", "spin", "example", "spin", "examplefuncsplayer"),
        ("compile-failure", "broken", "example", "broken", "examplefuncsplayer"),
    ]:
        request = {
            "version": 1,
            "game_config": {"map": "DefaultSmall"},
            "players": [
                {"uri": f"/inputs/{a}.zip", "package": package_a},
                {"uri": f"/inputs/{b}.zip", "package": package_b},
            ],
        }
        (inputs / "request.json").write_text(json.dumps(request))
        case = output / name
        case.mkdir()
        case.chmod(0o777)
        completed = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network=none",
                "--memory=4g",
                "--cpus=2",
                "--pids-limit=256",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,nosuid,size=1g",
                "-v",
                f"{inputs}:/inputs:ro",
                "-v",
                f"{case}:/output",
                args.image,
                "run",
                "--request",
                "/inputs/request.json",
            ],
            timeout=800,
            check=False,
        )
        if name == "compile-failure":
            assert completed.returncode != 0
            error = json.loads((case / "error.json").read_text())
            assert (
                error["error_type"] == "player_error"
                and error["failed_policy_index"] == 0
            )
            assert not (case / "results.json").exists()
        else:
            assert completed.returncode == 0, f"{name} failed; inspect {case}"
            result = json.loads((case / "results.json").read_text())
            assert sorted(result["scores"]) == [0.0, 1.0] and result["rounds"] > 0
            assert (case / "replay.bc26").read_bytes().startswith(b"\x1f\x8b")
        print(f"PASS {name}", flush=True)
