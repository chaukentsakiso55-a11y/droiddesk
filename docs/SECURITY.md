# Security model

## Protections in the MVP

- Pairing codes contain six random digits, expire after five minutes, and are
  consumed after one successful pairing.
- Each paired phone receives its own random bearer token.
- Tokens are compared with constant-time comparison.
- Controller state is stored outside the repository with user-only permissions
  where the operating system supports them.
- Request bodies are capped at 64 KiB and JSON types are validated.
- Remote commands are explicitly allowlisted on both sides.
- The API has no arbitrary command, shell, file-upload, or app-install endpoint.

## Important limitation

The MVP uses cleartext HTTP on the local network so a normal Android phone can
connect without installing a local certificate. Use it only on a trusted private
Wi-Fi network. Do not forward port 8765 to the internet.

Before internet or public-network support is added, use mutually authenticated
TLS or an end-to-end encrypted relay, rotate device credentials, and add device
revocation in the UI.

## Reporting

Do not post secrets or personal device data in a public issue. Report a security
problem privately to the repository owner.

