# Taiwan PCC Public-Viewing Slice

This branch now targets one executable, commercially useful source slice rather than waiting for four PCC datasets at once.

- Official source: PCC dataset 7260 — public viewing announcements before tender publication.
- Signal: `PROCUREMENT_PLAN`.
- Coverage: rolling previous-week public-viewing cases only; not full Taiwan procurement coverage.
- Identity: publisher tender/case number required and preserved.
- Fetch: official PCC XML endpoint.
- Incremental semantics: full rolling snapshot re-fetch; canonical idempotency handles repeats; disappearance is not cancellation.
- Construction: publisher procurement-nature field is preserved when supplied, but construction-code live proof remains part of validation. This source still has independent commercial value as pre-tender intelligence.
- Rights: official open-data catalogue, daily, free, Open Government Data License v1.0.
- Production status: not claimed until live workflow proves payload/schema against the official endpoint and runtime/source registry integration is complete.
