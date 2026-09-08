#!/usr/bin/env bash
# ultima.sh: the deterministic parts of a frontend audit.
#
#   orient [--path DIR] [--since DAYS] [--run-dir DIR] [--out FILE]
#       Profile the checkout: framework, styling approach, design-system source of truth,
#       token values, component inventory, hot spots from recent git history, decision
#       docs, and installed lint rules the lenses should defer to. Prints one JSON object
#       and writes it to RUN_DIR/profile.json when --run-dir is given. Exit 2 when no
#       frontend is detected under the scope.
#
#   merge RUN_DIR [--reconciled FILE] [--out FILE] [--roster a,b,c]
#       Pass 1: read every lens artifact in RUN_DIR (plus RUN_DIR/returns/<lens>.json when
#       the artifact is missing), validate each candidate, apply the mechanical gates in
#       order (instance dedupe, the three-instance gate, the design-system source gate, the
#       prior-decision dismissal), merge near-duplicates across lenses, promote corroborated
#       candidates once, score against the hot spots in profile.json, sort, and number.
#       Writes merged.json. Pass 2 (--reconciled): take the model's edited copy and restore
#       the gates, scores, numbering, and counts. --roster lists the dispatched lenses so a
#       missing artifact is reported.
#
#   render RUN_DIR [--in FILE] [--out FILE]
#       Write the self-contained HTML report from merged.json (or --in), profile.json, and
#       metadata.json. Inline CSS, no script tag, every field escaped. Prints the path.
#
# Exit 4 means python3 is missing. Everything here is python3 standard library inside
# bash; there is no jq, no node, no pip package.

set -euo pipefail

usage() {
  awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "${BASH_SOURCE[0]}"
}

die() {
  echo "ultima.sh: $*" >&2
  exit 1
}

need_python() {
  command -v python3 >/dev/null 2>&1 || { echo "ultima.sh: python3 not found" >&2; exit 4; }
}

cmd_orient() {
  need_python
  local path="." since="90" run_dir="" out=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --path) path="${2:-}"; shift 2 ;;
      --since) since="${2:-}"; shift 2 ;;
      --run-dir) run_dir="${2:-}"; shift 2 ;;
      --out) out="${2:-}"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "orient: unknown argument $1" ;;
    esac
  done
  [ -d "$path" ] || die "orient: path not found: $path"
  case "$since" in ''|*[!0-9]*) die "orient: --since takes a number of days" ;; esac
  local root
  root=$(git rev-parse --show-toplevel 2>/dev/null) || die "orient: not inside a git checkout"
  [ -n "$out" ] || { [ -z "$run_dir" ] || out="$run_dir/profile.json"; }
  ULTIMA_ROOT="$root" ULTIMA_PATH="$path" ULTIMA_SINCE="$since" ULTIMA_OUT="$out" \
    python3 - <<'PY'
import json, os, re, subprocess, sys
from collections import Counter

root = os.path.realpath(os.environ["ULTIMA_ROOT"])
scope_arg = os.environ["ULTIMA_PATH"]
since = int(os.environ["ULTIMA_SINCE"])
out_path = os.environ.get("ULTIMA_OUT") or ""

SKIP_DIRS = {"node_modules", ".git", "dist", "build", "out", ".next", ".nuxt", ".svelte-kit", ".output",
             "coverage", "vendor", "__generated__", "generated", ".turbo", ".cache", "storybook-static",
             ".angular", "target", ".venv", "venv"}
FRONTEND_EXT = (".tsx", ".jsx", ".vue", ".svelte", ".astro", ".css", ".scss", ".sass", ".less", ".ts", ".js", ".mjs", ".html")
COMPONENT_EXT = (".tsx", ".jsx", ".vue", ".svelte", ".astro")
FRAMEWORKS = [("react", "react"), ("preact", "preact"), ("vue", "vue"), ("svelte", "svelte"),
              ("@angular/core", "angular"), ("solid-js", "solid"), ("lit", "lit"), ("astro", "astro")]
META = [("next", "next"), ("nuxt", "nuxt"), ("@remix-run/react", "remix"), ("react-router", "react-router"),
        ("@sveltejs/kit", "sveltekit"), ("gatsby", "gatsby"), ("@tanstack/react-router", "tanstack-router"),
        ("expo", "expo"), ("react-native", "react-native")]
STYLING = [("tailwindcss", "tailwind"), ("@tailwindcss/vite", "tailwind"), ("@tailwindcss/postcss", "tailwind"),
           ("styled-components", "styled-components"), ("@emotion/react", "emotion"), ("@emotion/styled", "emotion"),
           ("@vanilla-extract/css", "vanilla-extract"), ("@stitches/react", "stitches"), ("@pandacss/dev", "panda"),
           ("styled-jsx", "styled-jsx"), ("sass", "sass"), ("sass-embedded", "sass"), ("less", "less"),
           ("unocss", "unocss"), ("@linaria/core", "linaria")]
LIBRARIES = ["@mui/material", "@mui/joy", "@chakra-ui/react", "@mantine/core", "antd", "@headlessui/react",
             "@headlessui/vue", "react-aria-components", "@react-aria/", "@ark-ui/", "@radix-ui/", "vuetify", "primevue",
             "primereact", "@nuxt/ui", "element-plus", "@angular/material", "@ionic/", "@shopify/polaris",
             "@fluentui/", "@carbon/", "@atlaskit/", "@adobe/react-spectrum", "flowbite", "daisyui", "@skeletonlabs/",
             "bits-ui", "@kobalte/core", "@ariakit/react", "@base-ui-components/"]
A11Y_LINT = ["eslint-plugin-jsx-a11y", "eslint-plugin-vuejs-accessibility", "@angular-eslint/template-parser",
             "eslint-plugin-svelte", "axe-core", "@axe-core/react", "jest-axe", "vitest-axe", "@axe-core/playwright",
             "eslint-plugin-lit-a11y"]
