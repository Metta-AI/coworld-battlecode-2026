# Battlecode 2026 on Softmax

Runs the original [Battlecode 2026 engine](https://github.com/battlecode/battlecode26)
and both Java players inside one JVM in one Coworld game container. Uses the
existing `game.player_runtime: "game-hosted"` contract; no Arena or platform changes.

The engine is pinned to `103abf6b67a2cf544e6344dddef9318af9ae9193`. Its rules,
maps, instrumenting classloaders, per-robot bytecode budgets, yield/resume behavior,
and cumulative 20-minute team execution limits are unchanged. The outer JVM
watchdog is 50 minutes and the hosted episode limit is 60 minutes, allowing both
teams' legal execution time plus compilation and engine overhead.

## Upload your player

Build your existing scaffold's **`zipForSubmit`** task and upload the resulting
**`submission.zip`** unchanged:

```sh
bash ./gradlew --no-daemon zipForSubmit
coworld upload-policy --file submission.zip --name "My Battlecode Player"
coworld submit "My Battlecode Player:v1" \
  --league league_f4446dd0-3031-4726-9569-1b387accf46d \
  --preference package=myplayer
```

Use the version returned by the upload and replace `myplayer` with your Java
package. Select your player identity before uploading.
**[Follow the full upload guide](docs/upload-player.md)** for installation, login,
player selection, source-only repositories, updates, and submission checks.
No player code changes, policy container, or ZIP metadata are required.

For direct episodes, set `game_config_overrides.player_options` to an ordered
array such as `[{"package":"SPAARK"},{"package":"Delta"}]`.
Each seat compiles into its own directory, so opposing policies may use identical
package names. A single `RobotPlayer.java` is detected automatically.

To reproduce the seven archived baseline submissions, run
`python3 scripts/build_submissions.py`. The helper restores missing scaffold
support files and runs the original `zipForSubmit` tasks without editing player
Java source or repacking the generated ZIPs. See `players/archives.json` for
pinned sources and `players/uploaded_archives.json` for deployed IDs and hashes.
The optional `battlecode2026 pack` command and `scripts/import_players.py` can
instead package sources with `battlecode.json` entrypoint metadata.

## Build and verify

Use current Coworld tooling with support for `game-hosted` file players.

```sh
docker build --platform linux/amd64 -t coworld-battlecode-2026:dev .
coworld build --version 0.1.2 --output coworld_manifest.json
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
Bundled `battlecode/` sources are ignored so archived engine modifications cannot
replace the pinned official engine.
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
runs all seven 2026 archive candidates under dedicated Coworld-owned bot identities.
These platform bots are separate from human accounts. The original two account-owned
entries have been retired from this league; their history remains available.

Publish with `coworld upload-coworld coworld_manifest.json --wait-certification`.
Create a separate `battlecode-2026` league using the platform commissioner. Configure
a two-seat `team_pair` schedule so each pair plays both side assignments, Elo
ranking, and `do_not_run` when fewer than two real players are present. Keep the
ladder disabled until hosted certification and an archived-player match pass.
Deployment IDs and hosted verification evidence are recorded in `docs/deployment.md`.

This repository and the copied scaffold example are distributed under the
included GPL-3.0 license. Archived players retain their upstream provenance and
licenses; their implementations are not rewritten here.
