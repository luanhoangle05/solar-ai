# Frontend validation handoff

Tung intentionally removed the frontend from main in commit
`d10c11a4be12c7ed06ac8d3defd641d491a3dde1`. Luan's integration accepts that
deletion, including the two frontend files changed by the approved validation
fix `7b0e2fc3cf19d0eff6fb876e807ecafee9459f9f`.

When Tung's frontend is integrated again, port the frontend portion of that
fix into his branch:

- Accept individually valid wind/gust values regardless of ordering.
- Do not require `wind_gust_kmh >= wind_speed_kmh`: instantaneous wind and
  preceding-hour maximum gust have different temporal semantics.
- Do not clamp or replace either value.
- Keep frontend validation aligned with Python, including existing finite,
  nonnegative, required-value checks and all unrelated constraints.
- Retain/update the corresponding frontend tests, including wind 15 km/h and
  gust 8 km/h, invalid individual values, and nonblocking diagnostics without
  changing status or payload values.

The original frontend changes are preserved in Git history at the fix commit:
`frontend/src/schemas/frontend-data.ts` and
`frontend/src/schemas/frontend-data.test.ts`.
Do not restore those files alone into the backend branch. Reapply the semantics
to the complete frontend when its integration is approved.

The Python correction remains in place. No shared field names, CSV columns,
JSON structures, weather mapping, or freshness rules change during this merge.
