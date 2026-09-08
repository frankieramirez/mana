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
recommendation = None
work = []

if reconciled:
    doc = load_json(reconciled)
    passno = int(doc.get("pass", 1)) + 1
    lenses_meta = doc.get("lenses", [])
    dismissed = list(doc.get("dismissed", []))
    residual_risks = list(doc.get("residual_risks", []))
    coverage = doc.get("coverage", {}) if isinstance(doc.get("coverage"), dict) else {}
    recommendation = doc.get("recommendation") if isinstance(doc.get("recommendation"), str) else None
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
    "recommendation": recommendation,
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
COLOR = {100: "#8ff5ff", 75: "#e8b45a", 50: "#6b7089"}

WORDMARK = (
    '<svg class="mark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 688 184" role="img" aria-label="mana">'
    '<defs><linearGradient id="face" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#efffff"/>'
    '<stop offset=".24" stop-color="#efffff"/><stop offset=".245" stop-color="#8ff5ff"/><stop offset=".59" stop-color="#56d5fa"/>'
    '<stop offset=".595" stop-color="#8292ff"/><stop offset="1" stop-color="#7470f3"/></linearGradient>'
    '<pattern id="dither" width="8" height="8" patternUnits="userSpaceOnUse"><path d="M0 0h4v4H0zM4 4h4v4H4z" fill="#393fc2"/></pattern>'
    '<g id="letters" fill-rule="evenodd"><path d="M0 112V8L8 0H28L64 36L100 0H120L128 8V112H100V44L64 80L28 44V112Z"/>'
    '<path transform="translate(144)" d="M0 112V24L24 0H80L104 24V112H76V76H28V112ZM52 20L34 38L52 56L70 38Z"/>'
    '<path transform="translate(264)" d="M0 112V8L8 0H28L84 64V0H104L112 8V112H84L28 48V112Z"/>'
    '<path transform="translate(392)" d="M0 112V24L24 0H80L104 24V112H76V76H28V112ZM52 20L34 38L52 56L70 38Z"/></g>'
    '<clipPath id="letter-clip"><path d="M0 112V8L8 0H28L64 36L100 0H120L128 8V112H100V44L64 80L28 44V112Z"/>'
    '<path clip-rule="evenodd" transform="translate(144)" d="M0 112V24L24 0H80L104 24V112H76V76H28V112ZM52 20L34 38L52 56L70 38Z"/>'
    '<path transform="translate(264)" d="M0 112V8L8 0H28L84 64V0H104L112 8V112H84L28 48V112Z"/>'
    '<path clip-rule="evenodd" transform="translate(392)" d="M0 112V24L24 0H80L104 24V112H76V76H28V112ZM52 20L34 38L52 56L70 38Z"/></clipPath>'
    '<g id="crystal"><path d="M66 8L114 64V104L66 168L18 104V64Z" fill="#272c83" stroke="#272c83" stroke-width="3" stroke-linejoin="miter"/>'
    '<path d="M66 8L18 64L42 72Z" fill="#e5ffff"/><path d="M66 8L90 72L114 64Z" fill="#8af2ff"/><path d="M66 8L42 72H90Z" fill="#b5faff"/>'
    '<path d="M18 64V104L42 72Z" fill="#8af2ff"/><path d="M114 64V104L90 72Z" fill="#438ae9"/><path d="M42 72L66 128L90 72Z" fill="#5bcded"/>'
    '<path d="M18 104L66 168L42 72Z" fill="#666aef"/><path d="M114 104L66 168L90 72Z" fill="#5044c1"/><path d="M42 72L66 168L66 128Z" fill="#a4acff"/>'
    '<path d="M90 72L66 168L66 128Z" fill="#7774f7"/><path d="M66 44L78 76L66 100L54 76Z" fill="#f0ffff"/></g></defs>'
    '<use href="#crystal"/><g transform="translate(164 36)"><use href="#letters" transform="translate(8 8)" fill="#343491"/>'
    '<use href="#letters" stroke="#343491" stroke-width="3" fill="url(#face)"/><g clip-path="url(#letter-clip)">'
    '<path d="M0 28H496V36H0ZM0 66H496V82H0ZM0 96H496V108H0Z" fill="url(#dither)" opacity=".42"/><path d="M0 108H496V112H0Z" fill="#4142aa"/></g></g></svg>'
)

