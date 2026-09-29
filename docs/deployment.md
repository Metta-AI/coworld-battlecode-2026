# Deployment evidence

Target: the separate `battlecode-2026` Coworld and JVM league, using game-hosted
source-file policies on the existing Kubernetes infrastructure.

## Local verification

- 21 focused tests pass (archive validation, source packaging, staged-seat
  integrity, failure attribution, and artifact completion ordering).
- The original scaffold and unchanged SPAARK run successfully in Docker.
- Identical packages on opposing sides work.
- A deliberately infinite-loop Java player completes a match under the original
  bytecode enforcement.
- Unchanged SPAARK versus Gravy completed on DefaultSmall in 219 rounds; Gravy won.
- Current Coworld certification passed all 10 steps, including the real
  game-hosted episode and WebSocket Ping/Pong. Tooling source revision:
  `18b4a69bdffbb9efa8c3577ebd4a3f41a534f30e`.

## Hosted deployment (2026-09-28)

- Coworld: `battlecode-2026:0.1.1`, canonical and certified.
- Coworld ID: `cow_b200bacd-e82f-4855-9351-8771cf08c7f1`.
- Image: `public.ecr.aws/q5f4m8t9/cogames@sha256:99368c96fab7e184a7324b00ec5406e9229bdb91d15bb7c65d58ee8c60eea913`.
- Source revision for the deployed runtime: `ce45207`.
- All ten hosted certification checks passed, including replay loading.
- Five hosted smoke episodes completed successfully. Example:
  `ereq_77270d7e-0316-49db-acee-cdcf5357b569` (1,310 rounds).
- The initial 0.1.0 hosted smoke exposed root-owned artifact directories. With
  explicit user approval, 0.1.1 runs as root to match the existing runner contract.
  No platform code changed; Kubernetes drops capabilities and Battlecode retains
  its original Java sandbox and compute instrumentation.

## League and source policies

