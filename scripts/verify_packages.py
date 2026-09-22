"""Check isolated skill payloads and audited offline helper entrypoints."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from shared_assets import safe_path

ROOT = Path(__file__).resolve().parent.parent
BUNDLED = re.compile(r"(?<![\w/])(?:references|scripts|assets)/[\w./-]+")


def inspect_package(folder, contract):
    if set(contract) != {"required", "smoke", "project_links"} or not isinstance(contract["required"], list) or not isinstance(contract["smoke"], list):
        raise ValueError(f"{folder.name}: invalid package contract")
    required = contract["required"]
    if "SKILL.md" not in required or len(required) != len(set(required)):
        raise ValueError(f"{folder.name}: missing entrypoint or duplicate requirement")
    for item in required:
        if not safe_path(folder, item).is_file():
            raise ValueError(f"{folder.name}: missing bundled asset {item}")
    for path in folder.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"{folder.name}: symlink in package {path}")
        if not path.is_file() or path.suffix != ".md":
            continue
        text = path.read_text()
        for match in BUNDLED.finditer(text):
            value = match.group().rstrip(".")
            # Templates are checked through the explicit required inventory.
            if text[match.end():match.end()+1] in ("{", "<", "*", "$") or value.endswith("/"):
                continue
            if not safe_path(folder, value).exists():
                raise ValueError(f"{folder.name}: {path.name} references missing bundled asset {value}")
        for target in re.findall(r"\]\(([^\s)]+)\)", text):
            if re.match(r"[a-zA-Z][\w+.-]*:", target) or target.startswith("#"):
                continue
            if target in contract["project_links"].get(path.relative_to(folder).as_posix(), []):
                continue
            value = target.split("#", 1)[0]
            if "<" in value or "{" in value:
                continue
            # Mana uses skill-root references/ and scripts/ links in stage-loaded documents.
            candidate = (folder if value.startswith(("references/", "scripts/", "assets/")) else path.parent) / value
            try:
                candidate.resolve().relative_to(folder.resolve())
            except ValueError as exc:
                raise ValueError(f"{folder.name}: link escapes package: {target}") from exc
            if not candidate.exists():
                raise ValueError(f"{folder.name}: missing linked asset {target} in {path.name}")


def smoke_package(folder, contract, scratch):
    bindir = scratch / "bin"
    bindir.mkdir()
    # No ambient CLI, credential helper, Git config, or network client enters PATH.
    for command in ("bash", "python3", "sed", "tr", "expand", "fold", "mktemp", "rm", "head", "mv", "cat", "dirname", "basename", "date", "grep", "sort", "wc", "cut", "mkdir", "chmod", "env", "awk", "id"):
        source = shutil.which(command)
        if source:
            (bindir / command).symlink_to(source)
    denied_log = scratch / "denied.log"
    for command in ("gh", "git", "curl", "wget"):
        stub = bindir / command
        stub.write_text('#!/bin/bash\nprintf "%s\\n" "$0 $*" >> "$MANA_DENIED_LOG"\nexit 97\n')
        stub.chmod(0o755)
    home, cwd = scratch / "home", scratch / "unrelated"
    home.mkdir()
    cwd.mkdir()
    env = {"PATH": str(bindir), "HOME": str(home), "XDG_CONFIG_HOME": str(home), "TMPDIR": str(scratch), "LC_ALL": "C", "MANA_DENIED_LOG": str(denied_log)}
    for script in (folder / "scripts").glob("*"):
        subprocess.run([str(bindir / "bash"), "-n", str(script)], env=env, cwd=cwd, check=True, capture_output=True)
    conflict_git = bindir / "git"
    conflict_git.write_text('''#!/bin/bash
if [[ "${MANA_CONFLICT_FIXTURE:-}" == 1 ]]; then
  case "$*" in
    'rev-parse --git-dir') echo .git; exit 0 ;;
    'rev-parse --short HEAD') echo abcdef; exit 0 ;;
    'rev-parse --git-path '*) printf '.git/%s\\n' "$3"; exit 0 ;;
    'ls-files -u') exit 0 ;;
  esac
fi
printf '%s\\n' "$*" >> "$MANA_DENIED_LOG"
exit 97
''')
    for case in contract["smoke"]:
        # Only audited help entrypoints execute here. Behavioral scenarios have separate fixtures.
        is_conflict = case.get("script") == "scripts/conflict-state" and case.get("args") == []
        if set(case) != {"script", "args", "exit"} or (case["args"] != ["--help"] and not is_conflict) or case["exit"] not in (0, 2):
            raise ValueError(f"{folder.name}: unaudited smoke entrypoint")
        script = safe_path(folder, case["script"])
        if not script.is_file() or not case["script"].startswith("scripts/"):
            raise ValueError(f"{folder.name}: invalid smoke script")
        case_env = dict(env, MANA_CONFLICT_FIXTURE="1") if is_conflict else env
        result = subprocess.run([str(bindir / "bash"), str(script), *case["args"]], env=case_env, cwd=cwd, capture_output=True, text=True, timeout=15)
        if is_conflict and "phase=clear" not in result.stdout:
            raise ValueError("isolated conflict-state fixture failed")
        if result.returncode != case["exit"] or not (result.stdout + result.stderr).strip():
            raise ValueError(f"{folder.name}: {case['script']} smoke failed ({result.returncode}): {result.stderr}")
    renderer = folder / "scripts/text-frame.sh"
    if renderer.exists():
        output = scratch / "frame.svg"
        subprocess.run([str(bindir / "bash"), str(renderer), str(output)], input="observed <check>\n", env=env, cwd=cwd, text=True, check=True, capture_output=True)
        if "observed &lt;check&gt;" not in output.read_text():
            raise ValueError(f"{folder.name}: renderer output is incorrect")
    if denied_log.exists():
        raise ValueError(f"{folder.name}: smoke attempted external tool: {denied_log.read_text()}")


def verify(root=ROOT):
    manifest = json.loads((root / "scripts/package-contracts.json").read_text())
    if set(manifest) != {"version", "skills"} or manifest["version"] != 1:
        raise ValueError("invalid package contract manifest")
    skills = {p.name for p in (root / "skills").iterdir() if p.is_dir()}
    if skills != manifest["skills"].keys():
        raise ValueError("package inventory differs from published skill directories")
    for name, contract in manifest["skills"].items():
        source = root / "skills" / name
        inspect_package(source, contract)
        with tempfile.TemporaryDirectory(prefix="mana isolated ") as temp:
            scratch = Path(temp)
            folder = scratch / name
            shutil.copytree(source, folder)
            inspect_package(folder, contract)
            smoke_package(folder, contract, scratch)
    print(f"standalone packages: {len(skills)} checked (static references and offline smoke only)")


if __name__ == "__main__":
    try:
        verify()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"package verification: {exc}", file=sys.stderr)
        sys.exit(1)