CSS = """
:root{color-scheme:dark;--bg:#0b0d17;--fg:#e4e7f5;--soft:#d3d7ec;--muted:#9ba1c6;--dim:#7b81a8;--line:#22264a;--row:#181b33;--card:#101323;--glass:#10132399;--tab:#0e1020;--hover:#171b33;--indigo:#8292ff;--indigo-line:#393fc2;--cyan:#8ff5ff;--amber:#e8b45a;--gray:#6b7089;--red:#c96b6b;--green:#6fd3a4;--sans:'IBM Plex Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;--mono:'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;--pixel:'Pixelify Sans','Press Start 2P',var(--mono)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 var(--sans);text-wrap:pretty}
a{color:var(--cyan);text-decoration:none}a:hover{color:#fff;text-decoration:underline}
.page{min-height:100vh;background:radial-gradient(60rem 28rem at 50% -8rem,rgba(57,63,194,.32),transparent 70%),var(--bg)}
main{max-width:66rem;margin:0 auto;padding:3rem 1.5rem 6rem}
.mark{height:44px;width:auto;display:block}
.kicker{font-family:var(--pixel);font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--indigo)}
h1{margin:0;font-size:2.4rem;line-height:1.1;font-weight:600;letter-spacing:-.02em;overflow-wrap:anywhere}
h2{margin:0 0 .9rem;font-family:var(--pixel);font-size:.8rem;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:var(--indigo)}
h3{margin:0;font-size:1.25rem;font-weight:600;line-height:1.3}
h4{margin:0;font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;color:var(--dim)}
h5{margin:0;font-size:.68rem;letter-spacing:.12em;text-transform:uppercase}
p{margin:0}
.top{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:1.5rem 2rem;padding-bottom:2rem;border-bottom:1px solid var(--line)}
.top .id{display:flex;flex-direction:column;gap:.9rem}
.lede{max-width:34rem;color:var(--muted)}
.stats{display:grid;grid-template-columns:repeat(3,auto);gap:1.5rem}
.stat{display:flex;flex-direction:column;gap:.2rem}
.stat b{font-family:var(--pixel);font-size:2.2rem;line-height:1;font-weight:500}
.stat span{font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;color:var(--dim)}
dl{margin:0;padding:0}
dt{font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;color:var(--dim)}
dd{margin:.15rem 0 0;overflow-wrap:anywhere}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(11rem,1fr));gap:1rem 1.5rem;margin-top:1.75rem}
.meta div{min-width:0}
.meta .wide{grid-column:1/-1}
.mono{font-family:var(--mono);font-size:.85rem}
.sec{margin-top:3rem}
.lenses{display:grid;grid-template-columns:repeat(auto-fit,minmax(13rem,1fr));gap:.75rem}
.lens{display:flex;align-items:center;justify-content:space-between;gap:.75rem;padding:.8rem 1rem;border:1px solid var(--line);border-radius:8px;background:var(--glass)}
.lens .n{display:flex;align-items:center;gap:.6rem;min-width:0;font-weight:500;font-size:.92rem}
.dot{width:8px;height:8px;border-radius:2px;flex:none}
.lens .s{font-family:var(--mono);font-size:.75rem;color:var(--dim);white-space:nowrap}
.rankhead{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:.75rem;margin-bottom:1rem}
.rankhead h2{margin:0}
.tabs{display:flex;gap:2px;padding:3px;border:1px solid var(--line);border-radius:8px;background:var(--tab)}
.tabs input{position:absolute;opacity:0;width:0;height:0}
.tabs label{font:inherit;font-size:.78rem;padding:.3rem .8rem;border-radius:6px;cursor:pointer;color:var(--muted)}
.tabs label:hover{color:#fff}
main:has(#f-all:checked) label[for=f-all],main:has(#f-100:checked) label[for=f-100],main:has(#f-75:checked) label[for=f-75]{background:var(--line);color:#fff}
main:has(#f-100:checked) [data-s="75"],main:has(#f-75:checked) [data-s="100"]{display:none}
.empty{display:none;padding:2rem;text-align:center;color:var(--dim);font-style:italic;border:1px dashed var(--line);border-radius:12px}
main:has(#f-100:checked):not(:has([data-s="100"])) .empty,main:has(#f-75:checked):not(:has([data-s="75"])) .empty,main:not(:has([data-s])) .empty{display:block}
ol.rank{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:2px}
ol.rank li{display:grid;grid-template-columns:2rem minmax(0,1fr) 7rem 3.5rem;align-items:center;gap:1rem;padding:.7rem 1rem;border-radius:6px;background:var(--glass)}
ol.rank li:hover{background:var(--hover)}
.num{font-family:var(--pixel);font-size:1rem;color:var(--dim)}
ol.rank a{color:var(--fg);font-weight:500;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar{display:flex;align-items:center;gap:.5rem}
.bar i{flex:1;height:4px;border-radius:2px;background:#1c2040;overflow:hidden;display:block}
.bar i b{display:block;height:100%}
.bar span{font-family:var(--mono);font-size:.72rem;width:1.6rem;text-align:right}
.sc{font-family:var(--mono);font-size:.75rem;color:var(--dim);text-align:right}
.cards{margin-top:3rem;display:flex;flex-direction:column;gap:1.25rem}
.card{border:1px solid var(--line);border-radius:12px;background:var(--card);overflow:hidden;scroll-margin-top:1rem}
.card .accent{height:2px}
.card .body{padding:1.5rem 1.75rem}
.card header{display:flex;align-items:flex-start;gap:1rem}
.card .big{font-family:var(--pixel);font-size:1.6rem;line-height:1.2;width:2rem;flex:none}
.card .ttl{display:flex;flex-direction:column;gap:.6rem;min-width:0}
.chips{display:flex;flex-wrap:wrap;gap:.4rem}
.chip{font-size:.72rem;padding:.15rem .6rem;border-radius:999px;border:1px solid var(--line);color:var(--muted);white-space:nowrap}
.chip.lens{border-color:var(--indigo-line);color:var(--indigo)}
.chip.score{cursor:help;font-family:var(--mono)}
.inner{display:grid;grid-template-columns:minmax(0,1fr);gap:1.4rem;margin-top:1.5rem;padding-left:3rem}
@media (max-width:40rem){.inner{padding-left:0}}
.inner section{display:flex;flex-direction:column;gap:.35rem}
.inner p{color:var(--soft)}
ul.ev{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:.3rem;font-family:var(--mono);font-size:.8rem}
ul.ev li{display:flex;flex-wrap:wrap;gap:.25rem 1rem;overflow-wrap:anywhere}
ul.ev .loc{color:var(--indigo)}
ul.ev code{color:var(--soft);background:var(--bg);padding:0 .35rem;border-radius:4px;font-family:inherit}
details{margin-top:.2rem}
summary{cursor:pointer;list-style:none;font-size:.78rem;color:var(--cyan);display:inline-flex;align-items:center;gap:.4rem}
summary::-webkit-details-marker{display:none}
summary:hover{color:#fff}
summary .tri{font-family:var(--pixel)}
details[open] summary .tri{transform:rotate(90deg)}
details ul.ev{margin-top:.3rem}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%}
table.tok{font-size:.82rem;font-family:var(--mono)}
table.tok th{text-align:left;padding:.35rem .6rem;border-bottom:1px solid var(--line);font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;color:var(--dim);font-weight:500;font-family:var(--sans)}
table.tok td{padding:.45rem .6rem;border-bottom:1px solid var(--row);vertical-align:top}
table.tok td.nw{white-space:nowrap}
table.tok .tk{color:var(--cyan)}
table.tok .at{color:var(--dim)}
.sw{display:inline-block;width:.85em;height:.85em;border-radius:3px;vertical-align:-.1em;margin-right:.45rem;border:1px solid var(--line)}
.inner section.ba,.ba{display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));gap:.75rem}
.ba div{display:flex;flex-direction:column;gap:.35rem}
.ba h5.b{color:var(--red)}.ba h5.a{color:var(--green)}
pre{margin:0;padding:.8rem 1rem;border-radius:8px;background:var(--bg);border:1px solid #2a1c2e;overflow-x:auto;font-family:var(--mono);font-size:.8rem;line-height:1.5;color:var(--soft)}
pre.after{border-color:#1a2e2b}
pre code{font-family:inherit}
.conv{font-size:.85rem;color:var(--dim)}
.conv code{font-family:var(--mono);color:var(--indigo)}
ul.wins{margin:0;padding:0;list-style:none;display:flex;flex-wrap:wrap;gap:.4rem}
ul.wins li{font-size:.82rem;padding:.2rem .7rem;border-radius:6px;background:#141a2e;color:#b9f0d5}
.card footer{padding:.6rem 1.75rem;border-top:1px solid var(--row);font-size:.75rem;color:var(--dim);font-family:var(--mono)}
.tbl{overflow-x:auto;border:1px solid var(--line);border-radius:10px}
table.plain{font-size:.88rem}
table.plain thead tr{background:var(--tab)}
table.plain th{text-align:left;padding:.55rem .9rem;font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;color:var(--dim);font-weight:500}
table.plain td{padding:.6rem .9rem;border-top:1px solid var(--row);vertical-align:top}
table.plain .r{text-align:right}
table.plain .m{font-family:var(--mono)}
table.plain .l{color:var(--muted);white-space:nowrap}
.trio{display:grid;grid-template-columns:repeat(auto-fit,minmax(18rem,1fr));gap:2.5rem 3rem;margin-top:3.5rem}
.trio .wide{grid-column:1/-1}
ul.list{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:.6rem;font-size:.9rem}
ul.list li{display:flex;flex-direction:column;gap:.15rem}
ul.list .why{color:var(--dim);font-size:.82rem}
ul.list .why code{font-family:var(--mono)}
ul.list .tag{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:var(--dim)}
.cov{display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));gap:.9rem 1.5rem;padding:1.1rem 1.25rem;border:1px solid var(--line);border-radius:10px;background:var(--glass);font-size:.88rem}
.cov code{font-family:var(--mono);font-size:.82rem}
.start{margin-top:3.5rem;border:1px solid var(--indigo-line);border-radius:12px;background:linear-gradient(180deg,rgba(57,63,194,.18),rgba(16,19,35,.6));overflow:hidden}
.start .body{padding:1.75rem 1.75rem 1.5rem;display:grid;grid-template-columns:minmax(0,1fr);gap:1.25rem}
.start h2{margin:0;color:var(--cyan)}
.start .pick{display:flex;flex-direction:column;gap:.6rem}
.start .pick a{color:#fff;font-size:1.35rem;font-weight:600;line-height:1.3;display:flex;align-items:baseline;gap:.75rem}
.start .pick a .big{font-family:var(--pixel);font-size:1.4rem;color:var(--cyan)}
.start .pick p{color:var(--soft);max-width:44rem}
.start dl{display:grid;grid-template-columns:repeat(auto-fit,minmax(10rem,1fr));gap:.9rem 1.5rem;padding:1rem 0 0;border-top:1px solid var(--line);font-size:.88rem}
.start .dimmed{color:var(--muted)}
.foot{margin-top:4rem;padding-top:1.5rem;border-top:1px solid var(--line);display:flex;flex-wrap:wrap;justify-content:space-between;gap:.5rem;font-size:.75rem;color:var(--dim);font-family:var(--mono)}
@media print{.page{background:#fff}body{color:#000}.card{break-inside:avoid}main{max-width:none}}
"""


