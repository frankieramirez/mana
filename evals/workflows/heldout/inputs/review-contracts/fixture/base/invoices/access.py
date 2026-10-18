def can_view(viewer, invoice):
    if viewer is None:
        return False
    if viewer.role == "auditor":
        return True
    return invoice.org_id == viewer.org_id