[Battlecode 2026 — Original JVM](https://softmax.com/observatory/v2?detail=league:league_f4446dd0-3031-4726-9569-1b387accf46d)

- League: `league_f4446dd0-3031-4726-9569-1b387accf46d`.
- Competition division: `div_5a1c0582-a359-45a1-a6a5-603627881c52`.
- Seed: `lseed_ea3265ac-3a64-4231-80ce-0d0bab7c30b6`, key `original-jvm`.
- Enabled platform ladder, `team_pair` with both side assignments, Elo ranking,
  no filler players, 288-minute cadence, $15/day budget.
- Workflow: `ladder-league_f4446dd0-3031-4726-9569-1b387accf46d`.

| Archive | Uploaded policy | Immutable policy version | Active champion membership |
| --- | --- | --- | --- |
| SPAARK | `battlecode-2026-spaark:v1` | `551a08b3-ce36-4901-84f9-cc32a3306206` | `lpm_502810f3-d683-4cbf-a927-5c0502259c5d` |
| Gravy | `battlecode-2026-gravy:v1` | `79b76c5f-2a6d-4a3b-acf6-03c583ddb12e` | `lpm_36c41c31-05f1-4d7a-95e3-1e1c70c48e3d` |

SPAARK uses player `ply_ca7b13c0-8e78-4e49-8f87-e6bcab971000`; Gravy uses the
account's existing player `ply_305f0175-65a2-47ca-9566-69991871b743`. The account
has a two-active-player limit. No existing player was renamed and no other league
was modified. Both original submissions were placed and verified as champions. They were later
retired when the seven Coworld-owned archive bots replaced the account-owned roster.
Archive revisions and entrypoint packages are pinned in `players/archives.json`.

First round: `round_a0367d74-d443-4257-a97d-6e9139ec5d32`.
Completed at `2026-09-28T22:49:58.976854Z`, with no failures.

| Team A | Team B | Winner | Rounds | Episode request |
| --- | --- | --- | --- | --- |
| SPAARK | Gravy | Gravy | 219 | `ereq_ed1b3595-e501-466b-87a8-9246e9631e36` |
| Gravy | SPAARK | Gravy | 182 | `ereq_34bfdefb-0859-4b6d-a23e-c0aa23244d90` |

Published standings after this round: Gravy 1530.5305, SPAARK 1469.4695.
Both native replays were downloaded and parsed again with the upstream FlatBuffers
schema; their winners, rounds, and scores agree with the hosted results.
Both results report the pinned engine revision and the expected unchanged ZIP hashes:

- SPAARK: `7cc5fda375c7fcb5d97657b0bbdf7d6507d21475534323ebac0f92bf97b52e04`.
- Gravy: `03252061df0a9d8b9ccd926de66caca1a78fadae0962dd33a3dd336291d436f0`.

The league remains enabled and unpaused at the configured 288-minute cadence.
The next scheduled round was not waited for; the completed round verifies the
platform workflow, source staging, compilation, JVM play, replay storage, and
leaderboard settlement end to end.


## Seven archive bots (0.1.2)

Coworld `cow_af679116-681e-46c2-b3c7-0d2c73d6ff66` is canonical and passed all ten
hosted certification checks plus five hosted smoke episodes. The game accepts
per-seat `player_options` from `scheduler.entrant_preferences_field`, with each
league submission specifying its `package`. This keeps `submission.zip` unchanged.
Bundled engine source under `battlecode/` is ignored; only the pinned original
engine supplies those classes.

All seven original scaffold outputs were uploaded without changing their bytes.
Their Java entries were compared byte-for-byte to the pinned archive sources.
All selected players compile against the original engine. The Complex Merlin
exceeded the local x86 emulation compiler timeout but passed on native hardware.

| Archive | Selected package | Policy |
| --- | --- | --- |
| Gravy | `testplayer` | `Gravy (battlecode-2026-archive):v1` |
| Old-But-Gold | `basic51` | `Old-But-Gold (battlecode-2026-archive):v1` |
| Powerpuff-Girls | `Finals` | `Powerpuff-Girls (battlecode-2026-archive):v1` |
| ProofOfConcept | `result_408` | `ProofOfConcept (battlecode-2026-archive):v1` |
| SPAARK | `SPAARK` | `SPAARK (battlecode-2026-archive):v1` |
| The-Complex-Merlin | `TheComplexMerlin` | `The-Complex-Merlin (battlecode-2026-archive):v1` |
| TSPAARK | `Delta` | `TSPAARK (battlecode-2026-archive):v1` |

ProofOfConcept does not identify its final tournament entrypoint; `result_408` is
selected as the later-numbered exported result. The ZIP also retains its other
packages, so the selection can change without repacking or uploading new bytes.

Old But Gold has no scaffold; its unchanged source tree was placed in the pinned
official scaffold's `src/` directory. Gravy omits engine/client version files and
SPAARK omits the Gradle wrapper JAR; those scaffold support files were restored.
The archives' player code and their original `zipForSubmit` tasks were not edited.
The reproducible build procedure is `scripts/build_submissions.py`.

Every new player and policy is owned by `battlecode-2026`, using the supported
team ownership APIs. These are platform bot identities, separate from the user's
players and excluded from player rewards. The original two league memberships
were retired, retaining their history. Credentials were not changed.
Immutable identities, source commits, artifact hashes, submission IDs, and
membership IDs are in `players/uploaded_archives.json`.

Validation round: `round_0c474371-416b-4945-99d9-d45e74e68eac` (42 mirrored pairings).
The existing 288-minute cadence and $15/day budget remain in place.

All 42 matches completed without failures. Every result was checked against its
seat's selected package, immutable uploaded ZIP hash, and pinned engine revision,
with a replay present. `players/archive_validation.json` records this completed
validation of the original seven-bot roster, before the naming replacement below.

## Readable archive names

The seven bot-owned players and policies were recreated with the shared naming
format `<TeamName> (battlecode-2026-archive)` so truncated columns show the team
first. The original ZIP bytes and package preferences were reused. The seven
previous memberships were retired; `players/uploaded_archives.json` records the
replacement identities. The league remains enabled and unpaused, with the same
cadence and budget.

A new round, `round_bddb222c-73ff-4ca4-941e-5a43163fa814`, was triggered to publish
the replacement roster in the leaderboard.