STYLE_LINT = ["eslint-plugin-tailwindcss", "stylelint", "prettier-plugin-tailwindcss", "eslint-plugin-better-tailwindcss"]
DESIGN_FILE_RE = re.compile(r"^(tailwind\.config\.[cm]?[jt]s|theme\.[cm]?[jt]sx?|theme\.json|theme\.css|tokens?\.[cm]?[jt]sx?|tokens?\.json|tokens?\.css|design-tokens?\.[a-z]+|.*\.tokens\.json|variables\.(css|scss)|_variables\.scss|globals\.css|global\.css|components\.json|uno\.config\.[cm]?[jt]s|panda\.config\.[cm]?[jt]s|stitches\.config\.[cm]?[jt]s|vanilla-extract\.config\.[cm]?[jt]s)$")
DESIGN_DIR_RE = re.compile(r"(^|/)(packages|libs|apps)/(ui|design-system|design|tokens|theme|components)$|(^|/)\.storybook$|(^|/)src/(design-system|tokens|theme)$")
TOKEN_FILE_RE = re.compile(r"(token|theme|variables|globals?|colors?|palette|typography|spacing)", re.IGNORECASE)
CSS_VAR_RE = re.compile(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;{}]+);")
PASCAL_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")


def rel(p):
    return os.path.relpath(p, root).replace(os.sep, "/")


def walk(base):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        yield dirpath, dirnames, filenames


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def detect_packages(base):
    found = []
    for dirpath, dirnames, filenames in walk(base):
        if "package.json" not in filenames:
            continue
        if dirpath.count(os.sep) - base.count(os.sep) > 4:
            continue
        data = read_json(os.path.join(dirpath, "package.json"))
        if not isinstance(data, dict):
            continue
        deps = {}
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            d = data.get(key)
            if isinstance(d, dict):
                deps.update({str(k): str(v) for k, v in d.items()})
        frameworks = [name for dep, name in FRAMEWORKS if dep in deps]
        metas = [name for dep, name in META if dep in deps]
        if "react-native" in metas or "expo" in metas:
            frameworks = frameworks or ["react"]
        styling = sorted({name for dep, name in STYLING if dep in deps})
        libraries = sorted({dep for dep in deps if any(dep == lib or (lib.endswith("/") and dep.startswith(lib)) for lib in LIBRARIES)})
        a11y = sorted(dep for dep in deps if dep in A11Y_LINT)
        style_lint = sorted(dep for dep in deps if dep in STYLE_LINT)
        found.append({
            "dir": rel(dirpath) if dirpath != root else ".",
            "name": data.get("name"),
            "frameworks": frameworks,
            "meta": metas,
            "styling_deps": styling,
            "libraries": libraries,
            "a11y_lint": a11y,
            "style_lint": style_lint,
            "workspaces": bool(data.get("workspaces")),
        })
    return found


def hot_spots(scope_rel):
    try:
        raw = subprocess.run(
            ["git", "log", "--since=%d.days" % since, "--name-only", "--pretty=format:", "--", scope_rel],
            cwd=root, capture_output=True, text=True, check=False).stdout
    except OSError:
        raw = ""
    counts = Counter()
    for line in raw.splitlines():
        line = line.strip()
        if not line or not line.lower().endswith(FRONTEND_EXT):
            continue
        parts = set(line.split("/"))
        if parts & SKIP_DIRS:
            continue
        if not os.path.exists(os.path.join(root, line)):
            continue
        counts[line] += 1
    top = [{"file": f, "commits": n} for f, n in counts.most_common(30)]
    return top, sum(counts.values()), len(counts)


def styling_from_files(scope_abs):
    seen = set()
    for dirpath, dirnames, filenames in walk(scope_abs):
        for f in filenames:
            low = f.lower()
            if low.endswith((".module.css", ".module.scss", ".module.sass", ".module.less")):
                seen.add("css-modules")
            elif low.endswith(".css.ts"):
                seen.add("vanilla-extract")
            elif low.endswith((".css", ".scss", ".sass", ".less")):
                seen.add("stylesheets")
        if len(seen) >= 3:
            break
    return sorted(seen)


def design_files(scope_abs):
    files, dirs = [], []
    for dirpath, dirnames, filenames in walk(scope_abs):
        r = rel(dirpath)
        if r != "." and DESIGN_DIR_RE.search(r):
            dirs.append(r)
        for f in filenames:
            if DESIGN_FILE_RE.match(f):
                files.append(rel(os.path.join(dirpath, f)))
    return sorted(set(files))[:40], sorted(set(dirs))[:20]


