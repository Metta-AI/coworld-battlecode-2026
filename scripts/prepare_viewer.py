"""Adapt only the upstream browser client's URL entrypoint and playback defaults."""

import sys
from pathlib import Path

root = Path(sys.argv[1])
app = root / "src/app.tsx"
app.write_text(
    """// Coworld's immutable viewer passes the replay URL in the fragment.
const replayURL = new URLSearchParams(location.hash.slice(1)).get('replay')
    || new URLSearchParams(location.search).get('replay');
if (replayURL) {
    const url = new URL(location.href);
    url.searchParams.set('gameSource', replayURL);
    history.replaceState(null, '', url);
}
"""
    + app.read_text()
)
sidebar = root / "src/components/sidebar/sidebar.tsx"
text = sidebar.read_text()
needle = "GameRunner.setMatch(loadedGame.matches[0])"
assert text.count(needle) == 1
sidebar.write_text(
    text.replace(needle, needle + "\n                GameRunner.setPaused(false)")
)
runner = root / "src/playback/GameRunner.ts"
text = runner.read_text()
needle = "if (this.match.currentRound.isEnd() && this.targetUPS > 0) {\n                this.setPaused(true)"
assert text.count(needle) == 1
runner.write_text(
    text.replace(
        needle,
        "if (this.match.currentRound.isEnd() && this.targetUPS > 0) {\n                this.jumpToStart()",
    )
)
