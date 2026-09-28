#!/usr/bin/env python3
"""Reproduce source-only policy ZIPs from pinned public Battlecode archives."""

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from battlecode2026.runner import pack

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--catalog", type=Path, default=Path("players/archives.json"))
parser.add_argument("--output", type=Path, default=Path("artifacts/policies"))
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
records = []
for player in json.loads(args.catalog.read_text()):
    with tempfile.TemporaryDirectory(prefix="bc26-import-") as temporary:
        checkout = Path(temporary)
        for command in (
            ["git", "init", "--quiet", str(checkout)],
            [
                "git",
                "-C",
                str(checkout),
                "fetch",
                "--quiet",
                "--depth",
                "1",
                player["repository"],
                player["revision"],
            ],
            [
                "git",
                "-C",
                str(checkout),
                "checkout",
                "--quiet",
                "--detach",
                "FETCH_HEAD",
            ],
        ):
            subprocess.run(command, check=True)
        revision = subprocess.check_output(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
        ).strip()
        if revision != player["revision"]:
            raise RuntimeError("Archive revision mismatch")
        destination = args.output / f"{player['name'].lower()}.zip"
        pack(checkout / player["source_directory"], player["package"], destination)
        records.append(
            {
                **player,
                "file": destination.name,
                "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            }
        )
        print(f"{player['name']}: {destination}")
(args.output / "provenance.json").write_text(json.dumps(records, indent=2) + "\n")