def parse_tokens(files):
    tokens = []
    for f in files:
        low = f.lower()
        full = os.path.join(root, f)
        try:
            text = open(full, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if low.endswith((".css", ".scss")):
            if not TOKEN_FILE_RE.search(os.path.basename(low)):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                for m in CSS_VAR_RE.finditer(line):
                    tokens.append({"name": m.group(1), "value": m.group(2).strip(), "source": "%s:%d" % (f, i)})
                    if len(tokens) >= 400:
                        return tokens
        elif low.endswith(".json") and ("token" in low or low.endswith("theme.json")):
            data = read_json(full)
            if not isinstance(data, dict):
                continue

            def flatten(node, prefix):
                if isinstance(node, dict):
                    if "value" in node or "$value" in node:
                        v = node.get("$value", node.get("value"))
                        tokens.append({"name": prefix, "value": str(v), "source": f})
                        return
                    for k, v in node.items():
                        if str(k).startswith("$"):
                            continue
                        flatten(v, (prefix + "." + str(k)) if prefix else str(k))
                elif isinstance(node, (str, int, float)) and prefix:
                    tokens.append({"name": prefix, "value": str(node), "source": f})

            flatten(data, "")
            if len(tokens) >= 400:
                return tokens[:400]
    return tokens


UI_DIRS = {"components", "component", "ui", "features", "views", "pages", "app", "layouts", "screens", "widgets", "routes"}


def inventory(scope_abs):
    paths, by_dir = [], Counter()
    for dirpath, dirnames, filenames in walk(scope_abs):
        in_ui_dir = bool(set(rel(dirpath).split("/")) & UI_DIRS)
        for f in filenames:
            stem, ext = os.path.splitext(f)
            if ext not in COMPONENT_EXT:
                continue
            if stem in ("index",) or ".test" in stem or ".spec" in stem or ".stories" in stem or stem.endswith(".d"):
                continue
            if not (PASCAL_RE.match(stem) or in_ui_dir or ext in (".vue", ".svelte", ".astro")):
                continue
            r = rel(os.path.join(dirpath, f))
            paths.append(r)
            by_dir[os.path.dirname(r) or "."] += 1
    paths.sort()
    return {"count": len(paths), "by_dir": [{"dir": d, "count": n} for d, n in by_dir.most_common(25)],
            "paths": paths[:300], "truncated": len(paths) > 300}


def docs():
    listed = []
    domain_line = None
    for name in ("CLAUDE.md", "AGENTS.md"):
        p = os.path.join(root, name)
        if not os.path.exists(p):
            continue
        listed.append(name)
        try:
            text = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        m = re.search(r"^Domain docs:\s*(.+)$", text, re.MULTILINE)
        if m and domain_line is None:
            domain_line = m.group(1).strip()
    for name in ("CONTEXT.md", "CONTEXT-MAP.md", "DESIGN.md", "STYLEGUIDE.md", "docs/DESIGN.md", "docs/design-system.md",
                 "docs/agents/issue-tracker.md", "docs/agents/triage-labels.md"):
        if os.path.exists(os.path.join(root, name)):
            listed.append(name)
    if domain_line:
        for token in re.findall(r"[A-Za-z0-9_./-]+\.md|[A-Za-z0-9_./-]+/", domain_line):
            token = token.strip("/") if token.endswith("/") else token
            if os.path.exists(os.path.join(root, token)) and token not in listed:
                listed.append(token)
    adrs = []
    adr_dir = os.path.join(root, "docs", "adr")
    if os.path.isdir(adr_dir):
        for f in sorted(os.listdir(adr_dir)):
            if not f.endswith(".md"):
                continue
            title = f
            try:
                for line in open(os.path.join(adr_dir, f), encoding="utf-8", errors="replace"):
                    if line.startswith("#"):
                        title = line.lstrip("#").strip()
                        break
            except OSError:
                pass
            adrs.append({"path": "docs/adr/" + f, "title": title})
    return {"domain_docs_line": domain_line, "files": listed, "adrs": adrs[:60]}


packages = detect_packages(root)
frontend_packages = [p for p in packages if p["frameworks"]]

if scope_arg not in (".", ""):
    scope_abs = os.path.realpath(os.path.join(root, scope_arg)) if not os.path.isabs(scope_arg) else os.path.realpath(scope_arg)
    if not scope_abs.startswith(root):
        print("ultima.sh orient: path is outside the checkout", file=sys.stderr)
        sys.exit(1)
    scope_rel = rel(scope_abs) if scope_abs != root else "."
    chosen = None
    for p in frontend_packages:
        if p["dir"] == scope_rel or scope_rel.startswith(p["dir"].rstrip("/") + "/") or p["dir"] == ".":
            if chosen is None or len(p["dir"]) > len(chosen["dir"]):
                chosen = p
    scope_reason = "path argument"
else:
    scope_abs, scope_rel, chosen = root, ".", None
    scope_reason = "whole checkout"
    if len(frontend_packages) == 1:
        chosen = frontend_packages[0]
        if chosen["dir"] != ".":
            scope_rel = chosen["dir"]
            scope_abs = os.path.join(root, scope_rel)
            scope_reason = "only frontend package"
    elif len(frontend_packages) > 1:
        top, _, _ = hot_spots(".")
        best, best_n = None, -1
        for p in frontend_packages:
            prefix = "" if p["dir"] == "." else p["dir"].rstrip("/") + "/"
            n = sum(h["commits"] for h in top if h["file"].startswith(prefix)) if prefix else 0
            if n > best_n:
                best, best_n = p, n
        chosen = best
        if chosen and chosen["dir"] != ".":
            scope_rel = chosen["dir"]
            scope_abs = os.path.join(root, scope_rel)
        scope_reason = "frontend package with the most recent commits; pass path: to choose another"

if chosen is None and frontend_packages:
    chosen = frontend_packages[0]

top, churn_total, churn_files = hot_spots(scope_rel)
styling = sorted(set((chosen["styling_deps"] if chosen else []) + styling_from_files(scope_abs)))
dfiles, ddirs = design_files(scope_abs)
if scope_rel != ".":
    root_files, root_dirs = design_files(root)
    dfiles = sorted(set(dfiles + [f for f in root_files if "/" not in f]))
    ddirs = sorted(set(ddirs + root_dirs))
tokens = parse_tokens(dfiles)
inv = inventory(scope_abs)
framework = chosen["frameworks"][0] if chosen and chosen["frameworks"] else None
lint = {"a11y": sorted({d for p in packages for d in p["a11y_lint"]}),
        "style": sorted({d for p in packages for d in p["style_lint"]})}

head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False).stdout.strip()
profile = {
    "root": root,
    "head": head or None,
    "scope": {"path": scope_rel, "reason": scope_reason},
    "framework": framework,
    "meta": chosen["meta"] if chosen else [],
    "styling": styling,
    "design_system": {
        "files": dfiles,
        "dirs": ddirs,
        "libraries": chosen["libraries"] if chosen else [],
        "tokens": tokens,
        "token_count": len(tokens),
    },
    "packages": [{"dir": p["dir"], "name": p["name"], "frameworks": p["frameworks"], "meta": p["meta"]} for p in packages],
    "frontend_packages": [p["dir"] for p in frontend_packages],
    "inventory": inv,
    "hot_spots": {"since_days": since, "top": top, "commit_touches": churn_total, "files_touched": churn_files},
    "docs": docs(),
    "lint": lint,
}
text = json.dumps(profile, indent=2)
if out_path:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
print(text)
if framework is None or (inv["count"] == 0 and not top):
    print("ultima.sh orient: no frontend detected under %s" % scope_rel, file=sys.stderr)
    sys.exit(2)
