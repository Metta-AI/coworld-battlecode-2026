# Battlecode 2026 on Softmax

Runs the original [Battlecode 2026 engine](https://github.com/battlecode/battlecode26)
and both Java players inside one JVM in one Coworld game container. Uses the
existing `game.player_runtime: "game-hosted"` contract; no Arena or platform changes.

The engine is pinned to `103abf6b67a2cf544e6344dddef9318af9ae9193`. Its rules,
maps, instrumenting classloaders, per-robot bytecode budgets, yield/resume behavior,
and cumulative 20-minute team execution limits are unchanged. The outer JVM
watchdog is 50 minutes and the hosted episode limit is 60 minutes, allowing both
teams' legal execution time plus compilation and engine overhead.

## Upload an existing player

Upload a ZIP containing `src/<package>/RobotPlayer.java` and its Java dependencies.
The original scaffold's `zipForSubmit` output (packages at ZIP root) also works.
A single `RobotPlayer.java` is detected automatically. For a repository containing
multiple historical players, add `battlecode.json` at the ZIP root:

```json
{"package": "SPAARK"}
```

The helper packages unchanged Java sources and writes that metadata:

```sh
python3 -m pip install -e .
battlecode2026 pack /path/to/2026-SPAARK --package SPAARK --output spaark.zip
coworld upload-policy --file spaark.zip --name battlecode-2026-spaark
```

Select the intended Softmax player identity before uploading. Submit the exact
returned policy version to the Battlecode 2026 JVM league. Each seat compiles into
its own directory, so opposing policies may use identical package names.
Only the selected entrypoint and referenced Java sources are compiled. Uploaded
Gradle scripts, annotation processors, and precompiled classes are not executed.
This initial port supports Java source, not Scala or Python players. ZIPs are
limited to 32 MiB compressed, 128 MiB expanded, and 10,000 entries.

Reproduce the two archived imports, with pinned commits and SHA-256 provenance:

```sh
PYTHONPATH=src python3 scripts/import_players.py
```

## Build and verify

Use current Coworld tooling with support for `game-hosted` file players.

```sh
docker build --platform linux/amd64 -t coworld-battlecode-2026:dev .
coworld build --version 0.1.1 --output coworld_manifest.json
coworld certify coworld_manifest.json --timeout-seconds 300 --no-open-report
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The manifest bundles the unmodified scaffold example at revision
`f69e2ab872a0061c9d4a684aa1dd798a0829da85`. Certification runs example versus example.
`scripts/smoke.py` additionally checks SPAARK compatibility, identical package
names, an infinite-loop player exercising bytecode enforcement, and compilation
failure attribution. Pass `--scaffold`, `--spaark`, and a fresh `--output` directory.

## Episode contract

Softmax downloads and verifies policy files from S3 in its trusted staging step.
The game reads `COGAME_CONFIG_URI` and `COGAME_PLAYER_SEATS_URI`, extracts each
source ZIP, compiles with Java 21, and runs the unmodified headless engine.
The game reads the winner from the native replay, never player stdout.
The image runs as root to write the existing runner's root-owned artifact
directories. Kubernetes drops Linux capabilities, and the original Battlecode
classloader and bytecode instrumentation restrict uploaded Java code.

- Slots 0/1 are teams A/B; scores are 1 for the winner and 0 for the loser.
- Maps retain upstream seeds, round caps, and tiebreak rules.
- Results include the engine revision, source ZIP hashes, packages, and round count.
- Compilation diagnostics go to each seat's private `log_uri`.
- Invalid sources produce a typed `COGAME_PLAYER_FAILURE_URI` signal for that seat.
- Replay and seat logs finish before the results completion marker is written.

Player stdout is disabled on the public game stream. The pinned upstream engine
discards its internal robot log buffer; this initial wrapper exposes compiler
diagnostics, not robot `println` logs. Runtime exceptions otherwise retain the
original engine's gameplay semantics.

The original browser client is built into a static replay bundle. The only client
changes adapt Coworld's replay URL, start playback automatically, and loop playback.
`/client/global` shows match status and links to the replay after completion;
live board streaming is not yet implemented. Native `.bc26` files remain usable
with the original Battlecode client.

For standalone Docker runs, `battlecode2026 run --request REQUEST --output OUTPUT`
accepts `{"version":1,"players":[{"uri":"..."},{"uri":"..."}],"game_config":{"map":"DefaultSmall"}}`.
Policy URIs may be local paths, S3 URIs, or HTTPS URLs. The output directory must
be empty. Hosted operation uses the standard Coworld file contract instead.

## League

The [live JVM league](https://softmax.com/observatory/v2?detail=league:league_f4446dd0-3031-4726-9569-1b387accf46d)
runs unchanged SPAARK and Gravy source policies. Both side assignments completed
successfully, with native replays and published standings.

Publish with `coworld upload-coworld coworld_manifest.json --wait-certification`.
Create a separate `battlecode-2026` league using the platform commissioner. Configure
a two-seat `team_pair` schedule so each pair plays both side assignments, Elo
ranking, and `do_not_run` when fewer than two real players are present. Keep the
ladder disabled until hosted certification and an archived-player match pass.
Deployment IDs and hosted verification evidence are recorded in `docs/deployment.md`.

This repository and the copied scaffold example are distributed under the
included GPL-3.0 license. Archived players retain their upstream provenance and
licenses; their implementations are not rewritten here.