def e(v):
    return html.escape("" if v is None else str(v), quote=True)


def is_color(value):
    low = (value or "").strip().lower()
    return low.startswith("#") or low.startswith(("rgb", "hsl", "oklch", "oklab", "lab(", "lch(", "color("))


def swatch(value):
    if not is_color(value):
        return ""
    return '<span class="sw" style="background:%s"></span>' % e(value.strip())


def rank_label(n):
    return "%02d" % n


def color_of(c):
    return COLOR.get(c["strength"], COLOR[50])


def instance_row(i):
    return '<li><span class="loc">%s:%s</span><code>%s</code></li>' % (e(i["file"]), e(i["line"]), e(i["quote"]))


def chip(text, cls=""):
    return '<span class="chip %s">%s</span>' % (e(cls), e(text))


def card(c):
    s = c.get("score", {})
    col = color_of(c)
    factors = "S %s x I %s x H %s x 2 / E %s" % (s.get("S"), s.get("I"), s.get("H"), s.get("E"))
    inst = c.get("instances", [])
    files = sorted({i["file"] for i in inst})
    hot = int(round(100 * (s.get("churn_share") or 0)))
    parts = ['<article class="card" id="c%d" data-s="%d">' % (c["rank"], c["strength"])]
    parts.append('<div class="accent" style="background:linear-gradient(90deg,%s,transparent 70%%)"></div><div class="body">' % col)
    chips = [chip(LENS_LABEL.get(l, l), "lens") for l in c.get("lenses", [c.get("lens")])]
    chips.append('<span class="chip" style="border-color:%s;color:%s">strength %d</span>' % (col, col, c["strength"]))
    chips.append(chip("%d instances" % len(inst)))
    chips.append(chip("effort %s" % EFFORT_LABEL.get(c.get("effort"), c.get("effort"))))
    chips.append(chip("hot path %d%%" % hot))
    chips.append('<span class="chip score" title="%s">score %s</span>' % (e(factors), e(s.get("total"))))
    parts.append('<header><span class="big" style="color:%s">%s</span><div class="ttl"><h3>%s</h3><div class="chips">%s</div></div></header>' % (
        col, rank_label(c["rank"]), e(c["title"]), "".join(chips)))
    parts.append('<div class="inner">')
    parts.append('<section><h4>Problem</h4><p>%s</p></section>' % e(c["problem"]))
    shown, rest = inst[:3], inst[3:]
    ev = '<ul class="ev">%s</ul>' % "".join(instance_row(i) for i in shown)
    if rest:
        ev += '<details><summary><span class="tri">&#9656;</span>%d more</summary><ul class="ev">%s</ul></details>' % (len(rest), "".join(instance_row(i) for i in rest))
    parts.append('<section><h4>Evidence</h4>%s</section>' % ev)
    tokens = c.get("tokens") or []
    if tokens:
        rows = []
        for t in tokens:
            rows.append('<tr><td class="nw">%s%s</td><td class="tk">%s</td><td class="nw">%s%s</td><td class="at">%s</td></tr>' % (
                swatch(t.get("found")), e(t.get("found")), e(t.get("name") or ""), swatch(t.get("value")), e(t.get("value") or ""), e(t.get("source") or "")))
        parts.append('<section><h4>Found versus token</h4><div class="scroll"><table class="tok"><thead><tr><th>Found</th><th>Token</th><th>Value</th><th>Defined at</th></tr></thead><tbody>%s</tbody></table></div></section>' % "".join(rows))
    before, after = c.get("before"), c.get("after")
    if before or after:
        cols = []
        if before:
            cols.append('<div><h5 class="b">Before</h5><pre><code>%s</code></pre></div>' % e(before["code"]))
        if after:
            cols.append('<div><h5 class="a">After</h5><pre class="after"><code>%s</code></pre></div>' % e(after["code"]))
        parts.append('<section class="ba">%s</section>' % "".join(cols))
    fix = '<section><h4>Fix</h4><p>%s</p>' % e(c["fix"])
    if c.get("convention_source"):
        fix += '<p class="conv">Already done right at <code>%s</code></p>' % e(c["convention_source"])
    parts.append(fix + "</section>")
    if c.get("wins"):
        parts.append('<section><h4>Wins</h4><ul class="wins">%s</ul></section>' % "".join("<li>%s</li>" % e(w) for w in c["wins"]))
    parts.append("</div></div>")
    foot = ["%d files" % len(files)]
    if c.get("corroborated"):
        foot.append("two lenses agree")
    foot.extend(c.get("gates") or [])
    parts.append('<footer>%s</footer></article>' % e(" · ".join(foot)))
    return "".join(parts)


