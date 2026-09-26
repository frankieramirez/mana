# Invoice access and logging contract

Only the owning tenant may read an invoice.
Session token values must never appear in logs.

The application must enforce tenant ownership regardless of gateway configuration. The gateway's deployed policy and log collector configuration are unavailable in this fixture. These files describe synthetic data and local source only. They do not establish production exposure or a successful exploit.
