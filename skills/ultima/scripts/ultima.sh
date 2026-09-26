#!/usr/bin/env bash
# ultima.sh: the deterministic parts of a project audit.
#
#   orient [--path DIR] [--category all|ux|architecture|data-reliability|security] [--since DAYS] [--run-dir DIR] [--out FILE]
#       Profile the checkout: framework, styling approach, design-system source of truth,
#       token values, component inventory, hot spots from recent git history, decision
#       docs, and installed lint rules the lenses should defer to. Prints one JSON object
#       and writes it to RUN_DIR/profile.json when --run-dir is given. Exit 2 when no
#       applicable project source is detected under the selected scope and categories.
#
#   merge RUN_DIR [--reconciled FILE] [--out FILE] [--roster a,b,c]
#       Pass 1: read every lens artifact in RUN_DIR (plus RUN_DIR/returns/<lens>.json when
#       the artifact is missing), validate each candidate, apply the mechanical gates in
#       order (instance dedupe, the three-instance gate, the design-system source gate, the
#       decision routing), merge matching causes and remedies across lenses, rank impact
#       separately from confidence, assign stable IDs, and number.
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
  local path="." since="90" run_dir="" out="" category="ux,architecture,data-reliability"
  while [ $# -gt 0 ]; do
    case "$1" in
      --path) path="${2:-}"; shift 2 ;;
      --since) since="${2:-}"; shift 2 ;;
      --run-dir) run_dir="${2:-}"; shift 2 ;;
      --out) out="${2:-}"; shift 2 ;;
      --category) category="${2:-}"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "orient: unknown argument $1" ;;
    esac
  done
  [ -d "$path" ] || die "orient: path not found: $path"
  case "$since" in ''|*[!0-9]*) die "orient: --since takes a number of days" ;; esac
  local root
  root=$(git rev-parse --show-toplevel 2>/dev/null) || die "orient: not inside a git checkout"
  [ -n "$out" ] || { [ -z "$run_dir" ] || out="$run_dir/profile.json"; }
  ULTIMA_ROOT="$root" ULTIMA_PATH="$path" ULTIMA_SINCE="$since" ULTIMA_OUT="$out" ULTIMA_CATEGORY="$category" \
    python3 - <<'PY'
import json, os, re, subprocess, sys
from collections import Counter

root = os.path.realpath(os.environ["ULTIMA_ROOT"])
scope_arg = os.environ["ULTIMA_PATH"]
since = int(os.environ["ULTIMA_SINCE"])
out_path = os.environ.get("ULTIMA_OUT") or ""
categories = os.environ["ULTIMA_CATEGORY"].split(",")
if any(c not in ("all", "ux", "architecture", "data-reliability", "security") for c in categories) or ("all" in categories and len(categories) > 1):
    sys.exit("ultima.sh orient: invalid category")
if categories == ["all"]:
    categories = ["ux", "architecture", "data-reliability", "security"]

SKIP_DIRS = {"node_modules", ".git", "dist", "build", "out", ".next", ".nuxt", ".svelte-kit", ".output",
             "coverage", "vendor", "__generated__", "generated", ".turbo", ".cache", "storybook-static",
             ".angular", "target", ".venv", "venv"}
FRONTEND_EXT = (".tsx", ".jsx", ".vue", ".svelte", ".astro", ".css", ".scss", ".sass", ".less", ".ts", ".js", ".mjs", ".html")
SOURCE_EXT = FRONTEND_EXT + (".py", ".go", ".rs", ".java", ".kt", ".cs", ".rb", ".php", ".ex", ".exs", ".swift", ".c", ".h", ".cpp", ".sh", ".sql")
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
        yield dirpath, dirnames, sorted(f for f in filenames if not os.path.islink(os.path.join(dirpath, f)))


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
            "dependencies": sorted(deps),
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
        if not line or not line.lower().endswith(SOURCE_EXT):
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
                 "ARCHITECTURE.md", "docs/architecture.md", "docs/agents/issue-tracker.md", "docs/agents/triage-labels.md"):
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


scope_abs = os.path.realpath(os.path.join(root, scope_arg)) if not os.path.isabs(scope_arg) else os.path.realpath(scope_arg)
if scope_abs != root and not scope_abs.startswith(root + os.sep):
    sys.exit("ultima.sh orient: path is outside the checkout")
scope_rel = rel(scope_abs) if scope_abs != root else "."
scope_reason = "whole checkout" if scope_rel == "." else "path argument"
packages = detect_packages(scope_abs)
frontend_packages = [p for p in packages if p["frameworks"]]
# An explicit subdirectory may inherit its containing package's framework.
if not frontend_packages and scope_rel != ".":
    frontend_packages = [p for p in detect_packages(root) if p["frameworks"] and
                         (p["dir"] == "." or scope_rel.startswith(p["dir"] + "/"))]
chosen = frontend_packages[0] if frontend_packages else None

MANIFESTS = {"package.json", "go.mod", "go.work", "Cargo.toml", "pyproject.toml", "requirements.txt",
             "Pipfile", "Gemfile", "composer.json", "pom.xml", "build.gradle", "build.gradle.kts",
             "mix.exs", "Package.swift", "CMakeLists.txt", "Makefile"}