def rank_row(c):
    col = color_of(c)
    return ('<li data-s="%d"><span class="num">%s</span><a href="#c%d">%s</a>'
            '<span class="bar"><i><b style="width:%d%%;background:%s"></b></i><span style="color:%s">%d</span></span>'
            '<span class="sc">%s</span></li>') % (
        c["strength"], rank_label(c["rank"]), c["rank"], e(c["title"]), c["strength"], col, col, c["strength"], e(c.get("score", {}).get("total")))


def plain_table(cands):
    rows = []
    for c in cands:
        rows.append('<tr><td class="num">%d</td><td>%s</td><td class="l">%s</td><td class="m" style="color:%s">%d</td><td class="m">%d</td><td>%s</td><td class="m r">%s</td></tr>' % (
            c["rank"], e(c["title"]), e(", ".join(LENS_LABEL.get(l, l) for l in c.get("lenses", []))), color_of(c), c["strength"],
            len(c.get("instances", [])), e(EFFORT_LABEL.get(c.get("effort"), c.get("effort"))), e(c.get("score", {}).get("total"))))
    return ('<div class="tbl"><table class="plain"><thead><tr><th>#</th><th>Candidate</th><th>Lens</th><th>Strength</th><th>Instances</th><th>Effort</th><th class="r">Score</th></tr></thead><tbody>%s</tbody></table></div>' % "".join(rows))