PY
}

cmd_merge() {
  need_python
  local run_dir="" reconciled="" out="" roster=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --reconciled) reconciled="${2:-}"; shift 2 ;;
      --out) out="${2:-}"; shift 2 ;;
      --roster) roster="${2:-}"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      -*) die "merge: unknown option $1" ;;
      *) [ -z "$run_dir" ] || die "merge: one run dir only"; run_dir="$1"; shift ;;
    esac
  done
  [ -n "$run_dir" ] && [ -d "$run_dir" ] || die "merge: run dir missing"
  [ -z "$reconciled" ] || [ -f "$reconciled" ] || die "merge: reconciled file missing: $reconciled"
  ULTIMA_RUN_DIR="$run_dir" ULTIMA_RECONCILED="$reconciled" ULTIMA_OUT="${out:-$run_dir/merged.json}" ULTIMA_ROSTER="$roster" \
    python3 - <<'PY'
import datetime, json, math, os, re, sys

run_dir = os.environ["ULTIMA_RUN_DIR"]
reconciled = os.environ.get("ULTIMA_RECONCILED") or ""
out_path = os.environ["ULTIMA_OUT"]
roster = [r for r in (os.environ.get("ULTIMA_ROSTER") or "").split(",") if r]

LENSES = ["design-system", "interaction-states", "accessibility", "component-architecture"]
LENS_ORDER = {name: i for i, name in enumerate(LENSES)}
STRENGTHS = (50, 75, 100)
EFFORT = {"S": 2, "M": 3, "L": 5}
STRENGTH_POINTS = {100: 3, 75: 2, 50: 1}
PROMOTE = {50: 75, 75: 100, 100: 100}
STOP = {"the", "a", "an", "of", "in", "on", "to", "for", "and", "or", "with", "without", "is", "are", "no", "not",
        "into", "from", "by", "at", "as", "use", "uses", "using", "instead"}


def warn(msg):
    print("ultima.sh merge: " + msg, file=sys.stderr)


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def words(title):
    return {w for w in re.findall(r"[a-z0-9]+", str(title).lower()) if w not in STOP and len(w) > 1}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def clean_instances(raw):
    seen, out = set(), []
    if not isinstance(raw, list):
        return out
    for it in raw:
        if not isinstance(it, dict):
            continue
        f = it.get("file")
        line = it.get("line")
        quote = it.get("quote")
        if not isinstance(f, str) or not f.strip() or not isinstance(quote, str) or not quote.strip():
            continue
        try:
            line = int(line)
        except (TypeError, ValueError):
            continue
        if line < 1:
            continue
        key = (os.path.normpath(f).replace(os.sep, "/"), line)
        if key in seen:
            continue
        seen.add(key)
        out.append({"file": key[0], "line": line, "quote": quote.strip()[:300]})
    return out


def clean_tokens(raw):
    out = []
    if not isinstance(raw, list):
        return out
    for t in raw:
        if not isinstance(t, dict):
            continue
        found = t.get("found")
        if not isinstance(found, str) or not found.strip():
            continue
        out.append({"found": found.strip()[:120],
                    "name": str(t.get("name") or "").strip()[:120] or None,
                    "value": str(t.get("value") or "").strip()[:120] or None,
                    "source": str(t.get("source") or "").strip()[:200] or None})
    return out


def clean_snippet(raw):
    if not isinstance(raw, dict):
        return None
    code = raw.get("code")
    if not isinstance(code, str) or not code.strip():
        return None
    return {"language": str(raw.get("language") or "text")[:30], "code": code.rstrip()[:2000]}


def normalize(c, lens):
    if not isinstance(c, dict):
        return None, "not an object"
    title = c.get("title")
    problem = c.get("problem")
    fix = c.get("fix")
    if not isinstance(title, str) or not title.strip():
        return None, "missing title"
    if not isinstance(problem, str) or not problem.strip():
        return None, "missing problem"
    if not isinstance(fix, str) or not fix.strip():
        return None, "missing fix"
    try:
        strength = int(c.get("strength"))
    except (TypeError, ValueError):
        return None, "strength is not one of 50, 75, 100"
    if strength not in STRENGTHS:
        strength = max((s for s in STRENGTHS if s <= strength), default=50)
    effort = str(c.get("effort") or "M").upper()[:1]
    if effort not in EFFORT:
        effort = "M"
    instances = clean_instances(c.get("instances"))
    if not instances:
        return None, "no quoted instance"
    wins = [str(w).strip() for w in c.get("wins", []) if isinstance(w, (str, int, float)) and str(w).strip()] if isinstance(c.get("wins"), list) else []
    lenses = c.get("lenses") if isinstance(c.get("lenses"), list) else []
    lenses = [l for l in lenses if l in LENS_ORDER] or [lens]
    prior = c.get("prior_decision")
    prior = prior.strip() if isinstance(prior, str) and prior.strip() else None
    conv = c.get("convention_source")
    conv = conv.strip() if isinstance(conv, str) and conv.strip() else None
    return {
        "title": " ".join(title.split())[:120],
        "lens": lenses[0],
        "lenses": sorted(set(lenses), key=lambda l: LENS_ORDER[l]),
        "problem": problem.strip(),
        "fix": fix.strip(),
        "wins": wins[:8],
        "effort": effort,
        "strength": strength,
        "instances": instances,
        "before": clean_snippet(c.get("before")),
        "after": clean_snippet(c.get("after")),
        "tokens": clean_tokens(c.get("tokens")),
        "convention_source": conv,
        "prior_decision": prior,
        "gates": [],
        "corroborated": False,
        "promoted": False,
    }, None


def apply_gates(c):
    if c["strength"] >= 75 and len(c["instances"]) < 3:
        c["gates"].append("demoted: fewer than 3 quoted instances")
        c["strength"] = 50
    if c["lens"] == "design-system" and c["strength"] >= 75:
        sourced = any(t.get("source") for t in c["tokens"]) or bool(c["convention_source"])
        if not sourced:
            c["gates"].append("demoted: fix names no token or component source")
            c["strength"] = 50
    return c