source_files, manifests, entrypoints, data_files, deployment_files = [], [], [], [], []
for directory, _, filenames in walk(scope_abs):
    for filename in filenames:
        path = rel(os.path.join(directory, filename))
        if filename in MANIFESTS or filename.endswith((".csproj", ".sln")):
            manifests.append(path)
        if filename.lower().endswith(SOURCE_EXT):
            source_files.append(path)
        if re.search(r"(^|/)(main|server|app|index|worker|cli)\.[^.]+$|(^|/)(routes|controllers|handlers|cmd)/", path):
            entrypoints.append(path)
        if re.search(r"(^|/)(migrations?|models?|schemas?|repositories|stores?|queues?|jobs|db|database)(/|\.)|\.(sql|prisma)$", path, re.I):
            data_files.append(path)
        if filename.startswith(("Dockerfile", "docker-compose", "compose.")) or re.search(r"(^|/)(deploy|infra|terraform|k8s)/|\.tf$", path):
            deployment_files.append(path)
# Hidden CI configuration is listed explicitly; generated and dependency trees stay excluded.
workflow_dir = os.path.join(scope_abs, ".github", "workflows")
if os.path.isdir(workflow_dir):
    deployment_files.extend(rel(os.path.join(workflow_dir, f)) for f in sorted(os.listdir(workflow_dir))
                            if f.endswith((".yml", ".yaml")) and not os.path.islink(os.path.join(workflow_dir, f)))
components = [{"name": p["name"] or p["dir"], "path": p["dir"], "manifest":
               (p["dir"] + "/" if p["dir"] != "." else "") + "package.json"} for p in packages]
for manifest in manifests:
    if manifest.endswith("package.json"):
        continue
    directory = os.path.dirname(manifest) or "."
    if not any(c["path"] == directory for c in components):
        components.append({"name": directory, "path": directory, "manifest": manifest})
if not components and source_files:
    components.append({"name": os.path.basename(scope_abs), "path": scope_rel, "manifest": None})
by_name = {p["name"]: p for p in packages if p["name"]}
edges = [{"from": p["dir"], "to": by_name[d]["dir"], "source":
          (p["dir"] + "/" if p["dir"] != "." else "") + "package.json", "kind": "declared dependency"}
         for p in packages for d in p["dependencies"] if d in by_name]
map_lists = {"manifests": manifests, "entrypoints": entrypoints, "data_files": data_files,
             "deployment_files": deployment_files}
system_map = {k: v[:300] for k, v in map_lists.items()}
system_map.update({"components": components[:300], "dependency_edges": edges[:300],
                  "source_count": len(source_files), "source_files": source_files[:300],
                  "coverage": {"truncated": [k for k, v in dict(map_lists, components=components, dependency_edges=edges, source_files=source_files).items() if len(v) > 300],
                               "notes": ["Discovery seeds only; verify boundaries and trace important flows before dispatch.",
                                         "Dependency edges cover declared local JavaScript package dependencies only; runtime and other language edges require inspection."],
                               "excluded_dirs": sorted(SKIP_DIRS)}})
security_patterns = {
    "authentication": r"authenticat|verify_session|jwt|oauth|session|login",
    "authorization": r"authoriz|permission|tenant|ownership|policy|rbac",
    "untrusted_input": r"request|req\.|argv|stdin|upload|deserialize|subprocess|innerHTML",
    "sensitive_data": r"password|secret|token|credential|personal|invoice|cookie",
}
security_matches = {surface: [] for surface in security_patterns}
security_unreadable = []
if "security" in categories:
    for path in source_files:
        try:
            with open(os.path.join(root, path), encoding="utf-8", errors="replace") as source:
                content = source.read()
        except OSError:
            security_unreadable.append(path)
            continue
        for surface, pattern in security_patterns.items():
            if re.search(pattern, path + "\n" + content, re.I):
                security_matches[surface].append(path)
security_surfaces = {surface: {
    "status": ("discovered" if matches else "not-discovered") if "security" in categories else "not-examined",
    "files": matches[:300], "truncated": len(matches) > 300,
} for surface, matches in security_matches.items()}
security_surfaces["unreadable_files"] = security_unreadable
security_surfaces["external_controls"] = {"status": "unavailable",
    "notes": ["Deployment identity, gateway policies and secret-store controls require supplied evidence; no external systems were contacted."]}
has_frontend = any(p["frameworks"] for p in packages) or any(f.endswith(COMPONENT_EXT + (".html", ".css", ".scss")) for f in source_files)
category_lenses = {"ux": ["design-system", "interaction-states", "accessibility", "component-architecture"],
                   "architecture": ["system-architecture"], "data-reliability": ["data-integrity", "failure-recovery"]}
applicable = {"ux": has_frontend, "architecture": bool(source_files or manifests),
              "data-reliability": bool(source_files), "security": bool(source_files)}
