# Founder Control Center

Private, fail-closed control plane for the founder portfolio.

## Invariants

- `UNKNOWN != GREEN`
- dashboard state never replaces source-of-truth systems
- every material status carries source/freshness metadata
- RED actions never execute autonomously
- YELLOW actions prepare only and require founder approval
- GREEN actions are read-only or internal/non-destructive
- no credentials are exposed to the browser

## Current MVP

- private token-based authentication (fails closed if token is absent)
- normalized Company Manifest model
- all known portfolio items visible from first boot
- ACTIVE / NEXT / WAIT per company
- CEO attention ranking with explicit uncertainty
- company detail pages
- action center with GREEN / YELLOW / RED enforcement
- audit log for every attempted control action
- read-only GitHub adapter
- application health adapter
- JSON APIs for companies, actions and audit
- responsive desktop/mobile UI

## Run

```bash
export FCC_ADMIN_TOKEN='use-a-long-random-secret'
export FCC_SESSION_SECRET='use-another-long-random-secret'
python -m founder_control_center.app
```

Open `http://127.0.0.1:8088`.

For local HTTP only, set `FCC_SECURE_COOKIE=0`. Keep it enabled behind HTTPS.

## Tests

```bash
python -m unittest discover -s founder_control_center/tests -v
```

## Live integrations

`FCC_GITHUB_TOKEN` is optional. Without it, the application intentionally shows repository truth as `UNKNOWN` during live refresh rather than fabricating a healthy state.

Production deployment, billing changes, external communications, destructive data operations and irreversible commitments are not executed by this MVP.

## Security status

Authentication is fail-closed. `FCC_ADMIN_TOKEN` and `FCC_SESSION_SECRET` stay server-side. The MVP does not claim 2FA is enabled: 2FA remains `UNKNOWN / NOT CONNECTED` until a real identity provider is integrated. Production deployment remains a YELLOW action requiring founder approval.
