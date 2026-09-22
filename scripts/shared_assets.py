"""Render shared artifacts from one ownership manifest, using only the standard library."""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys


def safe_path(root, value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"invalid path: {value!r}")
    parts = PurePosixPath(value)
    if parts.is_absolute() or any(p in (".", "..") for p in value.split("/")):
        raise ValueError(f"path escapes or is not normalized: {value}")
    current = root
    for part in parts.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"symlink path is not allowed: {value}")
    return current


def fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise ValueError(f"invalid declaration: expected {required}, optional {optional}")


def render_agent(item, source):
    fields(item, ("source", "destination", "name", "description"), ("tools",))
    for key in ("name", "description", "tools"):
        value = item.get(key, "")
        if not isinstance(value, str) or "\n" in value or "\r" in value:
            raise ValueError(f"invalid agent {key}")
    if not re.fullmatch(r"[a-z][a-z0-9-]*", item["name"]):
        raise ValueError("invalid agent name")
    header = f"---\nname: {item['name']}\ndescription: {item['description']} Generated from {item['source']}, do not edit by hand.\n"
    if "tools" in item:
        header += f"tools: {item['tools']}\n"
    return (header + "---\n\n").encode() + source


def render_activation(original, block):
    begin, end = "<!-- BEGIN MANA PERSONA -->", "<!-- END MANA PERSONA -->"
    if block.count(begin) != 1 or block.count(end) != 1 or not block.startswith(begin) or not block.endswith(end):
        raise ValueError("invalid canonical persona activation block")
    text = original.decode()
    counts = text.count(begin), text.count(end)
    if counts not in ((0, 0), (1, 1)) or (counts == (1, 1) and text.index(begin) > text.index(end)):
        raise ValueError("malformed persona markers; repair before syncing")
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
    stripped = pattern.sub("", text)
    fm = re.match(r"\A---\r?\n.*?\r?\n---\r?\n", stripped, re.S)
    if not fm:
        raise ValueError("missing frontmatter")
    if counts == (1, 1):
        return pattern.sub(lambda _: block, text, count=1).encode()
    newline = "\r\n" if "\r\n" in stripped[:fm.end()] else "\n"
    return (stripped[:fm.end()] + newline + block + newline + stripped[fm.end():]).encode()


def plan(root, manifest, only=None):
    fields(manifest, ("version", "copies", "agents", "persona"))
    if manifest["version"] != 1 or not isinstance(manifest["copies"], list) or not isinstance(manifest["agents"], list):
        raise ValueError("unsupported manifest version or collections")
    updates, sources = {}, set()

    def read(value):
        path = safe_path(root, value)
        sources.add(path)
        return path.read_bytes()

    def add(value, data, mode=None):
        path = safe_path(root, value)
        if path in updates:
            raise ValueError(f"duplicate destination owner: {value}")
        updates[path] = (data, mode)

    if only in (None, "copies"):
        for item in manifest["copies"]:
            fields(item, ("source", "destinations"))
            if not isinstance(item["destinations"], list) or not item["destinations"]:
                raise ValueError("copy needs destinations")
            data = read(item["source"])
            mode = safe_path(root, item["source"]).stat().st_mode & 0o777
            for destination in item["destinations"]:
                add(destination, data, mode)
    if only in (None, "agents"):
        for item in manifest["agents"]:
            fields(item, ("source", "destination", "name", "description"), ("tools",))
            add(item["destination"], render_agent(item, read(item["source"])))
    if only in (None, "persona") and manifest["persona"] is not None:
        p = manifest["persona"]
        fields(p, ("voice", "session", "activation", "skill_root", "voice_destination", "entry_destination", "style_destination"))
        voice = read(p["voice"])
        session = read(p["session"]).strip()
        block = read(p["activation"]).decode().strip()
        header = b"---\nname: archmage\ndescription: Narrates as Archmage, an experienced mage working beside you\nkeep-coding-instructions: true\n---\n\n"
        add(p["style_destination"], header + session + b"\n\n" + voice)
        skill_root = safe_path(root, p["skill_root"])
        for directory in sorted(skill_root.iterdir()):
            if directory.is_symlink():
                raise ValueError(f"symlink skill: {directory}")
            if not directory.is_dir():
                continue
            base = directory.relative_to(root).as_posix()
            entry = base + "/" + p["entry_destination"]
            # Entrypoints are explicitly updated in place by the activation renderer.
            path = safe_path(root, entry)
            try:
                add(entry, render_activation(path.read_bytes(), block))
            except ValueError as exc:
                raise ValueError(f"{entry}: {exc}") from exc
            dest = base + "/" + p["voice_destination"]
            if dest != p["voice"]:
                add(dest, voice)
    overlap = sources & updates.keys()
    if overlap:
        raise ValueError(f"destination overwrites canonical source: {sorted(map(str, overlap))}")
    for path in updates:
        if path.exists() and not path.is_file():
            raise ValueError(f"destination is not a file: {path}")
        for parent in path.parents:
            if parent == root:
                break
            if parent.exists() and not parent.is_dir():
                raise ValueError(f"destination parent is not a directory: {parent}")
    return updates


def sync(root, manifest, check=False, only=None):
    updates = plan(root, manifest, only)
    stale = [(p, data, mode) for p, (data, mode) in updates.items()
             if not p.exists() or p.read_bytes() != data or (mode is not None and p.stat().st_mode & 0o777 != mode)]
    for path, data, mode in stale:
        if check:
            print(f"{path.relative_to(root)} is out of sync; run scripts/sync-assets.sh", file=sys.stderr)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if mode is not None:
                path.chmod(mode)
            print(f"wrote {path.relative_to(root)}")
    return int(check and bool(stale))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--only", choices=("agents", "persona", "copies"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    try:
        manifest = json.loads((root / "scripts/shared-assets.json").read_text())
        return sync(root, manifest, args.check, args.only)
    except (ValueError, OSError) as exc:
        print(f"shared assets: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