category_lenses["security"] = (
    (["access-control"] if any(security_surfaces[k]["files"] for k in ("authentication", "authorization")) or entrypoints else []) +
    (["input-boundaries"] if security_surfaces["untrusted_input"]["files"] else []) +
    (["sensitive-data"] if security_surfaces["sensitive_data"]["files"] else []))
if applicable["security"] and not category_lenses["security"]:
    category_lenses["security"] = ["access-control"]
recommended = [lens for category in categories if applicable[category] for lens in category_lenses[category]]

top, churn_total, churn_files = hot_spots(scope_rel)
styling = sorted(set((chosen["styling_deps"] if chosen else []) + styling_from_files(scope_abs)))
dfiles, ddirs = design_files(scope_abs)
if scope_rel != ".":
    root_files, root_dirs = design_files(root)
    dfiles = sorted(set(dfiles + [f for f in root_files if "/" not in f]))
    ddirs = sorted(set(ddirs + root_dirs))
tokens = parse_tokens(dfiles)
inv = inventory(scope_abs)
framework = chosen["frameworks"][0] if chosen and chosen["frameworks"] else ("html" if has_frontend else None)
lint = {"a11y": sorted({d for p in packages for d in p["a11y_lint"]}),
        "style": sorted({d for p in packages for d in p["style_lint"]})}

