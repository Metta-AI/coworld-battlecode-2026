"""Fetch source ZIPs, compile isolated teams, and run an unmodified JVM engine."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

MAX_ARCHIVE = 32 * 1024 * 1024
MAX_SOURCE = 128 * 1024 * 1024
MAX_FILES = 10000
PACKAGE = re.compile(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*", re.ASCII)
MAP = re.compile(r"[A-Za-z0-9_-]+")
RESERVED = {"java", "javax", "jdk", "sun", "battlecode", "softmax"}


class EpisodeError(Exception):
    def __init__(
        self, message: str, kind: str = "config_error", slot: int | None = None
    ):
        super().__init__(message)
        self.kind = kind
        self.slot = slot


def copy_bounded(source, destination, limit: int) -> None:
    total = 0
    while chunk := source.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise EpisodeError("Artifact exceeds size limit", "player_error")
        destination.write(chunk)


def fetch(uri: str, destination: Path) -> None:
    parsed = urlsplit(uri)
    if parsed.scheme == "s3":
        import boto3
        from botocore.config import Config

        response = boto3.client(
            "s3", config=Config(connect_timeout=15, read_timeout=60)
        ).get_object(Bucket=parsed.netloc, Key=unquote(parsed.path.lstrip("/")))
        source = response["Body"]
    elif parsed.scheme == "https":
        source = urlopen(uri, timeout=60)
    elif parsed.scheme in ("", "file"):
        if parsed.netloc:
            raise EpisodeError("Remote file authorities are unsupported")
        source = open(unquote(parsed.path), "rb")
    else:
        raise EpisodeError("Policy URI must be s3://, https://, or a local path")
    try:
        with destination.open("wb") as output:
            copy_bounded(source, output, MAX_ARCHIVE)
    finally:
        source.close()


def extract_sources(archive: Path, destination: Path, package: str | None) -> str:
    """Accept src/ ZIPs, GitHub wrapper directories, and scaffold submission ZIPs."""
    with zipfile.ZipFile(archive) as zf:
        entries = zf.infolist()
        if len(entries) > MAX_FILES or sum(i.file_size for i in entries) > MAX_SOURCE:
            raise EpisodeError("ZIP exceeds source limits", "player_error")
        paths = []
        seen = set()
        for info in entries:
            path = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in info.filename
                or "\x00" in info.filename
                or ":" in info.filename
                or stat.S_ISLNK(mode)
                or info.flag_bits & 1
            ):
                raise EpisodeError("Unsafe or encrypted ZIP entry", "player_error")
            if info.filename in seen:
                raise EpisodeError("Duplicate ZIP entry", "player_error")
            seen.add(info.filename)
            if not info.is_dir() and path.suffix == ".java":
                paths.append((info, path))
        roots = {
            p.parts[: p.parts.index("src") + 1] for _, p in paths if "src" in p.parts
        }
        if len(roots) > 1:
            raise EpisodeError("ZIP contains multiple src/ roots", "player_error")
        root = next(iter(roots), ())
        metadata_path = (
            "/".join((*root[:-1], "battlecode.json")) if root else "battlecode.json"
        )
        if package is None and metadata_path in seen:
            info = zf.getinfo(metadata_path)
            if info.file_size > 4096:
                raise EpisodeError("battlecode.json is too large", "player_error")
            metadata = json.loads(zf.read(info))
            if (
                not isinstance(metadata, dict)
                or set(metadata) != {"package"}
                or not isinstance(metadata["package"], str)
            ):
                raise EpisodeError(
                    "battlecode.json must contain a package string", "player_error"
                )
            package = metadata["package"]
        for info, path in paths:
            if root and path.parts[: len(root)] != root:
                continue
            relative = PurePosixPath(*path.parts[len(root) :])
            # Some scaffold submissions bundle modified engine sources. Never
            # compile those: the pinned engine remains the only Battlecode API.
            if relative.parts[0] == "battlecode":
                continue
            if relative.parts[0] in RESERVED:
                raise EpisodeError(
                    "Source uses a reserved engine/runtime namespace", "player_error"
                )
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as source, target.open("xb") as output:
                copy_bounded(source, output, MAX_SOURCE)
    candidates = sorted(destination.rglob("RobotPlayer.java"))
    if package is None:
        if len(candidates) != 1:
            raise EpisodeError(
                "Specify package when ZIP does not contain exactly one RobotPlayer.java",
                "player_error",
            )
        package = ".".join(candidates[0].relative_to(destination).parts[:-1])
    if not PACKAGE.fullmatch(package) or package.split(".")[0] in RESERVED:
        raise EpisodeError("Invalid player package", "player_error")
    if not destination.joinpath(*package.split("."), "RobotPlayer.java").is_file():
        raise EpisodeError(
            "Selected package is missing RobotPlayer.java", "player_error"
        )
    return package


def child_env() -> dict[str, str]:
    # Neither javac nor player code needs the parent's S3/upload credentials.
    return {
        k: v
        for k, v in os.environ.items()
        if k in {"PATH", "JAVA_HOME", "LANG", "HOME", "TMPDIR"}
    }


def execute(
    command: list[str], log: Path, timeout: int, kind: str, slot: int | None = None
) -> None:
    with log.open("wb") as output:
        try:
            result = subprocess.run(
                command,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                env=child_env(),
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise EpisodeError(
                f"Process timed out; see {log.name}", kind, slot
            ) from error
    if result.returncode:
        raise EpisodeError(
            f"Process exited {result.returncode}; see {log.name}", kind, slot
        )


def validate_request(request: dict) -> tuple[list[dict], str]:
    if not isinstance(request, dict) or set(request) - {
        "version",
        "players",
        "game_config",
    }:
        raise EpisodeError("Unexpected episode request fields")
    if request.get("version") != 1:
        raise EpisodeError("Episode request version must be 1")
    players = request.get("players")
    if not isinstance(players, list) or len(players) != 2:
        raise EpisodeError("Battlecode requires exactly two ordered policy uploads")
    for player in players:
        if not isinstance(player, dict) or set(player) - {"uri", "package", "sha256"}:
            raise EpisodeError("Unexpected policy fields")
        if not isinstance(player.get("uri"), str) or not player["uri"]:
            raise EpisodeError("Each player requires a source ZIP URI")
        if "package" in player and (
            not isinstance(player["package"], str)
            or not PACKAGE.fullmatch(player["package"])
        ):
            raise EpisodeError("Invalid package")
        if "sha256" in player and (
            not isinstance(player["sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", player["sha256"])
        ):
            raise EpisodeError("Invalid sha256")
    config = request.get("game_config", {})
    if not isinstance(config, dict) or set(config) - {"map"}:
        raise EpisodeError(
            "Only map is configurable; upstream maps own seeds and round limits"
        )
    map_name = config.get("map", "DefaultSmall")
    if not isinstance(map_name, str) or not MAP.fullmatch(map_name):
        raise EpisodeError("Invalid map name")
    return players, map_name


def run_episode(request: dict, output: Path, engine: Path) -> dict:
    players, map_name = validate_request(request)
    if not (engine / "maps" / f"{map_name}.map26").is_file():
        raise EpisodeError("Unknown bundled map")
    jar = str(engine / "battlecode.jar")
    with tempfile.TemporaryDirectory(prefix="battlecode-") as temporary:
        work = Path(temporary)
        packages, classes, digests = [], [], []
        for slot, player in enumerate(players):
            archive = work / f"{slot}.zip"
            fetch(player["uri"], archive)
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            if player.get("sha256", digest) != digest:
                raise EpisodeError("Policy SHA-256 mismatch", "player_error", slot)
            source = work / str(slot) / "src"
            source.mkdir(parents=True)
            try:
                package = extract_sources(archive, source, player.get("package"))
            except (
                EpisodeError,
                zipfile.BadZipFile,
                ValueError,
                UnicodeError,
            ) as error:
                raise EpisodeError(str(error), "player_error", slot) from error
            compiled = work / str(slot) / "classes"
            compiled.mkdir()
            # Compile the selected RobotPlayer and its source dependencies. Historical
            # repositories often also contain obsolete packages that must not be built.
            execute(
                [
                    "javac",
                    "-J-Xmx512m",
                    "--release",
                    "21",
                    "-encoding",
                    "UTF-8",
                    "-proc:none",
                    "-classpath",
                    jar,
                    "-sourcepath",
                    str(source),
                    "-d",
                    str(compiled),
                    str(source.joinpath(*package.split("."), "RobotPlayer.java")),
                ],
                output / f"compile-{slot}.log",
                120,
                "player_error",
                slot,
            )
            packages.append(package)
            classes.append(str(compiled))
            digests.append(digest)
        properties = {
            "bc.server.mode": "headless",
            "bc.server.websocket": "false",
            "bc.server.wait-for-client": "false",
            "bc.game.map-path": str(engine / "maps"),
            "bc.game.maps": map_name,
            "bc.server.save-file": str(output / "replay.bc26"),
            "bc.server.validate-maps": "true",
            "bc.server.alternate-order": "false",
            "bc.engine.debug-methods": "false",
            "bc.engine.enable-profiler": "false",
            "bc.engine.show-indicators": "true",
            "bc.server.robot-player-to-system-out": "false",
            "bc.server.robot-player-replay-file-per-team-limit-bytes": "1048576",
        }
        for slot, side in enumerate(("a", "b")):
            properties.update(
                {
                    f"bc.game.team-{side}": f"policy-{slot}",
                    f"bc.game.team-{side}.url": classes[slot],
                    f"bc.game.team-{side}.package": packages[slot],
                    f"bc.game.team-{side}.language": "java",
                }
            )
        opens = [
            f"--add-opens=java.base/{name}=ALL-UNNAMED"
            for name in (
                "jdk.internal.misc",
                "jdk.internal.math",
                "jdk.internal.util",
                "jdk.internal.access",
                "sun.security.action",
            )
        ]
        execute(
            [
                "java",
                "-Xmx2g",
                *opens,
                *[f"-D{k}={v}" for k, v in properties.items()],
                "-cp",
                jar,
                "battlecode.server.Main",
                "-c=-",
            ],
            output / "engine.log",
            # Upstream allows 20 minutes per team. Leave room for both teams
            # and engine overhead without replacing its competition clock.
            int(os.environ.get("BATTLECODE_TIMEOUT_SECONDS", "3000")),
            "game_error",
        )
        execute(
            [
                "java",
                "-Xmx1g",
                "-cp",
                os.pathsep.join((jar, str(engine / "adapter"))),
                "softmax.ReplayResult",
                str(output / "replay.bc26"),
                str(work / "result.json"),
            ],
            output / "replay-reader.log",
            60,
            "game_error",
        )
        result = json.loads((work / "result.json").read_text())
        result.update(
            {
                "map": map_name,
                "packages": packages,
                "policy_sha256": digests,
                "engine_revision": (engine / "revision.txt").read_text().strip(),
            }
        )
        return result


def publish(path: Path, uri: str) -> None:
    parsed = urlsplit(uri)
    if parsed.scheme == "s3":
        import boto3

        boto3.client("s3").upload_file(
            str(path), parsed.netloc, unquote(parsed.path.lstrip("/"))
        )
    elif parsed.scheme == "https":
        with path.open("rb") as body:
            request = Request(
                uri,
                data=body,
                method="PUT",
                headers={"Content-Length": str(path.stat().st_size)},
            )
            with urlopen(request, timeout=120) as response:
                response.read()
    else:
        raise EpisodeError("Upload destination must be s3:// or https://")


def pack(source: Path, package: str, destination: Path) -> None:
    source = source.resolve()
    if (source / "src").is_dir():
        source /= "src"
    if (
        not PACKAGE.fullmatch(package)
        or not source.joinpath(*package.split("."), "RobotPlayer.java").is_file()
    ):
        raise EpisodeError("Package must identify a RobotPlayer.java under src/")
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            zipfile.ZipInfo("battlecode.json"), json.dumps({"package": package}) + "\n"
        )
        for path in sorted(source.rglob("*.java")):
            if path.is_symlink() or not path.resolve().is_relative_to(source):
                raise EpisodeError("Source symlinks are unsupported")
            info = zipfile.ZipInfo(
                str(PurePosixPath("src", *path.relative_to(source).parts))
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--request", type=Path, required=True)
    run.add_argument("--output", type=Path, default=Path("/output"))
    package = commands.add_parser("pack")
    package.add_argument("source", type=Path)
    package.add_argument("--package", required=True)
    package.add_argument("--output", type=Path, required=True)
    commands.add_parser("serve", help="Run the Coworld game-hosted contract")
    args = parser.parse_args()
    if args.command == "serve":
        from battlecode2026.service import serve

        serve()
        return
    if args.command == "pack":
        pack(args.source, args.package, args.output)
        return
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Require a fresh artifact directory so failed reruns cannot publish stale wins.
    if any(output.iterdir()):
        parser.error("Output directory must be empty")
    try:
        request = json.loads(args.request.read_text())
        result = run_episode(
            request,
            output,
            Path(os.environ.get("BATTLECODE_HOME", "/opt/battlecode")).resolve(),
        )
        (output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    except Exception as error:
        failure = {
            "error_type": error.kind
            if isinstance(error, EpisodeError)
            else "game_error",
            "message": str(error)
            if isinstance(error, EpisodeError)
            else type(error).__name__,
        }
        if isinstance(error, EpisodeError) and error.slot is not None:
            failure["failed_policy_index"] = error.slot
        (output / "error.json").write_text(json.dumps(failure, indent=2) + "\n")
        if uri := os.environ.get("BATTLECODE_ERROR_UPLOAD_URI"):
            publish(output / "error.json", uri)
        parser.exit(1, json.dumps(failure) + "\n")
    # Publish results last: their presence means the replay upload also succeeded.
    for name, variable in (
        ("replay.bc26", "BATTLECODE_REPLAY_UPLOAD_URI"),
        ("results.json", "BATTLECODE_RESULTS_UPLOAD_URI"),
    ):
        if uri := os.environ.get(variable):
            publish(output / name, uri)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