def same_pattern(a, b):
    if jaccard(words(a["title"]), words(b["title"])) >= 0.6:
        return True
    fa = {(i["file"], i["line"]) for i in a["instances"]}
    fb = {(i["file"], i["line"]) for i in b["instances"]}
    return jaccard(fa, fb) >= 0.5


def merge_into(keep, other):
    seen = {(i["file"], i["line"]) for i in keep["instances"]}
    for i in other["instances"]:
        if (i["file"], i["line"]) not in seen:
            keep["instances"].append(i)
            seen.add((i["file"], i["line"]))
    if other["strength"] > keep["strength"]:
        keep["strength"] = other["strength"]
        keep["fix"] = other["fix"]
    if len(other["problem"]) > len(keep["problem"]):
        keep["problem"] = other["problem"]
    for w in other["wins"]:
        if w not in keep["wins"]:
            keep["wins"].append(w)
    keep["wins"] = keep["wins"][:8]
    for t in other["tokens"]:
        if t not in keep["tokens"]:
            keep["tokens"].append(t)
    keep["before"] = keep["before"] or other["before"]
    keep["after"] = keep["after"] or other["after"]
    keep["convention_source"] = keep["convention_source"] or other["convention_source"]
    keep["prior_decision"] = keep["prior_decision"] or other["prior_decision"]
    keep["lenses"] = sorted(set(keep["lenses"]) | set(other["lenses"]), key=lambda l: LENS_ORDER[l])
    keep["gates"] = keep["gates"] + [g for g in other["gates"] if g not in keep["gates"]]
    if effort_rank(other["effort"]) > effort_rank(keep["effort"]):
        keep["effort"] = other["effort"]


def effort_rank(e):
    return EFFORT[e]


profile = {}
profile_path = os.path.join(run_dir, "profile.json")
if os.path.exists(profile_path):
    try:
        profile = load_json(profile_path)
    except ValueError:
        warn("profile.json is not valid JSON; scoring without hot spots")
hot = [h["file"] for h in (profile.get("hot_spots", {}).get("top") or []) if isinstance(h, dict) and h.get("file")]
hot_set = set(hot)
top5 = set(hot[:5])


def score(c):
    files = {i["file"] for i in c["instances"]}
    churn_share = (len(files & hot_set) / len(files)) if files else 0.0
    S = STRENGTH_POINTS[c["strength"]]
    I = min(4, 1 + int(math.floor(math.log2(len(c["instances"])))))
    H = 10 + int(round(10 * churn_share)) + (5 if files & top5 else 0)
    E = EFFORT[c["effort"]]
    c["score"] = {"S": S, "I": I, "H": H, "E": E, "churn_share": round(churn_share, 2),
                  "total": int(round(S * I * H * 2 / E))}
    return c


def sort_key(c):
    return (-c["strength"], -c["score"]["total"], -len(c["instances"]), LENS_ORDER[c["lens"]], c["title"].lower())


counts = {"malformed": 0, "demoted_instances": 0, "demoted_source": 0, "dismissed_prior_decision": 0,
          "dedup_merged": 0, "promoted": 0, "lenses_missing": []}
lenses_meta = []
dismissed = []
residual_risks = []
coverage = {}
work = []

if reconciled:
    doc = load_json(reconciled)
    passno = int(doc.get("pass", 1)) + 1
    lenses_meta = doc.get("lenses", [])
    dismissed = list(doc.get("dismissed", []))
    residual_risks = list(doc.get("residual_risks", []))
    coverage = doc.get("coverage", {}) if isinstance(doc.get("coverage"), dict) else {}
    prior = doc.get("counts", {})
    for k in counts:
        if k in prior:
            counts[k] = prior[k]
    for c in doc.get("candidates", []):
        n, why = normalize(c, c.get("lens") if isinstance(c, dict) and c.get("lens") in LENS_ORDER else LENSES[0])
        if n is None:
            counts["malformed"] += 1
            dismissed.append({"title": str(c.get("title", "?"))[:80] if isinstance(c, dict) else "?",
                              "lens": c.get("lens") if isinstance(c, dict) else None,
                              "reason": "malformed after reconciliation: " + why, "stage": "merge"})
            continue
        n["corroborated"] = bool(c.get("corroborated", False)) or len(n["lenses"]) > 1
        n["promoted"] = bool(c.get("promoted", False))
        work.append(n)
else:
    passno = 1
    names = roster or LENSES
    for name in names:
        if name not in LENS_ORDER:
            warn("unknown lens in roster: " + name)
            continue
        path = os.path.join(run_dir, name + ".json")
        hydration = "artifact"
        if not os.path.exists(path):
            path = os.path.join(run_dir, "returns", name + ".json")
            hydration = "return"
        if not os.path.exists(path):
            counts["lenses_missing"].append(name)
            lenses_meta.append({"name": name, "status": "missing", "candidates_in": 0})
            continue
        try:
            art = load_json(path)
        except ValueError:
            counts["lenses_missing"].append(name)
            lenses_meta.append({"name": name, "status": "unparseable", "candidates_in": 0})
            continue
        if not isinstance(art, dict):
            counts["lenses_missing"].append(name)
            lenses_meta.append({"name": name, "status": "unparseable", "candidates_in": 0})
            continue
        cands = art.get("candidates") if isinstance(art.get("candidates"), list) else []
        lenses_meta.append({"name": name, "status": "ok", "hydration": hydration, "candidates_in": len(cands)})
        for r in art.get("residual_risks", []) if isinstance(art.get("residual_risks"), list) else []:
            residual_risks.append({"lens": name, "text": str(r)})
        cov = art.get("coverage")
        if isinstance(cov, dict):
            coverage[name] = cov
        for c in cands:
            n, why = normalize(c, name)
            if n is None:
                counts["malformed"] += 1
                dismissed.append({"title": str(c.get("title", "?"))[:80] if isinstance(c, dict) else "?",
                                  "lens": name, "reason": "malformed: " + why, "stage": "merge"})
                continue
            work.append(n)

