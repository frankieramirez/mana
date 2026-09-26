import logging


def audit(request):
    logging.info('session=%s', request.session.token)
