#!/bin/sh
set -eu
output=$1
mkdir -p "$output"
container=$(docker create "${BATTLECODE_IMAGE:-coworld-battlecode-2026:dev}")
trap 'docker rm "$container" >/dev/null' EXIT
# The image builds this directory afresh from the pinned upstream client.
# Replace the output directory atomically enough for the local build hook.
staging=$(mktemp -d)
trap 'docker rm "$container" >/dev/null; rm -rf "$staging"' EXIT
docker cp "$container:/opt/battlecode/viewer/." "$staging/"
python3 - "$staging" "$output" <<'PY'
from pathlib import Path
import shutil
import sys
source, target = map(Path, sys.argv[1:])
for child in target.iterdir():
    if child.is_dir() and not child.is_symlink():
        shutil.rmtree(child)
    else:
        child.unlink()
shutil.copytree(source, target, dirs_exist_ok=True)
PY
