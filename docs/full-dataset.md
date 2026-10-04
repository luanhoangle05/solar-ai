# Full historical dataset preparation

Run from the repository root with the existing Python environment:

```powershell
.\.venv\Scripts\python.exe -m scripts.build_full_dataset --audit-only --offline
.\.venv\Scripts\python.exe -m scripts.build_full_dataset --offline
```

The first command audits the existing 36 cached UTC calendar-month chunks for 2023-2025.
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

The approved Policy A excludes whole timestamp groups failing hard validation
only for negative GHI/DHI. Shared validation remains unchanged. Missing hours,
duplicate timestamps, null/nonfinite values, other validation failures and failed
chunks still block publication. The gate requires exactly 54 unique exclusions
and accepted yearly hours 8,739 / 8,768 / 8,743. Count differences stop publication.
Wind/gust ordering remains only a diagnostic for otherwise valid hours.

If coverage passes, the offline command uses the existing reference PV model
and midpoint solar implementation. It checks every row and repeats all hourly
physics calculations for deterministic comparison before publishing the four
canonical CSVs and their handoff metadata. Existing published outputs are not
overwritten. Interrupted unpublished files may remain in publication_pending;
they are not a completed dataset. A complete publication includes all eight
required outputs and matching manifest hashes.

All expected timestamps were retrieved, but 54 nighttime hours have negative
GHI and DHI (21 in 2023, 16 in 2024, 17 in 2025), from -46 to -0.5 W/m2.
Provider cause is unconfirmed. No angle variants are generated for these hours:
378 rows are omitted, leaving 183,750 rows. Official UTC year splits are 2023
train (61,173), 2024 validation (61,376), 2025 test (61,201); never percentage
or random split. Raw caches and the seasonal sample remain unchanged.

Both manifest.json and quality_report.json retain exact exclusion timestamps,
reasons, raw GHI/DHI, year/month, coverage before/after and lost row count.
No interpolation, clamping, replacement or source substitution occurs.
README_DUY.md warns about gaps: sequence models must use actual timestamps,
stop look-back at missing hours and pad history rather than bridge a gap.
Verify Duy's existing LSTM against the actual gaps before final handoff.

Tests are offline:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.pipeline.test_full_dataset -v
```

Keep the committed seasonal sample unchanged. Generated full datasets and raw
provider caches are not automatically committed. Once quality passes, prefer
sharing a versioned archive of CSVs and provenance, with checksums, separately
from source code. Final size and sharing decisions follow successful publication.