def gate_candidates(work):
    kept = []
    for c in work:
        if c["prior_decision"]:
            counts["dismissed_prior_decision"] += 1
            dismissed.append({"title": c["title"], "lens": c["lens"], "reason": "settled by " + c["prior_decision"],
                              "stage": "merge"})
            continue
        before = c["strength"]
        apply_gates(c)
        if before != c["strength"]:
            if any("instances" in g for g in c["gates"]):
                counts["demoted_instances"] += 1
            if any("source" in g for g in c["gates"]):
                counts["demoted_source"] += 1
        kept.append(c)
    return kept


def dedupe_across_lenses(kept):
    merged = []
    for c in sorted(kept, key=lambda x: (-x["strength"], -len(x["instances"]))):
        target = next((m for m in merged if same_pattern(m, c)), None)
        if target is None:
            merged.append(c)
            continue
        counts["dedup_merged"] += 1
        other_lenses = set(c["lenses"]) - set(target["lenses"])
        merge_into(target, c)
        if other_lenses:
            target["corroborated"] = True
    return merged


def promote_corroborated(merged):
    for c in merged:
        if c["corroborated"] and not c["promoted"] and len(c["instances"]) >= 3 and c["strength"] < 100:
            c["strength"] = PROMOTE[c["strength"]]
            c["promoted"] = True
            counts["promoted"] += 1
            c["gates"].append("promoted: two lenses agree")
    return merged


merged = promote_corroborated(dedupe_across_lenses(gate_candidates(work)))

for c in merged:
    score(c)
merged.sort(key=sort_key)
for i, c in enumerate(merged, 1):
    c["rank"] = i

strong = [c for c in merged if c["strength"] >= 75]
weak = [c for c in merged if c["strength"] < 75]
result = {
    "pass": passno,
    "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "lenses": lenses_meta,
    "counts": dict(counts, strong=len(strong), weak=len(weak), total=len(merged)),
    "candidates": merged,
    "dismissed": dismissed,
    "residual_risks": residual_risks,
    "coverage": coverage,
}
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=2)
    fh.write("\n")
print("merge pass %d: %d candidates (%d strong, %d weak), %d dismissed, lenses missing: %s -> %s" % (
    passno, len(merged), len(strong), len(weak), len(dismissed),
    ",".join(counts["lenses_missing"]) or "none", out_path))
PY
}

cmd_render() {
  need_python
  local run_dir="" inp="" out=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --in) inp="${2:-}"; shift 2 ;;
      --out) out="${2:-}"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      -*) die "render: unknown option $1" ;;
      *) [ -z "$run_dir" ] || die "render: one run dir only"; run_dir="$1"; shift ;;
    esac
  done
  [ -n "$run_dir" ] && [ -d "$run_dir" ] || die "render: run dir missing"
  inp="${inp:-$run_dir/merged.json}"
  [ -f "$inp" ] || die "render: merged file missing: $inp"
  ULTIMA_RUN_DIR="$run_dir" ULTIMA_IN="$inp" ULTIMA_OUT="${out:-$run_dir/report.html}" \
    python3 - <<'PY'
import datetime, html, json, os, sys

run_dir = os.environ["ULTIMA_RUN_DIR"]
doc = json.load(open(os.environ["ULTIMA_IN"], encoding="utf-8"))
out_path = os.environ["ULTIMA_OUT"]


def load(name):
    p = os.path.join(run_dir, name)
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except ValueError:
            return {}
    return {}


profile = load("profile.json")
meta = load("metadata.json")
LENS_LABEL = {"design-system": "Design system", "interaction-states": "Interaction states",
              "accessibility": "Accessibility", "component-architecture": "Component architecture"}
EFFORT_LABEL = {"S": "small", "M": "medium", "L": "large"}


def e(v):
    return html.escape("" if v is None else str(v), quote=True)


def chip(text, cls=""):
    return '<span class="chip %s">%s</span>' % (e(cls), e(text))


def swatch(value):
    v = (value or "").strip()
    low = v.lower()
    is_color = low.startswith("#") or low.startswith(("rgb", "hsl", "oklch", "oklab", "lab(", "lch(", "color("))
    if not is_color:
        return ""
    return '<span class="sw" style="background:%s"></span>' % e(v)


def instance_row(i):
    return '<li><code class="loc">%s:%s</code> <code class="q">%s</code></li>' % (e(i["file"]), e(i["line"]), e(i["quote"]))