head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False).stdout.strip()
profile = {
    "root": root,
    "head": head or None,
    "scope": {"path": scope_rel, "reason": scope_reason},
    "categories": categories,
    "category_applicability": applicable,
    "security_surfaces": security_surfaces,
    "recommended_lenses": recommended,
    "system_map": system_map,
    "framework": framework,
    "meta": chosen["meta"] if chosen else [],
    "styling": styling,
    "design_system": {
        "files": dfiles,
        "dirs": ddirs,
        "libraries": sorted({lib for p in frontend_packages for lib in p["libraries"]}),
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
if not recommended:
    print("ultima.sh orient: no applicable project source for selected categories under %s" % scope_rel, file=sys.stderr)
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
import datetime, hashlib, json, os, re, sys

run_dir = os.environ["ULTIMA_RUN_DIR"]
reconciled = os.environ.get("ULTIMA_RECONCILED") or ""
out_path = os.environ["ULTIMA_OUT"]
roster = [r for r in (os.environ.get("ULTIMA_ROSTER") or "").split(",") if r]

LENSES = ["design-system", "interaction-states", "accessibility", "component-architecture",
          "system-architecture", "data-integrity", "failure-recovery", "access-control", "input-boundaries", "sensitive-data"]
CATEGORY = {l: "ux" for l in LENSES[:4]}
CATEGORY.update({"system-architecture": "architecture", "data-integrity": "data-reliability", "failure-recovery": "data-reliability",
                 "access-control": "security", "input-boundaries": "security", "sensitive-data": "security"})
IMPACT = {"low": 1, "medium": 2, "high": 3, "critical": 4}
REACH = {"local": 1, "package": 2, "system": 3}
LENS_ORDER = {name: i for i, name in enumerate(LENSES)}
STRENGTHS = (50, 75, 100)
EFFORT = {"S": 2, "M": 3, "L": 5}


def warn(msg):
    print("ultima.sh merge: " + msg, file=sys.stderr)


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


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


def text_field(c, key):
    value = c.get(key)
    return value.strip() if isinstance(value, str) else ""


def clean_trace(raw):
    out = []
    if isinstance(raw, list):
        for step in raw:
            if not isinstance(step, dict) or step.get("role") not in ("source", "boundary", "consumer"):
                continue
            instances = clean_instances([step])
            if instances:
                out.append(dict(instances[0], role=step["role"]))
    return out


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
    trace = clean_trace(c.get("trace"))
    evidence_kind = c.get("evidence_kind", "pattern")
    if evidence_kind not in ("pattern", "trace"):
        return None, "unknown evidence kind"
    instances = clean_instances((c.get("instances") if isinstance(c.get("instances"), list) else []) + trace)
    if not instances:
        return None, "no quoted instance"
    wins = [str(w).strip() for w in c.get("wins", []) if isinstance(w, (str, int, float)) and str(w).strip()] if isinstance(c.get("wins"), list) else []
    lenses = c.get("lenses") if isinstance(c.get("lenses"), list) else []
    lenses = [l for l in lenses if l in LENS_ORDER] or [lens]
    prior = c.get("prior_decision")
    prior = prior.strip() if isinstance(prior, str) and prior.strip() else None
    conv = c.get("convention_source")
    conv = conv.strip() if isinstance(conv, str) and conv.strip() else None
    category = c.get("category", CATEGORY[lens])
    if category not in CATEGORY.values():
        return None, "unknown category"
    decision = c.get("decision_status", "accepted" if prior else "none")
    if decision not in ("none", "accepted", "violated", "revisit"):
        return None, "unknown decision status"
    action = c.get("action", "plan" if evidence_kind == "trace" or effort == "L" else "fix")
    if action not in ("fix", "plan", "decision-needed"):
        return None, "unknown action"
    if evidence_kind == "trace" or effort == "L" or category == "security" or any(CATEGORY[l] == "security" for l in lenses):
        action = "plan"
    if decision == "revisit":
        action = "decision-needed"
    cause, boundary = text_field(c, "root_cause"), text_field(c, "affected_boundary")
    identity = [cause or title.strip(), boundary, fix.strip(), evidence_kind, decision, prior]
    finding_id = "F-" + hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:12]
    if reconciled and re.fullmatch(r"F-[a-f0-9]{12}", str(c.get("id", ""))):
        finding_id = c["id"]
    extra = {k: text_field(c, k) for k in ("invariant", "invariant_source", "scenario", "verification",
             "decision_reason", "compatibility", "rollback", "runtime_evidence", "flow", "assessment")}
    return dict(extra, **{
        "id": finding_id,
        "category": category,
        "categories": sorted(set([category] + [CATEGORY[l] for l in lenses])),
        "evidence_kind": evidence_kind,
        "evidence_status": "runtime" if c.get("evidence_status") == "runtime" else "static",
        "trace": trace,
        "control_review": clean_instances(c.get("control_review")),
        "impact": c.get("impact") if c.get("impact") in IMPACT else "medium",
        "reach": c.get("reach") if c.get("reach") in REACH else "local",
        "root_cause": cause,
        "affected_boundary": boundary,
        "decision_status": decision,
        "action": action,
        "remediation": [x.strip() for x in c.get("remediation", []) if isinstance(x, str) and x.strip()] if isinstance(c.get("remediation"), list) else [],
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
    }), None


def source_matches(item):
    root = profile.get("root")
    if not root:
        return False
    path = os.path.realpath(os.path.join(root, item["file"]))
    scope = os.path.realpath(os.path.join(root, profile.get("scope", {}).get("path", ".")))
    if not path.startswith(scope + os.sep):
        return False
    try:
        with open(path, encoding="utf-8") as source:
            lines = source.read().splitlines()
        quoted = item["quote"].splitlines()
        actual = "\n".join(lines[item["line"] - 1:item["line"] - 1 + len(quoted)])
        parts = item["quote"].split("[REDACTED]")
        if not any(part.strip() for part in parts):
            return False
        return re.search(".*?".join(re.escape(part) for part in parts), actual) is not None
    except (OSError, UnicodeError):
        return False


def apply_gates(c):
    reasons = []
    if c["evidence_kind"] == "trace":
        locations = {(x["file"], x["line"]) for x in c["trace"]}
        roles = {x["role"] for x in c["trace"]}
        if len(locations) < 2 or roles != {"source", "boundary", "consumer"} or not all(c[k] for k in ("invariant", "invariant_source", "scenario", "verification")):
            reasons.append("incomplete trace evidence")
    elif len(c["instances"]) < 3:
        reasons.append("fewer than 3 quoted instances")
    if c["lens"] == "design-system" and not (any(t.get("source") for t in c["tokens"]) or c["convention_source"]):
        reasons.append("fix names no token or component source")
    if c["decision_status"] in ("accepted", "violated", "revisit") and not c["prior_decision"]:
        reasons.append("decision has no source document")
    if c["decision_status"] == "revisit" and not c["decision_reason"]:
        reasons.append("decision has no changed assumption or evidence")
    if c["evidence_status"] == "runtime" and not c["runtime_evidence"]:
        reasons.append("runtime claim has no evidence reference")
        c["evidence_status"] = "static"
    if "security" in c["categories"]:
        c["action"] = "decision-needed" if c["decision_status"] == "revisit" else "plan"
        if c["evidence_kind"] != "trace" or not c["flow"] or not c["control_review"]:
            reasons.append("security requires a connected trace and enclosing control review")
        if c["assessment"] != "demonstrated":
            reasons.append("security impact depends on an unresolved assumption")
        source = re.fullmatch(r"(.+):(\d+)", c["invariant_source"])
        if not source or not source_matches({"file": source[1], "line": int(source[2]), "quote": c["invariant"]}):
            reasons.append("security invariant does not match its source")
        if not all(source_matches(item) for item in c["trace"] + c["control_review"]):
            reasons.append("security evidence does not match in-scope source")
    required_plan = ("remediation", "compatibility", "rollback", "verification")
    c["plan_missing"] = [k for k in required_plan if not c[k]] if c["action"] == "plan" else []
    c["plan_status"] = "incomplete" if c["plan_missing"] else ("documented" if c["action"] == "plan" else "not-applicable")
    if reasons and c["strength"] >= 75:
        c["strength"] = 50
        c["gates"].extend("demoted: " + r for r in reasons)
    return c


def same_pattern(a, b):
    # Shared locations or similar titles alone do not establish a shared cause.
    if a["evidence_kind"] != b["evidence_kind"] or a["decision_status"] != b["decision_status"] or a["prior_decision"] != b["prior_decision"]:
        return False
    if a["root_cause"] and b["root_cause"] and a["affected_boundary"] and b["affected_boundary"]:
        return all(a[k].casefold() == b[k].casefold() for k in ("root_cause", "affected_boundary", "fix"))
    return a["title"].casefold() == b["title"].casefold() and a["fix"].casefold() == b["fix"].casefold()


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
    keep["categories"] = sorted(set(keep["categories"] + other["categories"]))
    keep["impact"] = max((keep["impact"], other["impact"]), key=IMPACT.get)
    keep["reach"] = max((keep["reach"], other["reach"]), key=REACH.get)
    if other["action"] == "plan" and keep["action"] == "fix":
        keep["action"] = "plan"
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


def score(c):
    files = {i["file"] for i in c["instances"]}
    churn_share = len(files & hot_set) / len(files) if files else 0.0
    # Independent dimensions remain visible. Churn is only the last tie-breaker.
    c["score"] = {"impact": IMPACT[c["impact"]], "reach": REACH[c["reach"]],
                  "confidence": c["strength"], "effort": EFFORT[c["effort"]],
                  "churn_share": round(churn_share, 2)}
    return c


def sort_key(c):
    return (-(c["strength"] >= 75), -IMPACT[c["impact"]], -REACH[c["reach"]],
            -c["strength"], EFFORT[c["effort"]], -c["score"]["churn_share"], c["id"])


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
    names = roster or profile.get("recommended_lenses") or LENSES
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
        art = None
        for candidate_path, source in ((path, hydration), (os.path.join(run_dir, "returns", name + ".json"), "return")):
            try:
                candidate_art = load_json(candidate_path)
            except (ValueError, OSError):
                continue
            if isinstance(candidate_art, dict) and candidate_art.get("lens") == name and isinstance(candidate_art.get("candidates"), list):
                art, hydration = candidate_art, source
                break
        if art is None:
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
                lenses_meta[-1]["status"] = "partial"
                dismissed.append({"title": str(c.get("title", "?"))[:80] if isinstance(c, dict) else "?",
                                  "lens": name, "reason": "malformed: " + why, "stage": "merge"})
                continue
            work.append(n)

def gate_candidates(work):
    kept = []
    for c in work:
        if c["prior_decision"] and c["decision_status"] == "accepted":
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


# Agreement records provenance; it never increases confidence.
merged = dedupe_across_lenses(gate_candidates(work))

if len({c["id"] for c in merged}) != len(merged):
    sys.exit("ultima.sh merge: duplicate finding IDs in reconciliation; preserve each original identity")
for c in merged:
    apply_gates(c)
    score(c)
merged.sort(key=sort_key)
for i, c in enumerate(merged, 1):
    c["rank"] = i

strong = [c for c in merged if c["strength"] >= 75]
weak = [c for c in merged if c["strength"] < 75]
result = {
    "schema_version": 2,
    "pass": passno,
    "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "lenses": lenses_meta,
    "counts": dict(counts, strong=len(strong), weak=len(weak), total=len(merged), decision_needed=sum(c["action"] == "decision-needed" for c in merged)),
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
import datetime, html, json, os, re, sys

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
              "accessibility": "Accessibility", "component-architecture": "Component architecture",
              "system-architecture": "System architecture", "data-integrity": "Data integrity", "failure-recovery": "Failure recovery",
              "access-control": "Access control", "input-boundaries": "Input boundaries", "sensitive-data": "Sensitive data"}
CATEGORY_LABEL = {"ux": "UX & accessibility", "architecture": "Architecture", "data-reliability": "Data & reliability", "security": "Security"}
CATEGORY_LENSES = {"ux": list(LENS_LABEL)[:4], "architecture": ["system-architecture"],
                   "data-reliability": ["data-integrity", "failure-recovery"],
                   "security": ["access-control", "input-boundaries", "sensitive-data"]}
EFFORT_LABEL = {"S": "small", "M": "medium", "L": "large"}
COLOR = {100: "#8ff5ff", 75: "#e8b45a", 50: "#a8acc4"}

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
.mark{height:44px;width:165px;display:block;align-self:flex-start}
.kicker{font-family:var(--pixel);font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--indigo)}
h1{margin:0;font-size:2.4rem;line-height:1.1;font-weight:600;letter-spacing:-.02em;overflow-wrap:anywhere}
h2{margin:0 0 .9rem;font-family:var(--pixel);font-size:.8rem;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:var(--indigo)}
h3{margin:0;font-size:1.25rem;font-weight:600;line-height:1.3}
h4{margin:0;font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;color:var(--dim)}
h5{margin:0;font-size:.68rem;letter-spacing:.12em;text-transform:uppercase}
p{margin:0}
.top{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:1.5rem 2rem;padding-bottom:2rem;border-bottom:1px solid var(--line)}
.top .id{display:flex;flex-direction:column;gap:.9rem}
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
.tabs{display:flex;flex-wrap:wrap;gap:2px;padding:3px;border:1px solid var(--line);border-radius:8px;background:var(--tab)}
.tabs input{position:absolute;width:1px;height:1px;clip-path:inset(50%);overflow:hidden}
.tabs legend{font-size:.8rem;color:var(--soft);padding:0 .4rem}
.tabs input:focus-visible+label{outline:2px solid var(--cyan);outline-offset:2px}
a:focus-visible,summary:focus-visible{outline:2px solid var(--cyan);outline-offset:4px}
.category-tabs{margin:2rem 0 1rem;padding:.5rem}
.category-tabs label{font-size:.95rem;padding:.65rem 1rem}
.system-map pre{white-space:pre-wrap;overflow-wrap:anywhere}
.card:target{display:block!important;outline:2px solid var(--cyan)}
.tabs label{font:inherit;font-size:.78rem;padding:.3rem .8rem;border-radius:6px;cursor:pointer;color:var(--muted)}
.tabs label:hover{color:#fff}
main:has(#f-all:checked) label[for=f-all],main:has(#f-100:checked) label[for=f-100],main:has(#f-75:checked) label[for=f-75],main:has(#f-50:checked) label[for=f-50]{background:var(--line);color:#fff}
main:has(#f-100:checked) [data-s]:not([data-s="100"]),main:has(#f-75:checked) [data-s]:not([data-s="75"]),main:has(#f-50:checked) [data-s]:not([data-s="50"]){display:none}
.empty{display:none;padding:2rem;text-align:center;color:var(--soft);border:1px dashed var(--line);border-radius:12px}
ol.rank{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:2px}
ol.rank li{display:grid;grid-template-columns:2rem minmax(0,1fr) 5rem 4rem;align-items:center;gap:1rem;padding:.7rem 1rem;border-radius:6px;background:var(--glass)}
ol.rank li:hover{background:var(--hover)}
.num{font-family:var(--pixel);font-size:1rem;color:var(--dim)}
ol.rank a{color:var(--fg);font-weight:500;min-width:0;overflow-wrap:anywhere}
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
@media(max-width:40rem){ol.rank li{grid-template-columns:2rem minmax(0,1fr);gap:.5rem}.bar,.sc{display:none}.card .body{padding:1.1rem}.category-tabs label{padding:.6rem}.card header{gap:.6rem}}
@media print{.page,body{background:#fff!important;color:#000!important}main{max-width:none}.tabs,.empty{display:none!important}[data-category],.overview-content,[data-s]{display:block!important}.card{break-inside:avoid;background:#fff!important}main *{color:#000!important;text-shadow:none!important;box-shadow:none!important}details>*{display:block!important}.card .accent{display:none}}

"""

for category in ("all", *CATEGORY_LABEL):
    selector = "main:has(#cat-%s:checked)" % category
    CSS += selector + " label[for=cat-%s]{background:var(--line);color:#fff}" % category
    if category != "all":
        CSS += selector + ' [data-category]:not([data-category~="%s"]){display:none}' % category
        CSS += selector + ' .overview-content{display:none}'
    category_match = '[data-category~="%s"]' % category if category != "all" else ""
    for strength in ("all", "100", "75", "50"):
        match = '[data-s="%s"]' % strength if strength != "all" else '[data-s]'
        CSS += selector + ':has(#f-%s:checked):not(:has(article%s%s)) .empty{display:block}' % (strength, category_match, match)



def e(v):
    return html.escape("" if v is None else str(v), quote=True)


COLOR_RE = re.compile(r"#(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})|(?:rgba?|hsla?|oklch|oklab|lab|lch|color)\([0-9a-z.,%/ -]*\)", re.IGNORECASE)


def is_color(value):
    return bool(COLOR_RE.fullmatch((value or "").strip()))


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
    inst = c.get("instances", [])
    files = sorted({i["file"] for i in inst})
    hot = int(round(100 * (s.get("churn_share") or 0)))
    parts = ['<article class="card" id="%s" data-s="%d" data-category="%s">' % (e(c["id"]), c["strength"], e(" ".join(c["categories"]))) ]
    parts.append('<div class="accent" style="background:linear-gradient(90deg,%s,transparent 70%%)"></div><div class="body">' % col)
    chips = [chip(LENS_LABEL.get(l, l), "lens") for l in c.get("lenses", [c.get("lens")])]
    chips.append('<span class="chip" style="border-color:%s;color:%s">confidence %d</span>' % (col, col, c["strength"]))
    chips.append(chip("%d instances" % len(inst)))
    chips.append(chip("effort %s" % EFFORT_LABEL.get(c.get("effort"), c.get("effort"))))
    chips.append(chip("%s impact" % c["impact"]))
    chips.append(chip("%s reach" % c["reach"]))
    chips.append(chip(c["action"].replace("-", " ")))
    chips.append(chip("source inspection" if c["evidence_status"] == "static" else "runtime evidence"))
    parts.append('<header><span class="big" style="color:%s">%s</span><div class="ttl"><h3>%s</h3><div class="chips">%s</div></div></header>' % (
        col, rank_label(c["rank"]), e(c["title"]), "".join(chips)))
    parts.append('<div class="inner">')
    parts.append('<section><h4>Problem</h4><p>%s</p></section>' % e(c["problem"]))
    if "security" in c["categories"]:
        parts.append('<p><strong>Assessment:</strong> %s</p><p>%s</p>' % (e(c.get("assessment")), e(c.get("flow"))))
        parts.append('<details><summary>Enclosing controls inspected</summary><ul class="instances">%s</ul></details>' %
                     "".join(instance_row(i) for i in c.get("control_review", [])))
    if c["evidence_kind"] == "trace":
        parts.append('<section><h4>Traced flow</h4><ol class="ev">%s</ol></section>' % "".join(
            '<li><strong>%s</strong> <span class="loc">%s:%s</span> <code>%s</code></li>' %
            (e(t["role"]), e(t["file"]), e(t["line"]), e(t["quote"])) for t in c["trace"]))
        parts.append('<section><h4>Invariant</h4><p>%s</p><p class="conv">Source: %s</p></section>' % (e(c["invariant"]), e(c["invariant_source"])))
        parts.append('<section><h4>Failure scenario</h4><p>%s</p></section>' % e(c["scenario"]))
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
    for key, label in (("verification", "Verification"), ("compatibility", "Compatibility"), ("rollback", "Rollback"),
                       ("decision_reason", "Decision to review"), ("runtime_evidence", "Executed evidence")):
        if c.get(key):
            parts.append('<section><h4>%s</h4><p>%s</p></section>' % (label, e(c[key])))
    if c.get("prior_decision"):
        parts.append('<section><h4>Documented decision</h4><p>%s: %s</p></section>' % (e(c["decision_status"]), e(c["prior_decision"])))
    if c.get("plan_missing"):
        parts.append('<section><h4>Planning needed</h4><p>Before implementation, establish: %s. This finding needs further planning.</p></section>' % e(', '.join(c["plan_missing"])))
    if c.get("remediation"):
        parts.append('<section><h4>Migration steps</h4><ol>%s</ol></section>' % "".join('<li>%s</li>' % e(x) for x in c["remediation"]))
    if c.get("wins"):
        parts.append('<section><h4>Wins</h4><ul class="wins">%s</ul></section>' % "".join("<li>%s</li>" % e(w) for w in c["wins"]))
    parts.append("</div></div>")
    foot = [c["id"], "%d files" % len(files), "%d%% of evidence files changed recently" % hot]
    if c.get("corroborated"):
        foot.append("two lenses agree")
    foot.extend(c.get("gates") or [])
    parts.append('<footer>%s</footer></article>' % e(" · ".join(foot)))
    return "".join(parts)


def rank_row(c):
    return ('<li data-s="%d" data-category="%s"><span class="num">%s</span><a href="#%s">%s</a>'
            '<span class="bar">%s</span><span class="sc" aria-label="confidence %d">%d</span></li>') % (
        c["strength"], e(" ".join(c["categories"])), rank_label(c["rank"]), e(c["id"]), e(c["title"]), e(c["impact"]), c["strength"], c["strength"])


def dd(label, value, cls=""):
    return '<div><dt>%s</dt><dd class="%s">%s</dd></div>' % (e(label), e(cls), value)


cands = doc.get("candidates", [])
strong = [c for c in cands if c["strength"] >= 75]
weak = [c for c in cands if c["strength"] < 75]
cards = cands
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

out.append('<header class="top"><div class="id">%s<div class="kicker">Ultima · Project audit</div><h1>%s</h1></div>' % (WORDMARK, e(repo)))
out.append('<div class="stats"><div class="stat"><b style="color:%s">%d</b><span>Supported</span></div><div class="stat"><b style="color:%s">%d</b><span>Weaker</span></div><div class="stat"><b style="color:%s">%d</b><span>Dismissed</span></div></div></header>' % (
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
metadata_html = '<dl class="meta overview-content">%s<div class="wide"><dt>Design system</dt><dd class="mono" style="color:#b9bedb;font-size:.82rem">%s</dd></div></dl>' % ("".join(meta_items), e(design))

out.append('<fieldset class="tabs category-tabs"><legend>Audit category</legend>')
for category, label in [("all", "Overview"), *CATEGORY_LABEL.items()]:
    count = len(cands) if category == "all" else sum(category in c["categories"] for c in cands)
    out.append('<input type="radio" name="category" id="cat-%s"%s><label for="cat-%s">%s <span>(%d)</span></label>' % (
        category, ' checked' if category == "all" else '', category, e(label), count))
out.append('</fieldset>')
statuses = {l["name"]: l["status"] for l in doc.get("lenses", [])}
excluded_dirs = set(profile.get("system_map", {}).get("coverage", {}).get("excluded_dirs", [])) | {".git", "node_modules", "vendor", "dist", "build", ".venv", "venv"}
def unexamined_source(lens):
    cov = doc.get("coverage", {}).get(lens, {})
    skipped = cov.get("dirs_skipped") or cov.get("skipped") or []
    return any(not (set(str(path).strip("/").split("/")) & excluded_dirs) for path in skipped)
category_coverage = []
for category, label in CATEGORY_LABEL.items():
    expected = CATEGORY_LENSES[category]
    completed = [l for l in expected if statuses.get(l) == "ok"]
    attempted = [l for l in expected if l in statuses]
    examined = [l for l in completed if doc.get("coverage", {}).get(l, {}).get("status") == "complete"
                and not unexamined_source(l) and not doc.get("coverage", {}).get(l, {}).get("unavailable_controls")]
    status = "complete" if len(examined) == len(expected) else ("partial" if attempted else "not examined")
    category_coverage.append(dd(label, e(status)))
out.append(metadata_html)
map_data = profile.get("system_map", {})
if map_data:
    out.append('<section class="sec system-map overview-content"><h2>System map</h2><p>Discovery seeds; declared dependencies do not establish runtime flow.</p><ul class="list">')
    for component in map_data.get("components", []):
        out.append('<li><strong>%s</strong><span class="why">%s%s</span></li>' % (e(component["name"]), e(component["path"]), ' · ' + e(component["manifest"]) if component.get("manifest") else ''))
    out.append('</ul>')
    edges = map_data.get("dependency_edges", [])
    if edges:
        out.append('<h3>Declared package dependencies</h3><ul class="list">%s</ul>' % ''.join('<li>%s → %s <span class="why">%s</span></li>' % (e(x['from']), e(x['to']), e(x['source'])) for x in edges))
    for key, label in (("entrypoints", "Entry points to inspect"), ("data_files", "Data and persistence"), ("deployment_files", "Delivery configuration")):
        paths = map_data.get(key, [])
        if paths:
            out.append('<details><summary>%s (%d)</summary><ul class="ev">%s</ul></details>' % (label, len(paths), ''.join('<li>%s</li>' % e(x) for x in paths)))
    for note in map_data.get("coverage", {}).get("notes", []):
        out.append('<p class="conv">%s</p>' % e(note))
    if map_data.get("coverage", {}).get("truncated"):
        out.append('<p>Discovery lists truncated: %s</p>' % e(', '.join(map_data['coverage']['truncated'])))
    context_path = os.path.join(run_dir, "system-context.md")
    if os.path.isfile(context_path):
        with open(context_path, encoding="utf-8") as context_file:
            out.append('<details><summary>Verified flows and audit context</summary><pre>%s</pre></details>' % e(context_file.read()))
    else:
        out.append('<p>Verified flow map unavailable. Discovery alone is not a deep architecture audit.</p>')
    out.append('</section>')

lens_tiles = []
for l in doc.get("lenses", []):
    status = l.get("status", "?")
    ok = status == "ok"
    label = "ok · %d in" % l.get("candidates_in", 0) if ok else status
    dot = COLOR[100] if ok else "#c96b6b"
    lens_tiles.append('<div class="lens" data-category="%s"><div class="n"><span class="dot" style="background:%s;box-shadow:0 0 8px %s"></span><span>%s</span></div><span class="s">%s</span></div>' % (
        next((c for c, names in CATEGORY_LENSES.items() if l.get("name") in names), ""), dot, dot, e(LENS_LABEL.get(l.get("name"), l.get("name"))), e(label)))
if lens_tiles:
    out.append('<section class="sec"><h2>Lenses</h2><div class="lenses">%s</div></section>' % "".join(lens_tiles))

out.append('<section class="sec"><div class="rankhead"><h2>Ranked candidates</h2><fieldset class="tabs"><legend>Confidence</legend>'
           '<input type="radio" name="f" id="f-all" checked><label for="f-all">All</label>'
           '<input type="radio" name="f" id="f-100"><label for="f-100">Established</label>'
           '<input type="radio" name="f" id="f-75"><label for="f-75">Supported</label>'
           '<input type="radio" name="f" id="f-50"><label for="f-50">Uncertain</label></fieldset></div>')
out.append('<ol class="rank">%s</ol></section>' % "".join(rank_row(c) for c in cards))
out.append('<section class="cards">%s<p class="empty">No findings match this category and confidence. See Coverage for audit limits.</p></section>' % "".join(card(c) for c in cards))

dis = "".join('<li><span>%s</span><span class="why">%s · %s</span></li>' % (
    e(d.get("title")), e(LENS_LABEL.get(d.get("lens"), d.get("lens") or "")), e(d.get("reason"))) for d in dismissed)
risk = "".join('<li><span class="tag">%s</span><span>%s</span></li>' % (e(LENS_LABEL.get(r.get("lens"), r.get("lens"))), e(r.get("text"))) for r in risks)
cov_items = list(category_coverage)
for lens, c in (doc.get("coverage", {}) or {}).items():
    if isinstance(c, dict):
        bits = []
        if c.get("files_read") is not None:
            bits.append("%s files read" % c.get("files_read"))
        skipped = c.get("dirs_skipped") or c.get("skipped")
        if skipped:
            bits.append("skipped <code>%s</code>" % e(", ".join(map(str, skipped))))
        if c.get("unavailable_controls"):
            bits.append("unavailable controls: " + e(", ".join(map(str, c["unavailable_controls"]))))
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
    recommendation = doc.get("recommendation")
    recommendation_html = '<p>%s</p>' % e(recommendation) if recommendation else ''
    steps = ''.join('<li><a href="#%s">%s</a> · %s</li>' % (e(c['id']), e(c['title']), e(c['action'].replace('-', ' '))) for c in strong[:5])
    out.append('<section class="start overview-content"><div class="body"><h2>Recommended work order</h2>%s<ol>%s</ol></div></section>' % (recommendation_html, steps))

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
