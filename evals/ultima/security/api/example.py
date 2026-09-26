from types import SimpleNamespace


def example_request():
    return SimpleNamespace(invoice_id='b', session=SimpleNamespace(
        valid=True, tenant_id='alpha', token='SYNTHETIC-ONLY-SECRET-53'))