def card(c):
    s = c.get("score", {})
    factors = "S %s x I %s x H %s x 2 / E %s" % (s.get("S"), s.get("I"), s.get("H"), s.get("E"))
    inst = c.get("instances", [])
    files = sorted({i["file"] for i in inst})
    parts = []
    parts.append('<article class="card" id="c%d">' % c["rank"])
    parts.append('<header><span class="rank">%d</span><h3>%s</h3></header>' % (c["rank"], e(c["title"])))
    chips = [chip(LENS_LABEL.get(l, l), "lens") for l in c.get("lenses", [c.get("lens")])]
    chips.append(chip("strength %s" % c["strength"], "s%s" % c["strength"]))
    chips.append(chip("%d instances" % len(inst)))
    chips.append(chip("effort %s" % EFFORT_LABEL.get(c.get("effort"), c.get("effort"))))
    if s.get("churn_share") is not None:
        chips.append(chip("hot path %d%%" % int(round(100 * s["churn_share"]))))
    chips.append('<span class="chip score" title="%s">score %s</span>' % (e(factors), e(s.get("total"))))
    parts.append('<div class="chips">%s</div>' % "".join(chips))
    parts.append('<section><h4>Problem</h4><p>%s</p></section>' % e(c["problem"]))
    shown = inst[:3]
    rest = inst[3:]
    ev = '<ul class="ev">%s</ul>' % "".join(instance_row(i) for i in shown)
    if rest:
        ev += '<details><summary>%d more</summary><ul class="ev">%s</ul></details>' % (len(rest), "".join(instance_row(i) for i in rest))
    parts.append('<section><h4>Evidence</h4>%s</section>' % ev)
    tokens = c.get("tokens") or []
    if tokens:
        rows = []
        for t in tokens:
            rows.append('<tr><td>%s<code>%s</code></td><td>%s</td><td>%s<code>%s</code></td><td class="loc">%s</td></tr>' % (
                swatch(t.get("found")), e(t.get("found")), e(t.get("name") or ""), swatch(t.get("value")), e(t.get("value") or ""), e(t.get("source") or "")))
        parts.append('<section><h4>Found versus token</h4><table class="tok"><thead><tr><th>Found</th><th>Token</th><th>Value</th><th>Defined at</th></tr></thead><tbody>%s</tbody></table></section>' % "".join(rows))
    before, after = c.get("before"), c.get("after")
    if before or after:
        cols = []
        for label, snip in (("Before", before), ("After", after)):
            if snip:
                cols.append('<div><h5>%s</h5><pre><code>%s</code></pre></div>' % (label, e(snip["code"])))
        parts.append('<section class="ba">%s</section>' % "".join(cols))
    fix = e(c["fix"])
    if c.get("convention_source"):
        fix += ' <span class="conv">Already done right at <code class="loc">%s</code>.</span>' % e(c["convention_source"])
    parts.append('<section><h4>Fix</h4><p>%s</p></section>' % fix)
    if c.get("wins"):
        parts.append('<section><h4>Wins</h4><ul>%s</ul></section>' % "".join("<li>%s</li>" % e(w) for w in c["wins"]))
    foot = ["%d files" % len(files)]
    if c.get("corroborated"):
        foot.append("two lenses agree")
    if c.get("gates"):
        foot.append("; ".join(c["gates"]))
    parts.append('<footer>%s</footer>' % e(" | ".join(foot)))
    parts.append("</article>")
    return "".join(parts)


def table(cands, caption):
    if not cands:
        return ""
    rows = []
    for c in cands:
        rows.append('<tr><td>%d</td><td><a href="#c%d">%s</a></td><td>%s</td><td>%s</td><td>%d</td><td>%s</td><td>%s</td></tr>' % (
            c["rank"], c["rank"], e(c["title"]), e(", ".join(LENS_LABEL.get(l, l) for l in c.get("lenses", []))),
            c["strength"], len(c.get("instances", [])), e(EFFORT_LABEL.get(c.get("effort"), c.get("effort"))), e(c.get("score", {}).get("total"))))
    return '<section><h2>%s</h2><div class="scroll"><table><thead><tr><th>#</th><th>Candidate</th><th>Lens</th><th>Strength</th><th>Instances</th><th>Effort</th><th>Score</th></tr></thead><tbody>%s</tbody></table></div></section>' % (e(caption), "".join(rows))


cands = doc.get("candidates", [])
strong = [c for c in cands if c["strength"] >= 75]
weak = [c for c in cands if c["strength"] < 75]
cards = strong[:12]
more = strong[12:]

ds = profile.get("design_system", {})
lens_lines = []
for l in doc.get("lenses", []):
    status = l.get("status", "?")
    lens_lines.append("%s: %s%s" % (LENS_LABEL.get(l.get("name"), l.get("name")), status,
                                    " (%d in)" % l.get("candidates_in", 0) if status == "ok" else ""))
