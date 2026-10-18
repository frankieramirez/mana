"""Render a saved check log as an SVG for the review page."""
import html
import pathlib
import sys

if len(sys.argv) != 3:
    print("usage: render_check.py <saved-output> <output.svg>", file=sys.stderr)
    sys.exit(2)
source = pathlib.Path(sys.argv[1])
if not source.is_file():
    print(f"render_check: no such log: {source}", file=sys.stderr)
    sys.exit(2)
lines = source.read_text(errors="replace").splitlines() or ["(empty log)"]
height = 20 * len(lines) + 20
rows = "".join(
    f'<text x="10" y="{20 * (i + 1)}" font-family="monospace" font-size="13">{html.escape(line)}</text>'
    for i, line in enumerate(lines)
)
pathlib.Path(sys.argv[2]).write_text(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="{height}">'
    f'<rect width="100%" height="100%" fill="#ffffff"/>{rows}</svg>\n'
)
print(f"rendered {sys.argv[2]}")
