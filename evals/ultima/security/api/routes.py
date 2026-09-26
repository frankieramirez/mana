from .middleware import authenticated, tenant_invoice
from .store import load_invoice
from .telemetry import audit


def legacy_invoice(request):
    invoice = load_invoice(request.invoice_id)
    audit(request)
    return invoice


def scoped_invoice(request):
    return load_invoice(request.invoice_id)


ROUTES = {
    '/legacy/invoice': authenticated(legacy_invoice),
    '/invoice': authenticated(tenant_invoice(scoped_invoice)),
}
