# DroidDesk LAN protocol v1

The Windows controller listens on TCP port `8765`. Android is the client.
Messages use UTF-8 JSON with a maximum request body of 64 KiB.

## Pair

`POST /api/v1/pair`

```json
{"pairCode":"123456","deviceName":"My phone","androidVersion":"16"}
```

The code is single-use and expires after five minutes. A successful response
contains `deviceId`, `token`, `protocolVersion`, and `pollSeconds`.

## Authenticated calls

All remaining endpoints require `Authorization: Bearer <token>`.

- `POST /api/v1/status` updates device name, battery, Android version, and time.
- `GET /api/v1/commands?after=<id>` returns pending allowlisted commands.
- `POST /api/v1/commands/<id>/ack` records command completion.

Supported command types are `SHOW_HOME`, `OPEN_SETTINGS`, and `SYNC_NOW`.
Unknown command types are rejected by the controller and ignored by Android.

## Versioning

This document describes protocol version `1`. Incompatible future changes must
use a new `/api/vN` prefix.

