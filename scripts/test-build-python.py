#!/usr/bin/env python3
"""Offline contract fixtures for the Linear and Jira build-parent adapters.

The adapter is embedded in the portable ``tickets.sh`` shell script.  Extracting
it here keeps these tests independent of the shell dispatcher and of credentials.
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "skills" / "sift" / "scripts" / "tickets.sh"


def load_python_adapter(tracker: str):
    text = ADAPTER.read_text(encoding="utf-8")
    match = re.search(r"python3 - \"\$@\" <<'PY'(?:[^\n]*)\n(?P<code>.*)\nPY\n", text, re.S)
    if not match:
        raise AssertionError("tickets.sh has no embedded Python adapter")
    code = match.group("code")
    code = re.sub(r"\nmain\(\)\s*\Z", "", code)
    env = {
        "TICKETS_TRACKER": tracker,
        "TICKETS_PROJECT": "TEAM" if tracker == "linear" else "PROJ",
        "TICKETS_BODY_FILE": "",
        "LINEAR_API_KEY": "fixture",
        "JIRA_BASE_URL": "https://jira.example",
        "JIRA_EMAIL": "fixture@example",
        "JIRA_API_TOKEN": "fixture",
    }
    os.environ.update(env)
    namespace = {"__name__": "build_adapter_fixture"}
    exec(compile(code, str(ADAPTER), "exec"), namespace)
    return namespace


def output_of(callable_, *args):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        result = callable_(*args)
    return result, stream.getvalue()


def expected_failure(callable_, phrase, *args):
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        try:
            callable_(*args)
        except SystemExit as error:
            if error.code not in (1, 2, 3):
                raise AssertionError(f"unexpected exit code: {error.code!r}") from error
        else:
            raise AssertionError("expected adapter operation to fail")
    if phrase not in stderr.getvalue():
        raise AssertionError(f"expected {phrase!r} in adapter error, got {stderr.getvalue()!r}")


class LinearTransport:
    def __init__(self, namespace, fail_page=False):
        self.base = namespace["Linear"]()
        self.fail_page = fail_page
        self.updates = []
        self.issues = {
            "BLD-1": self.issue("BLD-1", "Build", "Work kind: build\n\n## Build order"),
            "CH-1": self.issue("CH-1", "Native child", "Native-only requirement."),
            "CH-2": self.issue("CH-2", "Explicit child", "Build parent: [Build](https://linear.example/BLD-1)"),
            "OTHER": self.issue("OTHER", "Other parent", "Work kind: build"),
        }
        self.issues["CH-1"]["parent"] = {
            "id": "id-BLD-1", "identifier": "BLD-1", "url": "https://linear.example/BLD-1"
        }
        self.base.gql = self.gql

    @staticmethod
    def issue(identifier, title, description, state_type="started"):
        return {
            "id": f"id-{identifier}", "identifier": identifier, "title": title,
            "url": f"https://linear.example/{identifier}", "description": description,
            "createdAt": identifier, "updatedAt": identifier,
            "state": {"name": "Open", "type": state_type},
            "labels": {"nodes": [{"name": "ready-for-agent", "id": "ready"}]},
            "assignee": None, "comments": {"nodes": []},
            "inverseRelations": {"nodes": []}, "parent": None,
        }

    def issue_for_test(self, identifier, title, description):
        return self.issue(identifier, title, description)

    def gql(self, query, variables=None):
        variables = variables or {}
        if "teams(" in query:
            return {"teams": {"nodes": [{"id": "team", "key": "TEAM", "name": "Team"}]}}
        if "issue(id:" in query:
            issue = self.issues.get(variables.get("i"))
            if not issue:
                return {"issue": None}
            return {"issue": issue}
        if "issues(" in query:
            if self.fail_page and variables.get("a") == "page-2":
                raise RuntimeError("second Linear page failed")
            page = variables.get("a")
            if page == "page-2":
                nodes = [self.issues["CH-2"]]
                return {"issues": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": nodes}}
            nodes = [self.issues["CH-1"]]
            return {"issues": {"pageInfo": {"hasNextPage": True, "endCursor": "page-2"}, "nodes": nodes}}
        if "issueUpdate" in query:
            issue_id = variables.get("id")
            issue = next(i for i in self.issues.values() if i["id"] == issue_id)
            payload = variables.get("i", {})
            if "description" in payload:
                issue["description"] = payload["description"]
                self.updates.append((issue["identifier"], payload["description"]))
            if "parentId" in payload:
                issue["parent"] = {"id": payload["parentId"]}
            return {"issueUpdate": {"success": True}}
        if "issueRelationCreate" in query:
            return {"issueRelationCreate": {"success": True}}
        if "viewer" in query:
            return {"viewer": {"id": "me", "name": "Fixture"}}
        raise AssertionError(f"unhandled Linear query: {query}")


class JiraTransport:
    def __init__(self, namespace, fail_page=False):
        self.base = namespace["Jira"]()
        self.fail_page = fail_page
        self.updates = []
        self.issues = {
            "PROJ-1": self.issue("PROJ-1", "Build", "Work kind: build\n\n## Build order"),
            "PROJ-2": self.issue("PROJ-2", "Native child", "Native-only requirement."),
            "PROJ-3": self.issue("PROJ-3", "Explicit child", "Build parent: [Build](https://jira.example/browse/PROJ-1)"),
            "PROJ-9": self.issue("PROJ-9", "Other parent", "Work kind: build"),
        }
        self.issues["PROJ-2"]["fields"]["parent"] = {"key": "PROJ-1"}
        self.issues["PROJ-1"]["fields"]["issuetype"] = {"hierarchyLevel": 1}
        self.base.api = self.api

    @staticmethod
    def issue(key, summary, description, status_category="indeterminate"):
        return {"id": f"id-{key}", "key": key, "fields": {
            "summary": summary, "description": {"type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]},
            "status": {"name": "Open", "statusCategory": {"key": status_category}},
            "labels": ["ready-for-agent"], "assignee": None, "issuelinks": [],
            "parent": None, "issuetype": {"hierarchyLevel": 0},
        }}

    def issue_for_test(self, key, summary, description):
        return self.issue(key, summary, description)

    def api(self, method, path, payload=None):
        if method == "GET" and path.startswith("/issue/"):
            key = path.split("/")[2].split("?")[0]
            return self.issues[key]
        if method == "POST" and path == "/search/jql":
            if self.fail_page and payload.get("nextPageToken") == "page-2":
                raise RuntimeError("second Jira page failed")
            if payload.get("nextPageToken") == "page-2":
                return {"issues": [self.issues["PROJ-3"]], "nextPageToken": None}
            return {"issues": [self.issues["PROJ-2"]], "nextPageToken": "page-2"}
        if method == "PUT" and path.startswith("/issue/"):
            key = path.split("/")[2]
            description = (payload.get("fields") or {}).get("description")
            if description is not None:
                self.issues[key]["fields"]["description"] = description
                self.updates.append((key, description))
            if "parent" in (payload.get("fields") or {}):
                self.issues[key]["fields"]["parent"] = payload["fields"]["parent"]
                self.updates.append((key, payload["fields"]["parent"]))
            return {}
        raise AssertionError(f"unhandled Jira request: {method} {path}")


class AdapterContract(unittest.TestCase):
    def assert_contract(self, namespace, transport, parent, child, other):
        adapter = transport.base
        for name in ("body", "update_body", "attach", "children"):
            self.assertTrue(hasattr(adapter, name), f"adapter lacks {name}()")

        _, body = output_of(adapter.body, child)
        self.assertIn("Native-only", body)

        result, printed = output_of(adapter.children, parent)
        self.assertIsNone(result)
        found = [line.split("\t") for line in printed.splitlines() if line.strip()]
        ids = {row[0] for row in found}
        self.assertEqual(ids, {child, other})

        # Use the explicit member as the attachment target after proving it is
        # discoverable. Remove its link to exercise the write path rather than
        # merely re-reading an already attached ticket.
        if hasattr(transport.issues[other], "get") and "description" in transport.issues[other]:
            transport.issues[other]["description"] = "Initial body"
        else:
            transport.issues[other]["fields"]["description"] = {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Initial body"}]}],
            }

        # Attaching twice must not duplicate native or explicit membership.
        target = other
        adapter.attach(target, parent)
        self.assertTrue(transport.updates, "attach must persist membership/native parent state")
        update_count = len(transport.updates)
        adapter.attach(target, parent)
        self.assertEqual(len(transport.updates), update_count)
        _, body = output_of(adapter.body, target)
        self.assertEqual(body.count("Build parent:"), 1)

        conflict_parent = "PROJ-9" if parent.startswith("PROJ-") else "OTHER"
        expected_failure(adapter.attach, "parent", target, conflict_parent)

        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as snapshot:
            snapshot.write("stale body\n")
            snapshot_path = snapshot.name
        try:
            expected_failure(adapter.update_body, "diff", target, "replacement body", snapshot_path)
        finally:
            os.unlink(snapshot_path)
        self.assertNotIn("replacement body", output_of(adapter.body, target)[1])

        # A current snapshot permits the guarded replacement.
        current = output_of(adapter.body, target)[1]
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as snapshot:
            snapshot.write(current)
            snapshot_path = snapshot.name
        try:
            adapter.update_body(target, "replacement body", snapshot_path)
        finally:
            os.unlink(snapshot_path)
        self.assertIn("replacement body", output_of(adapter.body, target)[1])

    def test_linear_union_conflict_stale_and_idempotent(self):
        ns = load_python_adapter("linear")
        transport = LinearTransport(ns)
        self.assert_contract(ns, transport, "BLD-1", "CH-1", "CH-2")

    def test_jira_union_conflict_stale_and_idempotent(self):
        ns = load_python_adapter("jira")
        transport = JiraTransport(ns)
        self.assert_contract(ns, transport, "PROJ-1", "PROJ-2", "PROJ-3")

    def test_linear_children_failed_page_is_not_silent(self):
        ns = load_python_adapter("linear")
        transport = LinearTransport(ns, fail_page=True)
        self.assertTrue(hasattr(transport.base, "children"), "Linear adapter lacks children()")
        with self.assertRaises(RuntimeError):
            output_of(transport.base.children, "BLD-1")

    def test_jira_children_failed_page_is_not_silent(self):
        ns = load_python_adapter("jira")
        transport = JiraTransport(ns, fail_page=True)
        self.assertTrue(hasattr(transport.base, "children"), "Jira adapter lacks children()")
        with self.assertRaises(RuntimeError):
            output_of(transport.base.children, "PROJ-1")

    def test_jira_unknown_hierarchy_uses_explicit_membership(self):
        ns = load_python_adapter("jira")
        transport = JiraTransport(ns)
        child = "PROJ-4"
        transport.issues[child] = transport.issue(child, "Unknown child", "Initial body")
        transport.issues[child]["fields"]["issuetype"] = {"hierarchyLevel": None}
        self.assertTrue(hasattr(transport.base, "attach"), "Jira adapter lacks attach()")
        transport.base.attach(child, "PROJ-1")
        body = output_of(transport.base.body, child)[1]
        self.assertIn("Build parent:", body)

    def test_literal_find_includes_closed_tickets(self):
        ns = load_python_adapter("linear")
        linear = LinearTransport(ns)
        linear.issues["CH-2"].update(description="source [x].", state={"name": "Done", "type": "completed"})
        printed = output_of(linear.base.find, "[x].")[1]
        self.assertIn("CH-2\tcompleted", printed)
        self.assertEqual(output_of(linear.base.find, ".*")[1], "")
        ns = load_python_adapter("jira")
        jira = JiraTransport(ns)
        jira.issues["PROJ-3"]["fields"].update(description=ns["adf"]("source [x]."),
            status={"name": "Done", "statusCategory": {"key": "done"}})
        self.assertIn("PROJ-3\tDone", output_of(jira.base.find, "[x].")[1])
        self.assertEqual(output_of(jira.base.find, ".*")[1], "")

    def test_missing_pagination_cursor_refuses_partial_discovery(self):
        ns = load_python_adapter("linear")
        linear = LinearTransport(ns)
        transport = linear.gql
        def missing_cursor(query, variables=None):
            response = transport(query, variables)
            if "issues" in response:
                response["issues"]["pageInfo"] = {"hasNextPage": True, "endCursor": None}
            return response
        linear.base.gql = missing_cursor
        expected_failure(linear.base.find, "pagination", "Build parent")
        ns = load_python_adapter("jira")
        jira = JiraTransport(ns)
        def missing_token(method, path, payload=None):
            return {"issues": [], "isLast": False}
        jira.base.api = missing_token
        expected_failure(jira.base.find, "pagination", "Build parent")

    def test_linear_next_rechecks_full_description_before_claiming(self):
        ns = load_python_adapter("linear")
        transport = LinearTransport(ns)
        build = transport.issue_for_test("BUILD-NEXT", "Build index", "Work kind: build")
        ready = transport.issue_for_test("READY-NEXT", "Ready implementation", "Build parent: [Build](parent)")
        transport.issues.update({"BUILD-NEXT": build, "READY-NEXT": ready})
        transport.base.open_issues = lambda **_: [
            {key: build[key] for key in ("identifier", "title", "url", "createdAt", "updatedAt", "labels", "assignee", "inverseRelations")},
            {key: ready[key] for key in ("identifier", "title", "url", "createdAt", "updatedAt", "labels", "assignee", "inverseRelations")},
        ]
        _, printed = output_of(transport.base.next, "ready-for-agent", False)
        self.assertIn("READY-NEXT", printed)
        self.assertNotIn("BUILD-NEXT", printed)

    def test_jira_next_rechecks_full_description_before_claiming(self):
        ns = load_python_adapter("jira")
        transport = JiraTransport(ns)
        build = transport.issue_for_test("PROJ-8", "Build index", "Work kind: build")
        ready = transport.issue_for_test("PROJ-7", "Ready implementation", "Build parent: [Build](parent)")
        transport.issues.update({"PROJ-8": build, "PROJ-7": ready})
        transport.base.search = lambda *_args, **_kwargs: [
            {"key": "PROJ-8", "fields": {"summary": "Build index", "created": "1", "assignee": None,
                "status": {"statusCategory": {"key": "indeterminate"}}, "issuelinks": []}},
            {"key": "PROJ-7", "fields": {"summary": "Ready implementation", "created": "2", "assignee": None,
                "status": {"statusCategory": {"key": "indeterminate"}}, "issuelinks": []}},
        ]
        _, printed = output_of(transport.base.next, "ready-for-agent", False)
        self.assertIn("PROJ-7", printed)
        self.assertNotIn("PROJ-8", printed)


if __name__ == "__main__":
    unittest.main()
