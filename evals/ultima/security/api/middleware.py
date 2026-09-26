from .store import load_invoice


def authenticated(handler):
    def wrapped(request):
        if not request.session.valid:
            raise PermissionError('authentication required')
        return handler(request)
    return wrapped


def tenant_invoice(handler):
    def wrapped(request):
        invoice = load_invoice(request.invoice_id)
        if invoice.tenant_id != request.session.tenant_id:
            raise PermissionError('wrong tenant')
        return handler(request)
    return wrapped
