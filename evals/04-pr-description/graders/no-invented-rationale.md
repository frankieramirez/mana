---
type: regex
target: last_message
match: not_contains
weight: 1
flags: i
---
\b(rotat(e|es|ed|ing|ion)|stale|revoc\w*|revoke[sd]?|invalidat\w*|thundering herd|rate.?limit\w*|Auth0|Okta|Cognito|Keycloak|jwks-rsa|node-jwks|roll\s?out)\b
