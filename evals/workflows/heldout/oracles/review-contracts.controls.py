"""Evaluator-only behavioral controls for review-contracts. Never copy into a candidate workspace.

Usage: python3 -I -B review-contracts.controls.py WORKSPACE
Prints one JSON object mapping each control id to {"passed": bool, "detail": str}.
"""
import json
import sys
import traceback
from datetime import date

sys.path.insert(0, sys.argv[1])

from invoices.access import can_view  # noqa: E402
from invoices.listing import list_invoices  # noqa: E402
from invoices.models import Invoice, Principal  # noqa: E402
from invoices.store import InvoiceStore  # noqa: E402
from reports.export import export_org  # noqa: E402

ACME_NEW = Invoice("A-3", "acme", date(2026, 5, 2))
ACME_MID = Invoice("A-2", "acme", date(2026, 2, 14))
ACME_OLD = Invoice("A-1", "acme", date(2025, 11, 30), archived=True)
GLOBEX = Invoice("G-1", "globex", date(2026, 4, 1))
GLOBEX_OLD = Invoice("G-0", "globex", date(2025, 6, 6), archived=True)
STORE = InvoiceStore([ACME_MID, GLOBEX, ACME_OLD, ACME_NEW, GLOBEX_OLD])

MEMBER = Principal("ana", "member", "acme")
ADMIN = Principal("cy", "admin", "acme")
OTHER_ADMIN = Principal("dee", "admin", "globex")
OTHER_MEMBER = Principal("bo", "member", "globex")


def numbers(rows):
    return [inv.number for inv in rows]


def cross_tenant_admin():
    """Identity cross-tenant-admin: an admin of one org must not see another org's invoices."""
    seen = [can_view(OTHER_ADMIN, inv) for inv in (ACME_NEW, ACME_OLD)]
    seen += [can_view(OTHER_ADMIN, inv, include_archived=True) for inv in (ACME_NEW, ACME_OLD)]
    listed = numbers(list_invoices(STORE, OTHER_ADMIN, "acme", include_archived=True))
    assert not any(seen), "globex admin can view acme invoices: %r" % seen
    assert listed == [], "globex admin lists acme invoices: %r" % listed


def archived_hidden_by_default():
    """Identity archived-visible-without-opt-in: archived rows need an admin of the org asking for them."""
    cases = {
        "member": can_view(MEMBER, ACME_OLD),
        "member asking": can_view(MEMBER, ACME_OLD, include_archived=True),
        "admin not asking": can_view(ADMIN, ACME_OLD),
    }
    leaked = [k for k, v in cases.items() if v]
    assert not leaked, "archived invoice visible to: %s" % ", ".join(leaked)
    listed = numbers(list_invoices(STORE, MEMBER, "acme", include_archived=True))
    assert "A-1" not in listed, "member listing includes archived invoice: %r" % listed


def listing_newest_first():
    """Identity listing-oldest-first: newest first, and limit keeps the newest rows.

    Uses an admin of the org who asks for archived rows, a view that both access
    identities leave correct, so this control isolates the ordering failure.
    """
    full = numbers(list_invoices(STORE, ADMIN, "acme", include_archived=True))
    assert full == ["A-3", "A-2", "A-1"], "admin opt-in listing order: %r" % full
    top = numbers(list_invoices(STORE, ADMIN, "acme", include_archived=True, limit=2))
    assert top == ["A-3", "A-2"], "admin listing with limit 2: %r" % top


def admin_archive_opt_in():
    """Preserved: an admin of the org who asks sees the org's archived invoices (any order)."""
    assert can_view(ADMIN, ACME_OLD, include_archived=True), "admin cannot opt in to archived"
    listed = sorted(numbers(list_invoices(STORE, ADMIN, "acme", include_archived=True)))
    assert listed == ["A-1", "A-2", "A-3"], "admin opt-in listing: %r" % listed


def member_own_org():
    """Preserved: members see their own org's current invoices and nothing of other orgs."""
    assert can_view(MEMBER, ACME_NEW), "member cannot see own invoice"
    assert not can_view(OTHER_MEMBER, ACME_NEW), "member sees another org"


def signed_out_denied():
    """Preserved: a signed out visitor sees nothing."""
    assert not can_view(None, ACME_NEW), "signed out visitor sees an invoice"
    assert numbers(list_invoices(STORE, None, "acme")) == [], "signed out listing is not empty"


def auditor_export():
    """Preserved caller: the compliance exporter reads every org, archived invoices included."""
    exporter = Principal("ledger-export", "auditor", None)
    assert can_view(exporter, GLOBEX_OLD), "auditor cannot view another org's archived invoice"
    acme = sorted(export_org(STORE, "acme"))
    globex = sorted(export_org(STORE, "globex"))
    assert acme == ["A-1", "A-2", "A-3"], "acme export: %r" % acme
    assert globex == ["G-0", "G-1"], "globex export: %r" % globex


CONTROLS = (cross_tenant_admin, archived_hidden_by_default, listing_newest_first,
            admin_archive_opt_in, member_own_org, signed_out_denied, auditor_export)

results = {}
for control in CONTROLS:
    try:
        control()
        results[control.__name__] = {"passed": True, "detail": ""}
    except Exception as exc:  # a crash is a failed control, with its reason kept
        detail = str(exc) if isinstance(exc, AssertionError) else traceback.format_exception_only(exc)[-1].strip()
        results[control.__name__] = {"passed": False, "detail": detail}
print(json.dumps(results, sort_keys=True))
