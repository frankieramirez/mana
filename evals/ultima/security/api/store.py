from types import SimpleNamespace

INVOICES = {'a': SimpleNamespace(tenant_id='alpha'), 'b': SimpleNamespace(tenant_id='beta')}


def load_invoice(invoice_id):
    return INVOICES[invoice_id]
