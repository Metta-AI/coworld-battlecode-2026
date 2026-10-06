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
    if (innerWidth < 800 && !url.searchParams.has('sidebarOpen')) {
        url.searchParams.set('sidebarOpen', 'false');
    }
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

# Keep the original controls, wrapping the timeline above the buttons on phones.
controls = root / "src/components/controls-bar/controls-bar.tsx"
text = controls.read_text()
needle = "flex absolute bottom-0 rounded-t-md z-10 pointer-events-none select-none"
assert text.count(needle) == 1
controls.write_text(text.replace(needle, "coworld-controls " + needle))
style = root / "style.css"
style.write_text(
    style.read_text()
    + """
@media (max-width: 799px) {
  .coworld-controls { max-width: calc(100vw - 64px); }
  .coworld-controls .opacity-0 { display: none; }
  .coworld-controls > div { flex-wrap: wrap; justify-content: center; max-width: 100%; }
}
"""
)

timeline = root / "src/components/controls-bar/controls-bar-timeline.tsx"
text = timeline.read_text()
for needle, replacement, count in [
    ("minWidth: TIMELINE_WIDTH", "width: 'min(350px, calc(100vw - 104px))'", 2),
    ("x / TIMELINE_WIDTH", "x / rect.width", 1),
    (
        "(marker.round / maxRound) * TIMELINE_WIDTH",
        "(marker.round / maxRound) * 100",
        1,
    ),
    ("left: `${position}px`", "left: `${position}%`", 1),
]:
    assert text.count(needle) == count
    text = text.replace(needle, replacement)
timeline.write_text(text.replace("const TIMELINE_WIDTH = 350\n", ""))
