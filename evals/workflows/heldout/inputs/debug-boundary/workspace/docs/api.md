# POST /readings

Devices post one JSON object per batch.

| Field | Rule |
|---|---|
| `readings` | Required. A non-empty list of JSON numbers. Integers and decimals are both fine, including zero and negative values. Strings (even numeric ones), booleans, `null`, nested lists, `NaN` and `Infinity` are invalid. |
| `device` | Optional string. Echoed back in the response. |
| anything else | Accepted and ignored. Firmware adds fields such as `fw` and `battery` without notice. |

A valid batch gets `200` with `device`, `count`, `mean` (three decimals), `min` and `max`.

An invalid batch gets `400` with an `error` string that names the problem. It is not summarized.

`500` means a bug on our side. The dispatcher logs the traceback for every `500`, and on-call reads those logs. Never answer a bug in our code with `400` or `200`.
