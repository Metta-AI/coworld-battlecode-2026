#!/usr/bin/env python3
"""Run archived scaffold zipForSubmit tasks; never rewrite their output ZIPs."""

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

SCAFFOLD_REVISION = "f69e2ab872a0061c9d4a684aa1dd798a0829da85"


def checkout(repository: str, revision: str, destination: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(destination)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(destination),
            "fetch",
            "--quiet",
            "--depth",
            "1",
            repository,
            revision,
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(destination),
            "checkout",
            "--quiet",
            "--detach",
            "FETCH_HEAD",
        ],
        check=True,
    )
    actual = subprocess.check_output(
        ["git", "-C", str(destination), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != revision:
        raise RuntimeError("Archive revision mismatch")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("players/archives.json"))
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/scaffold-policies")
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    architecture = "arm64" if platform.machine() in {"arm64", "aarch64"} else "amd64"
    with tempfile.TemporaryDirectory(prefix="bc26-scaffold-") as temporary:
        root = Path(temporary)
        scaffold = root / "scaffold"
        checkout(
            "https://github.com/battlecode/battlecode26-scaffold.git",
            SCAFFOLD_REVISION,
            scaffold,
        )
        for player in json.loads(args.catalog.read_text()):
            repo = root / player["name"]
            checkout(player["repository"], player["revision"], repo)
            source = repo / player["source_directory"]
            project = source.parent
            repairs = []
            if player["source_directory"] == ".":
                project = root / (player["name"] + "-scaffold")
                shutil.copytree(
                    scaffold, project, ignore=shutil.ignore_patterns(".git", "src")
                )
                shutil.copytree(
                    source, project / "src", ignore=shutil.ignore_patterns(".git")
                )
                repairs.append("source-only archive placed in official scaffold src/")
            for relative in (
                "engine_version.txt",
                "client_version.txt",
                "gradle/wrapper/gradle-wrapper.jar",
            ):
                target = project / relative
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(scaffold / relative, target)
                    repairs.append("restored omitted scaffold file: " + relative)
            log = args.output / f"{player['name']}.build.log"
            with log.open("w") as stream:
                subprocess.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "--platform",
                        f"linux/{architecture}",
                        "--cap-drop=ALL",
                        "--security-opt=no-new-privileges",
                        "-v",
                        f"{project}:/work",
                        "-v",
                        "bc26-gradle-cache:/root/.gradle",
                        "-w",
                        "/work",
                        "eclipse-temurin:21-jdk-jammy",
                        "bash",
                        "./gradlew",
                        "--no-daemon",
                        "zipForSubmit",
                    ],
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=600,
                )
            destination = args.output / f"{player['name']}.zip"
            shutil.copyfile(project / "submission.zip", destination)
            records.append(
                {
                    **player,
                    "file": destination.name,
                    "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                    "scaffold_revision": SCAFFOLD_REVISION,
                    "build_repairs": repairs,
                }
            )
            print(f"{player['name']}: {destination}", flush=True)
    (args.output / "provenance.json").write_text(json.dumps(records, indent=2) + "\n")


if __name__ == "__main__":
    main()
