# Full historical dataset preparation

Run from the repository root with the existing Python environment:

```powershell
.\.venv\Scripts\python.exe -m scripts.build_full_dataset --audit-only
.\.venv\Scripts\python.exe -m scripts.build_full_dataset --offline
```

The first command acquires/audits 36 UTC calendar-month chunks for 2023-2025.
Each includes the following month's first timestamp for the existing T+1
aggregate mapping. Expected weather intervals are 8,760 / 8,784 / 8,760.
The site comes from common configuration; the model is explicitly gem_seamless.
No alternate model, interpolation, clamping, or freshness-policy change is used.

Output is isolated in `data/generated/gem_2023_2025/`. Raw response bytes and
request/retrieval metadata live in `provider_responses/YYYY-MM.json` and
`YYYY-MM.metadata.json`. Matching cached pairs are checked against SHA256 and
request identity, then reused without HTTP. HTTP failures are recorded and may
be retried by rerunning. Corrupt/incomplete cache pairs stop that chunk and must
be inspected; they are never silently replaced. Acquisition progress is saved
after each chunk; coverage_report.json aggregates yearly and monthly results.

The publication gate deliberately requires every hour to be individually valid.
Missing timestamps and present-but-invalid hours are reported separately, with
exact excluded interval starts and reasons. Negative irradiance remains a hard
failure. Wind/gust ordering remains only a diagnostic for otherwise valid hours.

If coverage passes, the offline command uses the existing reference PV model
and midpoint solar implementation. It checks every row and repeats all hourly
physics calculations for deterministic comparison before publishing the four
canonical CSVs and their handoff metadata. Existing published outputs are not
overwritten. Interrupted unpublished files may remain in publication_pending;
they are not a completed dataset. A complete publication includes all eight
required outputs and matching manifest hashes.

Current acquisition found all expected timestamps, but 54 hours have negative
GHI and DHI (21 in 2023, 16 in 2024, 17 in 2025). These values range from -46 to
-0.5 W/m2. No canonical full dataset was published. Exact periods and all monthly
completeness figures are in coverage_report.json. Provider cause is unconfirmed.
Do not relax validation or publish an incomplete dataset without a team decision.

Tests are offline:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.pipeline.test_full_dataset -v
```

Keep the committed seasonal sample unchanged. Generated full datasets and raw
provider caches are not automatically committed. Once quality passes, prefer
sharing a versioned archive of CSVs and provenance, with checksums, separately
from source code. Final size and sharing decisions follow successful publication.
