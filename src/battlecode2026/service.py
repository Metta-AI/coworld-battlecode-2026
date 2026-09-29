"""Coworld game-hosted seats and artifact contract."""

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

from aiohttp import WSMsgType, web

from battlecode2026.runner import EpisodeError, run_episode


def file_path(uri: str) -> Path:
    parsed = urlsplit(uri)
    if parsed.scheme != "file" or parsed.netloc or not parsed.path.startswith("/"):
        raise EpisodeError("Coworld must stage absolute local file:// URIs")
    return Path(unquote(parsed.path))


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def seats_request(config: dict, document: dict) -> dict:
    if document.get("schema") != "coworld-player-seats/1":
        raise EpisodeError("Expected coworld-player-seats/1")
    seats = document.get("seats", [])
    if [s.get("slot") for s in seats] != [0, 1]:
        raise EpisodeError("Expected ordered seats 0 and 1")
    if (
        set(config) - {"map", "tokens", "player_options"}
        or len(config.get("tokens", [])) != 2
    ):
        raise EpisodeError("Expected a map and two runner-injected tokens")
    options = config.get("player_options", [{}, {}])
    if (
        not isinstance(options, list)
        or len(options) != 2
        or any(
            not isinstance(option, dict) or set(option) - {"package"}
            for option in options
        )
    ):
        raise EpisodeError("Expected one player_options object per seat")
    players = []
    for seat in seats:
        path = file_path(seat["file_uri"])
        if path.stat().st_size != seat["size_bytes"]:
            raise EpisodeError(
                "Staged policy size mismatch", "player_error", seat["slot"]
            )
        digest = seat["content_hash"]
        if not digest.startswith("sha256:"):
            raise EpisodeError("Expected a SHA-256 seat content hash")
        players.append(
            {
                "uri": seat["file_uri"],
                "sha256": digest.removeprefix("sha256:"),
                **options[seat["slot"]],
            }
        )
    return {
        "version": 1,
        "players": players,
        "game_config": {"map": config.get("map", "DefaultSmall")},
    }


def run_hosted(state: dict) -> None:
    document = json.loads(file_path(os.environ["COGAME_PLAYER_SEATS_URI"]).read_text())
    config = json.loads(file_path(os.environ["COGAME_CONFIG_URI"]).read_text())
    seats = document.get("seats", [])
    for seat in seats:
        write_atomic(file_path(seat["log_uri"]), b"")
    with tempfile.TemporaryDirectory(prefix="bc26-hosted-") as temporary:
        output = Path(temporary)
        failure = None
        try:
            request = seats_request(config, document)
            state["phase"] = "running"
            result = run_episode(
                request,
                output,
                Path(os.environ.get("BATTLECODE_HOME", "/opt/battlecode")),
            )
        except EpisodeError as error:
            if error.kind == "player_error" and error.slot is not None:
                failure = {"message": str(error), "failed_policy_index": error.slot}
                state.update(
                    phase="failed", message="Player compilation or packaging failed"
                )
            else:
                raise
        finally:
            for seat in seats:
                log = output / f"compile-{seat['slot']}.log"
                if log.exists():
                    write_atomic(file_path(seat["log_uri"]), log.read_bytes())
        if failure is not None:
            write_atomic(
                file_path(os.environ["COGAME_PLAYER_FAILURE_URI"]),
                json.dumps(failure).encode(),
            )
            return
        replay = file_path(os.environ["COGAME_SAVE_REPLAY_URI"])
        replay.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output / "replay.bc26", replay)
        state.update(phase="complete", result=result, replay_path=str(replay))
        write_atomic(
            file_path(os.environ["COGAME_RESULTS_URI"]), json.dumps(result).encode()
        )


def serve() -> None:
    state = {"phase": "starting"}
    viewer = Path(os.environ.get("BATTLECODE_VIEWER", "/opt/battlecode/viewer"))

    async def health(request):
        return web.json_response({"ok": True})

    async def status(request):
        return web.json_response({k: v for k, v in state.items() if k != "replay_path"})

    async def websocket(request):
        socket = web.WebSocketResponse(autoping=True)
        await socket.prepare(request)
        while not socket.closed:
            await socket.send_json(
                {k: v for k, v in state.items() if k != "replay_path"}
            )
            try:
                message = await socket.receive(timeout=1)
                if message.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                    break
            except asyncio.TimeoutError:
                pass
        return socket

    async def client(request):
        return web.Response(
            content_type="text/html",
            text="""<!doctype html><meta charset="utf-8">
<title>Battlecode 2026</title><style>body{background:#101820;color:#eee;font:18px system-ui;padding:3rem}a{color:#69d4cb}</style>
<h1>Battlecode 2026</h1><p id="status">Starting match…</p><p id="replay"></p>
<script>async function update(){const s=await(await fetch('/status')).json();
document.getElementById('status').textContent=s.phase==='complete'?'Match complete — winner: team '+(s.result.winner_slot===0?'A':'B')+', '+s.result.rounds+' rounds':s.phase;
if(s.phase==='complete')document.getElementById('replay').innerHTML='<a href="/viewer/index.html?gameSource=/replay.bc26">Watch in the Battlecode viewer</a>';}
update();setInterval(update,1000);</script>""",
        )

    async def replay(request):
        if "replay_path" not in state:
            raise web.HTTPNotFound()
        return web.FileResponse(state["replay_path"])

    async def startup(app):
        async def episode():
            try:
                await asyncio.to_thread(run_hosted, state)
            except Exception as error:
                state.update(phase="failed", message=type(error).__name__)
                # Infrastructure failures must terminate, rather than impersonating a
                # player failure or keeping the platform waiting until its deadline.
                print(f"Battlecode runtime failed: {type(error).__name__}", flush=True)
                os._exit(1)

        app["episode"] = asyncio.create_task(episode())

    app = web.Application()
    app.router.add_get("/healthz", health)
    app.router.add_get("/status", status)
    app.router.add_get("/global", websocket)
    app.router.add_get("/client/global", client)
    app.router.add_get("/replay.bc26", replay)
    app.router.add_static("/viewer/", viewer)
    app.on_startup.append(startup)
    web.run_app(
        app,
        host=os.environ.get("COGAME_HOST", "0.0.0.0"),
        port=int(os.environ.get("COGAME_PORT", "8080")),
        access_log=None,
    )
