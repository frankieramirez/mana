def can_view(viewer, invoice, include_archived=False):
    if viewer is None:
        return False
    if viewer.role == "auditor":
        return True
    show_archived = include_archived and viewer.role == "admin"
    return invoice.org_id == viewer.org_id or viewer.role == "admin" and (show_archived or not invoice.archived)