def dd(label, value, cls=""):
    return '<div><dt>%s</dt><dd class="%s">%s</dd></div>' % (e(label), e(cls), value)


cands = doc.get("candidates", [])
strong = [c for c in cands if c["strength"] >= 75]
weak = [c for c in cands if c["strength"] < 75]
cards = strong[:12]
more = strong[12:]
dismissed = doc.get("dismissed", [])
risks = [r for r in doc.get("residual_risks", []) if isinstance(r, dict)]
ds = profile.get("design_system", {}) or {}
hs = profile.get("hot_spots", {}) or {}
repo = meta.get("repo") or os.path.basename(str(profile.get("root") or "")) or "repository"
head = (meta.get("head") or profile.get("head") or "")[:12]
generated = doc.get("generated_at") or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
generated = generated.replace("T", " ").replace("Z", " UTC")

out = []
out.append('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
out.append('<title>Ultima audit: %s</title><style>%s</style></head><body><div class="page"><main>' % (e(repo), CSS))

out.append('<header class="top"><div class="id">%s<div class="kicker">Ultima · Frontend audit</div><h1>%s</h1>'
           '<p class="lede">%d candidates worth acting on, %d weaker, %d dismissed. Ranked by strength, then by score.</p></div>' % (
               WORDMARK, e(repo), len(strong), len(weak), len(dismissed)))
out.append('<div class="stats"><div class="stat"><b style="color:%s">%d</b><span>Act on</span></div><div class="stat"><b style="color:%s">%d</b><span>Weaker</span></div><div class="stat"><b style="color:%s">%d</b><span>Dismissed</span></div></div></header>' % (
    COLOR[100], len(strong), COLOR[75], len(weak), COLOR[50], len(dismissed)))

design = " · ".join((ds.get("libraries") or []) + (ds.get("dirs") or []) + (ds.get("files") or [])[:4]) or "none found"
meta_items = [
    dd("Repository", e(repo), "mono"), dd("Head", e(head), "mono"), dd("Scope", e(profile.get("scope", {}).get("path", ".")), "mono"),
    dd("Generated", e(generated), "mono"),
    dd("Framework", e(", ".join([x for x in [profile.get("framework")] + list(profile.get("meta") or []) if x]) or "unknown")),
    dd("Styling", e(", ".join(profile.get("styling") or []) or "unknown")),
    dd("Tokens parsed", e(ds.get("token_count", 0))),
    dd("Hot spots", e("%d files touched in %s days" % (hs.get("files_touched", 0), hs.get("since_days", "?")))),
]
out.append('<dl class="meta">%s<div class="wide"><dt>Design system</dt><dd class="mono" style="color:#b9bedb;font-size:.82rem">%s</dd></div></dl>' % ("".join(meta_items), e(design)))

lens_tiles = []
for l in doc.get("lenses", []):
    status = l.get("status", "?")
    ok = status == "ok"
    label = "ok · %d in" % l.get("candidates_in", 0) if ok else status
    dot = COLOR[100] if ok else "#c96b6b"
    lens_tiles.append('<div class="lens"><div class="n"><span class="dot" style="background:%s;box-shadow:0 0 8px %s"></span><span>%s</span></div><span class="s">%s</span></div>' % (
        dot, dot, e(LENS_LABEL.get(l.get("name"), l.get("name"))), e(label)))
if lens_tiles:
    out.append('<section class="sec"><h2>Lenses</h2><div class="lenses">%s</div></section>' % "".join(lens_tiles))

out.append('<section class="sec"><div class="rankhead"><h2>Ranked candidates</h2><div class="tabs">'
           '<input type="radio" name="f" id="f-all" checked><label for="f-all">All</label>'
           '<input type="radio" name="f" id="f-100"><label for="f-100">Strong</label>'
           '<input type="radio" name="f" id="f-75"><label for="f-75">Moderate</label></div></div>')
out.append('<ol class="rank">%s</ol></section>' % "".join(rank_row(c) for c in cards))
out.append('<section class="cards">%s<p class="empty">No candidates at this strength.</p></section>' % "".join(card(c) for c in cards))

if more:
    out.append('<section class="sec"><h2>More candidates</h2>%s</section>' % plain_table(more))
if weak:
    out.append('<section class="sec" style="margin-top:3.5rem"><h2>Weaker candidates</h2>%s</section>' % plain_table(weak))

dis = "".join('<li><span>%s</span><span class="why">%s · %s</span></li>' % (
    e(d.get("title")), e(LENS_LABEL.get(d.get("lens"), d.get("lens") or "")), e(d.get("reason"))) for d in dismissed)
risk = "".join('<li><span class="tag">%s</span><span>%s</span></li>' % (e(LENS_LABEL.get(r.get("lens"), r.get("lens"))), e(r.get("text"))) for r in risks)
cov_items = []
for lens, c in (doc.get("coverage", {}) or {}).items():
    if isinstance(c, dict):
        bits = []
        if c.get("files_read") is not None:
            bits.append("%s files read" % c.get("files_read"))
        skipped = c.get("dirs_skipped") or c.get("skipped")
        if skipped:
            bits.append("skipped <code>%s</code>" % e(", ".join(map(str, skipped))))
        for note in c.get("notes") or []:
            bits.append(e(note))
        cov_items.append(dd(LENS_LABEL.get(lens, lens), " · ".join(bits) or "no notes"))
missing = doc.get("counts", {}).get("lenses_missing") or []
if missing:
    cov_items.append(dd("No usable output", e(", ".join(missing)), "dimmed"))
docs_files = (profile.get("docs", {}) or {}).get("files") or []
adrs = (profile.get("docs", {}) or {}).get("adrs") or []
if docs_files or adrs:
    cov_items.append(dd("Decision docs", '<code>%s</code>' % e(" · ".join(docs_files + [a["path"] for a in adrs]))))
lint = profile.get("lint", {}) or {}
if lint.get("a11y") or lint.get("style"):
    cov_items.append(dd("Lint rules deferred to", '<code>%s</code>' % e(", ".join((lint.get("a11y") or []) + (lint.get("style") or [])))))
out.append('<div class="trio"><section><h2>Dismissed</h2>%s</section><section><h2>Residual risks</h2>%s</section>'
           '<section class="wide"><h2>Coverage</h2><dl class="cov">%s</dl></section></div>' % (
               '<ul class="list">%s</ul>' % dis if dis else '<p class="dimmed">Nothing dismissed.</p>',
               '<ul class="list">%s</ul>' % risk if risk else '<p class="dimmed">None recorded.</p>',
               "".join(cov_items) or dd("Notes", "none")))

if strong:
    first = strong[0]
    s1 = first.get("score", {})
    why = "Strength %d, %s effort, %d%% hot path" % (first["strength"], EFFORT_LABEL.get(first.get("effort"), first.get("effort")), int(round(100 * (s1.get("churn_share") or 0))))
    text = doc.get("recommendation")
    if not isinstance(text, str) or not text.strip():
        nxt = strong[1].get("score", {}).get("total") if len(strong) > 1 else None
        text = "Highest score%s, %d quoted instances across %d files, and a fix the candidate names." % (
            " (%s versus %s for the next)" % (s1.get("total"), nxt) if nxt is not None else " (%s)" % s1.get("total"),
            len(first.get("instances", [])), len({i["file"] for i in first.get("instances", [])}))
    items = [dd("Why first", e(why))]
    if first.get("wins"):
        items.append(dd("Unblocks", e(", ".join(first["wins"][:2]))))
    if len(strong) > 1:
        second = strong[1]
        items.append(dd("Then", '<a href="#c%d">%s %s</a>' % (second["rank"], rank_label(second["rank"]), e(second["title"]))))
    coldest = min(strong[1:], key=lambda c: (c.get("score", {}).get("churn_share") or 0, -c["rank"])) if len(strong) > 2 else None
    if coldest is not None and (coldest.get("score", {}).get("churn_share") or 0) == 0:
        items.append(dd("Skip for now", '<a href="#c%d">%s %s</a> · 0%% hot path, no active churn' % (coldest["rank"], rank_label(coldest["rank"]), e(coldest["title"])), "dimmed"))
    out.append('<section class="start"><div class="body"><div class="pick"><h2>Start here</h2><a href="#c%d"><span class="big">%s</span>%s</a><p>%s</p></div><dl>%s</dl></div></section>' % (
        first["rank"], rank_label(first["rank"]), e(first["title"]), e(text), "".join(items)))

out.append('<footer class="foot"><span>generated by ultima</span><span>head %s</span></footer></main></div></body></html>' % e(head))

text = "".join(out)
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