summary = [
    ("Repository", meta.get("repo") or profile.get("root") or ""),
    ("Head", (meta.get("head") or profile.get("head") or "")[:12]),
    ("Scope", profile.get("scope", {}).get("path", ".")),
    ("Generated", doc.get("generated_at") or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
    ("Framework", ", ".join([x for x in [profile.get("framework")] + list(profile.get("meta") or []) if x]) or "unknown"),
    ("Styling", ", ".join(profile.get("styling") or []) or "unknown"),
    ("Design system", ", ".join((ds.get("libraries") or []) + (ds.get("dirs") or []) + (ds.get("files") or [])[:4]) or "none found"),
    ("Tokens parsed", str(ds.get("token_count", 0))),
    ("Hot spots", "%d files touched in %s days" % (profile.get("hot_spots", {}).get("files_touched", 0), profile.get("hot_spots", {}).get("since_days", "?"))),
    ("Lenses", "; ".join(lens_lines) or "none"),
]
summary_html = "".join("<div><dt>%s</dt><dd>%s</dd></div>" % (e(k), e(v)) for k, v in summary)

toc = "".join('<li><a href="#c%d">%s</a> %s</li>' % (c["rank"], e(c["title"]), chip("strength %s" % c["strength"], "s%s" % c["strength"])) for c in cards)

dismissed = doc.get("dismissed", [])
dis_html = "".join("<li><strong>%s</strong> (%s): %s</li>" % (e(d.get("title")), e(LENS_LABEL.get(d.get("lens"), d.get("lens") or "")), e(d.get("reason"))) for d in dismissed)

cov = doc.get("coverage", {}) or {}
cov_items = []
for lens, c in cov.items():
    if isinstance(c, dict):
        bits = ["%s: %s" % (k, ", ".join(map(str, v)) if isinstance(v, list) else v) for k, v in c.items()]
        cov_items.append("<li><strong>%s</strong>: %s</li>" % (e(LENS_LABEL.get(lens, lens)), e("; ".join(bits))))
missing = doc.get("counts", {}).get("lenses_missing") or []
if missing:
    cov_items.append("<li><strong>Lenses with no usable output</strong>: %s</li>" % e(", ".join(missing)))
docs_files = (profile.get("docs", {}) or {}).get("files") or []
adrs = (profile.get("docs", {}) or {}).get("adrs") or []
if docs_files or adrs:
    cov_items.append("<li><strong>Decision docs consulted</strong>: %s</li>" % e(", ".join(docs_files + [a["path"] for a in adrs])))
lint = profile.get("lint", {}) or {}
if lint.get("a11y") or lint.get("style"):
    cov_items.append("<li><strong>Lint rules deferred to</strong>: %s</li>" % e(", ".join((lint.get("a11y") or []) + (lint.get("style") or []))))
risks = doc.get("residual_risks", [])
risk_html = "".join("<li>%s: %s</li>" % (e(LENS_LABEL.get(r.get("lens"), r.get("lens"))), e(r.get("text"))) for r in risks if isinstance(r, dict))

CSS = """
:root{color-scheme:light dark;--bg:#fbfaf7;--fg:#1c1b19;--muted:#6b6862;--line:#e3dfd6;--card:#ffffff;--accent:#2f5d50;--warn:#a5641b;--weak:#7a7670;--code:#f1efe9;--sw:#d6d2c8}
@media (prefers-color-scheme:dark){:root{--bg:#161513;--fg:#ece8df;--muted:#a19c92;--line:#312e29;--card:#1f1d1a;--accent:#8fc4b0;--warn:#e0a45a;--weak:#8d8880;--code:#26231f;--sw:#3a3631}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
main{max-width:64rem;margin:0 auto;padding:2.5rem 1.25rem 5rem}
h1{font-size:1.7rem;margin:0 0 .25rem;letter-spacing:-.01em}
h2{font-size:1.15rem;margin:2.5rem 0 .75rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
h3{font-size:1.2rem;margin:0;font-weight:600}
h4{font-size:.75rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:1rem 0 .3rem}
h5{margin:.3rem 0;font-size:.8rem;color:var(--muted)}
p{margin:.3rem 0}
.lede{color:var(--muted);margin:0 0 1.5rem}
dl.sum{display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));gap:.6rem 1.5rem;margin:0;padding:1rem 1.25rem;border:1px solid var(--line);border-radius:10px;background:var(--card)}
dl.sum div{min-width:0}
dt{font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
dd{margin:0;overflow-wrap:anywhere}
ol.toc{padding-left:1.4rem}
ol.toc li{margin:.2rem 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:1.25rem 1.5rem;margin:1.25rem 0}
.card header{display:flex;align-items:baseline;gap:.75rem}
.rank{font-variant-numeric:tabular-nums;color:var(--muted);font-size:.9rem}
.chips{display:flex;flex-wrap:wrap;gap:.35rem;margin:.6rem 0 .2rem}
.chip{font-size:.72rem;padding:.1rem .55rem;border:1px solid var(--line);border-radius:999px;color:var(--muted);white-space:nowrap}
.chip.lens{color:var(--accent);border-color:var(--accent)}
.chip.s100{color:var(--accent);font-weight:600}
.chip.s75{color:var(--warn)}
.chip.s50{color:var(--weak)}
.chip.score{cursor:help}
ul.ev{list-style:none;padding:0;margin:0}
ul.ev li{margin:.25rem 0;overflow-wrap:anywhere}
code{font:.85em ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--code);padding:.05rem .3rem;border-radius:4px}
code.loc{color:var(--muted)}
pre{background:var(--code);padding:.75rem;border-radius:8px;overflow-x:auto;margin:0}
pre code{background:none;padding:0}
.ba{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:1rem}
@media (max-width:40rem){.ba{grid-template-columns:1fr}}
.sw{display:inline-block;width:.9em;height:.9em;border-radius:3px;border:1px solid var(--line);vertical-align:-.1em;margin-right:.35rem;background:var(--sw)}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{text-align:left;padding:.35rem .5rem;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.scroll{overflow-x:auto}
.conv{color:var(--muted)}
footer{margin-top:1rem;font-size:.78rem;color:var(--muted)}
details{margin:.4rem 0}
summary{cursor:pointer;color:var(--muted);font-size:.85rem}
.empty{color:var(--muted);font-style:italic}
@media print{body{background:#fff;color:#000}.card{break-inside:avoid;border-color:#bbb}main{max-width:none}}
"""

parts = []
parts.append("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">")
parts.append("<title>Frontend audit: %s</title><style>%s</style></head><body><main>" % (e(os.path.basename(str(meta.get("repo") or profile.get("root") or "repo"))), CSS))
parts.append("<h1>Frontend audit</h1><p class=\"lede\">%d candidates worth acting on, %d weaker ones, %d dismissed. Ranked by strength, then by score.</p>" % (len(strong), len(weak), len(dismissed)))
parts.append("<dl class=\"sum\">%s</dl>" % summary_html)
if cards:
    parts.append("<h2>Ranked</h2><ol class=\"toc\">%s</ol>" % toc)
    parts.append("<h2>Candidates</h2>")
    parts.extend(card(c) for c in cards)
else:
    parts.append("<h2>Candidates</h2><p class=\"empty\">No candidate cleared the evidence bar. The weaker table and Coverage below say what was seen.</p>")
parts.append(table(more, "More candidates"))
parts.append(table(weak, "Weaker candidates"))
parts.append("<h2>Dismissed</h2>%s" % ("<ul>%s</ul>" % dis_html if dis_html else "<p class=\"empty\">Nothing dismissed.</p>"))
if risk_html:
    parts.append("<h2>Residual risks</h2><ul>%s</ul>" % risk_html)
parts.append("<h2>Coverage</h2>%s" % ("<ul>%s</ul>" % "".join(cov_items) if cov_items else "<p class=\"empty\">No coverage notes.</p>"))
parts.append("</main></body></html>")

text = "".join(parts)
if "<script" in text.lower():
    print("ultima.sh render: refusing to write a report containing a script tag", file=sys.stderr)
    raise SystemExit(1)
os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
with open(out_path, "w", encoding="utf-8") as fh:
    fh.write(text)
print(out_path)
PY
}

case "${1:-}" in
  orient) shift; cmd_orient "$@" ;;
  merge) shift; cmd_merge "$@" ;;
  render) shift; cmd_render "$@" ;;
  -h|--help|"") usage; [ -n "${1:-}" ] && exit 0 || exit 1 ;;
  *) die "unknown subcommand $1" ;;
esac
