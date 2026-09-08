#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import json, os, pathlib, subprocess, tempfile

script = pathlib.Path("skills/ultima/scripts/ultima.sh").resolve()


def run(*a, cwd=None, ok=True, env=None):
    p = subprocess.run(["bash", str(script), *a], cwd=cwd, text=True, capture_output=True, env=env)
    if (p.returncode == 0) != ok:
        raise AssertionError((a, p.returncode, p.stdout, p.stderr))
    return p


def git(repo, *a):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True, env=env)


with tempfile.TemporaryDirectory(prefix="ultima-") as td:
    repo = pathlib.Path(td) / "app"
    (repo / "src" / "components").mkdir(parents=True)
    (repo / "src" / "styles").mkdir(parents=True)
    (repo / "docs" / "adr").mkdir(parents=True)
    (repo / "node_modules" / "react").mkdir(parents=True)
    (repo / "node_modules" / "react" / "package.json").write_text('{"name":"react","dependencies":{"vue":"1"}}')
    (repo / "package.json").write_text(json.dumps({
        "name": "app",
        "dependencies": {"react": "^18", "next": "^14", "@radix-ui/react-dialog": "^1"},
        "devDependencies": {"tailwindcss": "^3", "eslint-plugin-jsx-a11y": "^6"},
    }))
    (repo / "tailwind.config.ts").write_text("export default {}\n")
    (repo / "src" / "styles" / "tokens.css").write_text(":root {\n  --color-primary: #2563eb;\n  --space-4: 1rem;\n}\n")
    (repo / "src" / "components" / "Button.tsx").write_text('export const Button = () => <button style={{color: "#2563eb"}}>ok</button>\n')
    (repo / "src" / "components" / "Card.tsx").write_text('export const Card = () => <div onClick={() => {}}>card</div>\n')
    (repo / "src" / "components" / "Card.test.tsx").write_text("test('x', () => {})\n")
    (repo / "CLAUDE.md").write_text("## Agent skills\n\nDomain docs: single-context: CONTEXT.md and docs/adr/\n")
    (repo / "CONTEXT.md").write_text("# Context\n")
    (repo / "docs" / "adr" / "0001-radix.md").write_text("# Use Radix primitives for overlays\n")
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "one")
    (repo / "src" / "components" / "Button.tsx").write_text('export const Button = () => <button style={{color: "#2563eb", padding: 16}}>ok</button>\n')
    git(repo, "commit", "-qam", "two")
    (repo / "src" / "components" / "Button.tsx").write_text('export const Button = () => <button style={{color: "#2563eb", padding: 17}}>ok</button>\n')
    git(repo, "commit", "-qam", "three")

    run_dir = pathlib.Path(td) / "run"
    run_dir.mkdir()
    (run_dir / "returns").mkdir()
    out = run("orient", "--since", "90", "--run-dir", str(run_dir), cwd=repo).stdout
    prof = json.loads(out)
    assert prof["framework"] == "react", prof["framework"]
    assert "next" in prof["meta"]
    assert "tailwind" in prof["styling"] and "stylesheets" in prof["styling"], prof["styling"]
    assert "tailwind.config.ts" in prof["design_system"]["files"], prof["design_system"]["files"]
    assert "src/styles/tokens.css" in prof["design_system"]["files"]
    assert any(t["name"] == "--color-primary" and t["value"] == "#2563eb" and t["source"] == "src/styles/tokens.css:2" for t in prof["design_system"]["tokens"]), prof["design_system"]["tokens"]
    assert "@radix-ui/react-dialog" in prof["design_system"]["libraries"]
    assert prof["inventory"]["count"] == 2, prof["inventory"]
    assert prof["hot_spots"]["top"][0]["file"] == "src/components/Button.tsx", prof["hot_spots"]
    assert prof["hot_spots"]["top"][0]["commits"] == 3
    assert prof["docs"]["domain_docs_line"] == "single-context: CONTEXT.md and docs/adr/"
    assert "CONTEXT.md" in prof["docs"]["files"] and prof["docs"]["adrs"][0]["title"] == "Use Radix primitives for overlays"
    assert prof["lint"]["a11y"] == ["eslint-plugin-jsx-a11y"]
    assert not any(p["dir"].startswith("node_modules") for p in prof["packages"])
    assert (run_dir / "profile.json").exists()

    (repo / "server").mkdir()
    (repo / "server" / "main.go").write_text("package main\n")
    p = run("orient", "--path", "server", cwd=repo, ok=False)
    assert p.returncode == 2, p.returncode

    inst = lambda f, n, q: {"file": f, "line": n, "quote": q}
    (run_dir / "design-system.json").write_text(json.dumps({
        "lens": "design-system",
        "candidates": [
            {"title": "Hard-coded primary color instead of --color-primary", "problem": "Buttons carry the hex literal.",
             "fix": "Use var(--color-primary).", "wins": ["one place to change"], "effort": "S", "strength": 100,
             "instances": [inst("src/components/Button.tsx", 1, 'color: "#2563eb"'), inst("src/components/Card.tsx", 1, "#2563eb"),
                           inst("src/components/Nav.tsx", 4, "#2563eb"), inst("src/components/Button.tsx", 1, "dup")],
             "tokens": [{"found": "#2563eb", "name": "--color-primary", "value": "#2563eb", "source": "src/styles/tokens.css:2"}],
             "before": {"language": "tsx", "code": "<script>alert(1)</script>"}, "after": {"language": "tsx", "code": "var(--color-primary)"}},
            {"title": "Ad hoc spacing values", "problem": "Two paddings.", "fix": "Use --space-4.", "strength": 75, "effort": "M",
             "instances": [inst("src/components/Button.tsx", 2, "padding: 17"), inst("src/components/Card.tsx", 3, "padding: 3")]},
            {"title": "Unsourced token claim", "problem": "p", "fix": "use the token", "strength": 75,
             "instances": [inst("a.tsx", 1, "x"), inst("b.tsx", 1, "y"), inst("c.tsx", 1, "z")]},
            {"title": "missing fix", "problem": "p", "strength": 50, "instances": [inst("a.tsx", 1, "x")]},
        ],
        "residual_risks": ["JS theme files were listed, not parsed"],
        "coverage": {"files_read": 3, "skipped": ["src/legacy"]},
    }))
    (run_dir / "returns" / "accessibility.json").write_text(json.dumps({
        "lens": "accessibility",
        "candidates": [
            {"title": "Primary color literal repeated in components", "problem": "Same literal.", "fix": "token", "strength": 75,
             "instances": [inst("src/components/Button.tsx", 1, "#2563eb"), inst("src/components/Card.tsx", 1, "#2563eb"), inst("src/components/Nav.tsx", 4, "#2563eb")]},
            {"title": "Overlays reimplement Radix dialog", "problem": "p", "fix": "f", "strength": 100,
             "instances": [inst("x.tsx", 1, "a"), inst("y.tsx", 1, "b"), inst("z.tsx", 1, "c")], "prior_decision": "docs/adr/0001-radix.md"},
        ],
        "residual_risks": [],
    }))
    p = run("merge", str(run_dir), "--roster", "design-system,accessibility,interaction-states")
    merged = json.loads((run_dir / "merged.json").read_text())
    counts = merged["counts"]
    assert counts["lenses_missing"] == ["interaction-states"], counts
    assert counts["malformed"] == 1, counts
    assert counts["dismissed_prior_decision"] == 1, counts
    assert counts["demoted_instances"] == 1 and counts["demoted_source"] == 1, counts
    assert counts["dedup_merged"] == 1 and counts["promoted"] == 0, counts
    top = merged["candidates"][0]
    assert top["rank"] == 1 and top["strength"] == 100 and top["corroborated"] and len(top["instances"]) == 3, top
    assert top["lenses"] == ["design-system", "accessibility"], top["lenses"]
    assert top["score"]["H"] == 10 + 7 + 5 and top["score"]["I"] == 2, top["score"]
    assert counts["strong"] == 1 and counts["weak"] == 2, counts
    titles = [d["title"] for d in merged["dismissed"]]
    assert "Overlays reimplement Radix dialog" in titles and "missing fix" in titles, titles
    assert {l["name"]: l["status"] for l in merged["lenses"]} == {"design-system": "ok", "accessibility": "ok", "interaction-states": "missing"}
    assert merged["coverage"]["design-system"]["skipped"] == ["src/legacy"]

    rec = dict(merged)
    rec["candidates"] = [c for c in merged["candidates"] if c["title"] != "Unsourced token claim"]
    rec["dismissed"] = merged["dismissed"] + [{"title": "Unsourced token claim", "lens": "design-system", "reason": "taste", "stage": "reconcile"}]
    for c in rec["candidates"]:
        if c["title"] == "Ad hoc spacing values":
            c["strength"] = 75
            c["instances"].append(inst("src/components/Nav.tsx", 9, "padding: 5"))
            c["convention_source"] = "src/styles/tokens.css:3"
    (run_dir / "reconciled.json").write_text(json.dumps(rec))
    run("merge", str(run_dir), "--reconciled", str(run_dir / "reconciled.json"))
    merged2 = json.loads((run_dir / "merged.json").read_text())
    assert merged2["pass"] == 2
    assert [c["title"] for c in merged2["candidates"]][:2] == ["Hard-coded primary color instead of --color-primary", "Ad hoc spacing values"], [c["title"] for c in merged2["candidates"]]
    assert merged2["candidates"][1]["strength"] == 75 and merged2["candidates"][1]["rank"] == 2
    assert merged2["counts"]["strong"] == 2 and len(merged2["dismissed"]) == 3, merged2["counts"]

    (run_dir / "metadata.json").write_text(json.dumps({"repo": "acme/app", "head": "abc123def456"}))
    out = run("render", str(run_dir)).stdout.strip()
    html = pathlib.Path(out).read_text()
    assert out == str(run_dir / "report.html"), (out, str(run_dir))
    assert "<script" not in html.lower(), "script tag leaked"
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "background:#2563eb" in html, "swatch missing"
    assert "src/styles/tokens.css:2" in html and "Already done right at" in html
    for needle in ("Dismissed", "Interaction states"):
        assert needle in html, needle
    assert "Weaker candidates" not in html, "weak table rendered with no weak candidates"
    assert "Use Radix primitives" not in html and "docs/adr/0001-radix.md" in html
    assert html.count("<article") == 2, html.count("<article")
    assert "eslint-plugin-jsx-a11y" in html

    empty = pathlib.Path(td) / "empty"
    empty.mkdir()
    run("merge", str(empty), "--roster", "design-system")
    run("render", str(empty))
    assert "No candidate cleared" in (empty / "report.html").read_text()

print("ultima fixture tests: ok")
PY
