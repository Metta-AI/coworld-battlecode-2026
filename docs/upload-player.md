# Upload your Battlecode 2026 player to Softmax

You can submit the Java player from your existing Battlecode 2026 scaffold without
rewriting it or building a policy container. Build the scaffold's **`zipForSubmit`**
task and upload its **`submission.zip`** unchanged. Softmax compiles your source
with Java 21 and runs it in the original Battlecode engine, including its sandbox
and per-robot bytecode budgets.

## 1. Build your submission

You need Git, Java 21, and your Battlecode 2026 player repository. From the directory
containing its `gradlew` and `build.gradle` files, run:

```sh
java -version  # Check that this is Java 21.
bash ./gradlew --no-daemon zipForSubmit
```

The result is `submission.zip` in that directory. The task is named `zipForSubmit`,
not `zipForUpload`. Keep the ZIP as generated; no `battlecode.json` or other
Softmax-specific file is required.

If you only have Java sources, start with the
[official Battlecode 2026 scaffold](https://github.com/battlecode/battlecode26-scaffold),
put your package and its dependencies under `src/`, and run the same task. For
example, `src/myplayer/RobotPlayer.java` should declare `package myplayer;`.
Include all Java sources your player imports. The ZIP may contain multiple player
packages; you will select the one to run when submitting to the league.

## 2. Install the CLI and sign in

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed, run
these commands from your player repository. They install the tools in a local
virtual environment:

```sh
uv venv --python 3.12 .venv-softmax
uv pip install --python .venv-softmax/bin/python 'coworld[auth]'
source .venv-softmax/bin/activate
softmax login
coworld player list
```

Use a current Coworld CLI whose `coworld upload-policy --help` includes `--file`.
These examples use a macOS/Linux shell. Keep the environment activated for the
remaining commands.

Select the player identity you want to appear on the leaderboard. Replace
`ply_YOUR_PLAYER_ID` with an ID printed by `coworld player list`:

```sh
coworld player use ply_YOUR_PLAYER_ID
```

If you need a new identity, create it first with `coworld player create "My Player"`,
then select the returned ID. Account player limits apply. Select your identity
**before uploading**: the uploaded policy version is bound to that player.

## 3. Upload the ZIP and enter the league

Choose your own policy name and upload the file:

```sh
coworld upload-policy --file submission.zip --name "My Battlecode Player"
```

The upload prints a policy name and version. Submit that exact version, replacing
`myplayer` with the Java package containing your intended `RobotPlayer` class:

```sh
coworld submit "My Battlecode Player:v1" \
  --league league_f4446dd0-3031-4726-9569-1b387accf46d \
  --preference package=myplayer
```

Use the version actually returned by the upload, which may be `v2` or later.
Package names are case-sensitive: a class declared as `package SPAARK;` needs
`--preference package=SPAARK`. This selects the entrypoint without changing the
ZIP. Only that entrypoint and the Java sources it references are compiled.

The league uses your submission's package preference for each match. Both players
run in the game's JVM container; you do not need a Dockerfile, container registry,
or access to Softmax's S3 storage.

## 4. Check your submission

```sh
coworld submissions \
  --league league_f4446dd0-3031-4726-9569-1b387accf46d \
  --player ply_YOUR_PLAYER_ID
coworld memberships --league league_f4446dd0-3031-4726-9569-1b387accf46d
```

Open the [Battlecode 2026 league](https://softmax.com/observatory/v2?detail=league:league_f4446dd0-3031-4726-9569-1b387accf46d)
to see your entry, matches, and replays. Uploading alone does not enter the league;
the `submit` command does. Placement and scheduled matches are asynchronous, so a
successful submission does not immediately produce a leaderboard score.

To update your player, rebuild `submission.zip`, upload under the same policy
name, and submit the new returned version with the same package preference.
When finished, `coworld player unset` returns the CLI to your main account identity.

## Compatibility

- Upload Java source. Precompiled classes, annotation processors, and uploaded
  Gradle scripts are not executed during a hosted match.
- The original scaffold ZIP layout (packages at the root) and ZIPs containing
  a `src/` directory are supported. Keep the original scaffold output when available.
- The ZIP limits are 32 MiB compressed, 128 MiB expanded, and 10,000 entries.
- The hosted engine supplies the official `battlecode` classes. Bundled
  `battlecode/` engine sources cannot replace them.
- Scala and Python players are not supported by this port.
