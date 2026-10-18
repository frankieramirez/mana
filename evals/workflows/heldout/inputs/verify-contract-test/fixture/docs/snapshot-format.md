# Snapshot format, version 2

The snapshot is UTF-8 text.

1. The first line is exactly `SHELF/2`.
2. Each following line is `<sku>;<count>`, where count is a base-10 integer with no padding.
3. Rows are sorted by sku in ascending code-point order.
4. The file ends with a single newline after the last row.

The replenishment reader rejects any other header and any file that does not end with a newline. Changing any of these rules needs a coordinated release of both services.
