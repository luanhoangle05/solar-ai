"""Monthly fixed-GEM acquisition, strict coverage gate, and offline PV exports.

Run from the repository root: python -m scripts.build_full_dataset
Use --audit-only to acquire/audit without generating labels; --offline forbids HTTP.
Successful cache pairs are immutable and checked before reuse. Failed chunks are
reported and retried on the next invocation, never filled from another source.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess

import pandas as pd
import requests

from src.common.config import DEMO_LATITUDE_DEG, DEMO_LONGITUDE_DEG, DEFAULT_CONFIG
from src.common.schema import WEATHER_COLUMNS, FEATURE_COLUMNS, validate_weather_row
from src.pipeline.client import VARIABLES, _map_response
from src.pipeline.reference_pv import expand_hour, pv_metadata, split_for_timestamp
from src.pipeline.validate import _inspect_weather, _finite_number

ENDPOINT = 'https://historical-forecast-api.open-meteo.com/v1/forecast'
MODEL = 'gem_seamless'
ROOT = Path(__file__).resolve().parents[1] / 'data/generated/gem_2023_2025'
HOUR = timedelta(hours=1)
YEARS = (2023, 2024, 2025)
APPROVED_ACCEPTED_HOURS = {'2023': 8739, '2024': 8768, '2025': 8743}
NEGATIVE_IRRADIANCE_ISSUES = {'ghi_wm2: cannot be negative', 'dhi_wm2: cannot be negative'}


def stamp(value):
    return value.isoformat().replace('+00:00', 'Z')


def digest(content):
    return hashlib.sha256(content).hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def months():
    for year in YEARS:
        for month in range(1, 13):
            start = datetime(year, month, 1, tzinfo=timezone.utc)
            end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=timezone.utc)
            yield start, end


def parameters(start, end):
    # Terminal endpoint is required for preceding-hour aggregates at T+1.
    return dict(latitude=DEMO_LATITUDE_DEG, longitude=DEMO_LONGITUDE_DEG,
                hourly=','.join(VARIABLES), timezone='UTC', timeformat='unixtime',
                temperature_unit='celsius', wind_speed_unit='kmh', precipitation_unit='mm',
                models=MODEL, start_hour=start.strftime('%Y-%m-%dT%H:%M'),
                end_hour=end.strftime('%Y-%m-%dT%H:%M'))


def acquire(root, start, end, offline=False):
    cache = root / 'provider_responses'
    cache.mkdir(parents=True, exist_ok=True)
    key = start.strftime('%Y-%m')
    raw, meta = cache / (key + '.json'), cache / (key + '.metadata.json')
    params = parameters(start, end)
    if raw.exists() and meta.exists():
        content = raw.read_bytes()
        provenance = json.loads(meta.read_text(encoding='utf-8'))
        if (provenance['endpoint'] != ENDPOINT or provenance['request_parameters'] != params
                or provenance['sha256'] != digest(content)):
            raise ValueError('Cache integrity/identity mismatch; preserve and inspect cache')
        return json.loads(content), provenance
    if raw.exists() or meta.exists():
        raise ValueError('Incomplete cache pair; preserve and inspect before retry')
    if offline:
        raise ValueError('Missing cache in offline mode')
    response = requests.get(ENDPOINT, params=params, timeout=60, allow_redirects=False)
    try:
        if response.status_code != 200:
            raise ValueError(f'Historical provider HTTP {response.status_code}')
        content = response.content
        payload = json.loads(content)
        if not isinstance(payload, dict) or payload.get('error'):
            raise ValueError('Historical provider returned an error or invalid object')
        provenance = dict(endpoint=ENDPOINT, request_parameters=params,
                          fetched_at=stamp(datetime.now(timezone.utc)), sha256=digest(content))
        # Metadata acts as completion marker; partial pairs are never silently reused.
        temp = raw.with_suffix('.json.tmp')
        temp.write_bytes(content)
        temp.replace(raw)
        write_json(meta, provenance)
        return payload, provenance
    finally:
        response.close()


def gap_ranges(instants):
    ranges = []
    for value in sorted(set(instants)):
        if ranges and value == ranges[-1][1] + HOUR:
            ranges[-1][1] = value
        else:
            ranges.append([value, value])
    return [dict(start=stamp(a), end_inclusive=stamp(b), hours=int((b-a)/HOUR)+1)
            for a, b in ranges]


def audit_chunk(payload, provenance, start, end):
    expected = [start + n*HOUR for n in range(int((end-start)/HOUR))]
    hourly = payload.get('hourly', {}) if isinstance(payload, dict) else {}
    hourly = hourly if isinstance(hourly, dict) else {}
    times = hourly.get('time', [])
    times = times if isinstance(times, list) else []
    index = {t:i for i,t in enumerate(times) if type(t) is int}
    counter = Counter(t for t in times if type(t) is int)
    missing = [t for t in expected if int(t.timestamp()) not in index]
    duplicates = sum(max(0, counter[int(t.timestamp())]-1) for t in expected)
    bad_values = Counter()
    reasons = Counter()
    exclusions, accepted = [], []
    diagnostic = 0
    for t in expected:
        for provider, (field, _, aggregate) in VARIABLES.items():
            i = index.get(int((t+HOUR if aggregate else t).timestamp()))
            values = hourly.get(provider)
            if i is None or not isinstance(values, list) or i >= len(values) or not _finite_number(values[i]):
                bad_values[field] += 1
        weather, issues = None, []
        try:
            weather = _map_response(payload, t, t+HOUR,
                                    datetime.fromisoformat(provenance['fetched_at']),
                                    'open-meteo-historical-forecast-gem_seamless')
            issues, _ = _inspect_weather(weather)
            if issues:
                raise ValueError('; '.join(issues))
        except (ValueError, RuntimeError) as exc:
            reason = str(exc)
            reasons[reason] += 1
            exclusions.append(dict(timestamp=stamp(t), reason=reason, year=t.year,
                month=t.strftime('%Y-%m'), raw_ghi_wm2=weather['ghi_wm2'] if weather else None,
                raw_dhi_wm2=weather['dhi_wm2'] if weather else None,
                policy_a_eligible=bool(issues) and set(issues)<=NEGATIVE_IRRADIANCE_ISSUES))
            continue
        accepted.append(weather)
        diagnostic += int(weather['wind_gust_kmh'] < weather['wind_speed_kmh'])
    excluded_times = [datetime.fromisoformat(x['timestamp']) for x in exclusions]
    report = dict(month=start.strftime('%Y-%m'), expected_hours=len(expected),
                  retrieved_hours=len(expected)-len(missing), missing_timestamps=[stamp(t) for t in missing],
                  duplicate_timestamps=duplicates, invalid_required_value_counts=dict(bad_values),
                  hard_validation_failures=len(exclusions), exclusions=exclusions,
                  exclusion_reasons=dict(reasons), accepted_hours=len(accepted),
                  wind_gust_diagnostic_hours=diagnostic,
                  completeness_pct=100*len(accepted)/len(expected),
                  missing_periods=gap_ranges(missing), unusable_periods=gap_ranges(excluded_times))
    return accepted, report


def publication_allowed(reports, yearly, failures):
    exclusions = [x for r in reports for x in r['exclusions']]
    return (not failures and len(reports)==36
        and {y:r['accepted_hours'] for y,r in yearly.items()}==APPROVED_ACCEPTED_HOURS
        and len(exclusions)==54 and len({x['timestamp'] for x in exclusions})==54
        and all(x['policy_a_eligible'] for x in exclusions)
        and all(r['retrieved_hours']==r['expected_hours'] and r['duplicate_timestamps']==0
                and not r['invalid_required_value_counts']
                and r['accepted_hours']+len(r['exclusions'])==r['expected_hours'] for r in reports))


def exclusion_provenance(coverage):
    exclusions = [x for r in coverage.get('months', []) for x in r['exclusions']]
    return dict(policy='Policy A: omit entire hours failing only negative GHI/DHI validation',
        excluded_hours=len(exclusions), exclusions=exclusions, rows_lost=7*len(exclusions),
        coverage_by_year={y:dict(expected_hours=r['expected_hours'],
            retrieved_hours=r.get('retrieved_hours', r['expected_hours']),
            accepted_hours=r['accepted_hours'],
            before_exclusion_pct=100*r.get('retrieved_hours', r['expected_hours'])/r['expected_hours'],
            after_exclusion_pct=100*r['accepted_hours']/r['expected_hours'])
            for y,r in coverage['years'].items()},
        raw_provider_caches='Preserved unchanged; SHA256 verified before reuse',
        corrections='None: no interpolation, clamping, replacement, or source substitution')


def audit(root, offline=False):
    root.mkdir(parents=True, exist_ok=True)
    reports, observations, sources, failures = [], [], [], []
    for start, end in months():
        try:
            payload, provenance = acquire(root, start, end, offline)
        except (requests.RequestException, ValueError, OSError, KeyError) as exc:
            # No credential-bearing URL or response body in failure reports.
            reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
            failures.append(dict(month=start.strftime('%Y-%m'), reason=reason))
            payload, provenance = {}, {'fetched_at': stamp(datetime.now(timezone.utc))}
        else:
            sources.append(dict(month=start.strftime('%Y-%m'), **provenance))
        accepted, report = audit_chunk(payload, provenance, start, end)
        reports.append(report)
        observations.extend(accepted)
        print(f"{report['month']}: {report['accepted_hours']}/{report['expected_hours']} accepted", flush=True)
        write_json(root/'acquisition_progress.json', dict(months=reports, failed_chunks=failures))
    yearly = {}
    for year in YEARS:
        selected = [r for r in reports if r['month'].startswith(str(year))]
        summary = {key:sum(r[key] for r in selected) for key in
                   ('expected_hours','retrieved_hours','duplicate_timestamps','hard_validation_failures',
                    'accepted_hours','wind_gust_diagnostic_hours')}
        missing = [datetime.fromisoformat(t) for r in selected for t in r['missing_timestamps']]
        excluded = [datetime.fromisoformat(x['timestamp']) for r in selected for x in r['exclusions']]
        summary.update(missing_hours=len(missing), excluded_hours=len(excluded),
                       completeness_pct=100*summary['accepted_hours']/summary['expected_hours'],
                       missing_periods=gap_ranges(missing), unusable_periods=gap_ranges(excluded),
                       longest_missing_gap_hours=max((r['hours'] for r in gap_ranges(missing)), default=0),
                       longest_unusable_gap_hours=max((r['hours'] for r in gap_ranges(excluded)), default=0))
        for field in ('invalid_required_value_counts', 'exclusion_reasons'):
            counts = Counter()
            for r in selected:
                counts.update(r[field])
            summary[field] = dict(counts)
        yearly[str(year)] = summary
    passed = publication_allowed(reports, yearly, failures)
    result = dict(status='PASS' if passed else 'NOT READY', years=yearly, months=reports,
                  failed_chunks=failures, policy='Policy A: exactly 54 negative-GHI/DHI hours excluded; all other failures block')
    write_json(root/'coverage_report.json', result)
    return observations, sources, result


def generate(root, observations, sources, coverage):
    if coverage['status'] != 'PASS':
        raise ValueError('Coverage gate failed; no canonical CSV publication')
    # Refuse replacement of published outputs; reruns can always audit cached data.
    names = ('full_dataset.csv','train.csv','validation.csv','test.csv','manifest.json',
             'quality_report.json','split_summary.json','README_DUY.md')
    if any((root/name).exists() for name in names):
        raise ValueError('Published output already exists; inspect rather than overwrite')
    rows, physics = [], []
    for i, weather in enumerate(observations):
        expanded, diagnostics = expand_hour(weather, DEMO_LATITUDE_DEG, DEMO_LONGITUDE_DEG)
        rows.extend(expanded)
        physics.extend(diagnostics)
        if i % 744 == 0:
            print(f'PV hours: {i}/{len(observations)}', flush=True)
    df = pd.DataFrame(rows, columns=WEATHER_COLUMNS)
    quality, splits = check_rows(df, physics, coverage)
    # Verify every generated hour again, not just a small repeatability sample.
    for i, weather in enumerate(observations):
        repeated, repeated_physics = expand_hour(weather, DEMO_LATITUDE_DEG, DEMO_LONGITUDE_DEG)
        if repeated != rows[i*7:(i+1)*7] or repeated_physics != physics[i*7:(i+1)*7]:
            raise ValueError('Deterministic regeneration failed')
        if i % 744 == 0:
            print(f'Reproducibility hours: {i}/{len(observations)}', flush=True)
    quality['deterministic_full_regeneration'] = True
    staging = root/'publication_pending'
    staging.mkdir(exist_ok=True)
    df.to_csv(staging/'full_dataset.csv', index=False, lineterminator='\n')
    for split, year in zip(('train','validation','test'), YEARS):
        df[df.timestamp.str.startswith(str(year))].to_csv(staging/f'{split}.csv', index=False, lineterminator='\n')
    write_json(staging/'quality_report.json', quality)
    write_json(staging/'split_summary.json', splits)
    (staging/'README_DUY.md').write_text(handoff_text(), encoding='utf-8')
    code = subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip()
    code_paths = ('scripts/build_full_dataset.py','src/pipeline/reference_pv.py',
                  'src/pipeline/client.py','src/pipeline/solar_position.py',
                  'src/pipeline/transform.py','src/pipeline/validate.py','src/common/config.py',
                  'src/common/schema.py')
    repo = Path(__file__).resolve().parents[1]
    manifest = dict(site='Calgary development site', latitude=DEMO_LATITUDE_DEG, longitude=DEMO_LONGITUDE_DEG,
        endpoint=ENDPOINT, historical_model=MODEL, weather_source='archived operational forecasts, not station measurements',
        start='2023-01-01T00:00:00Z', end_inclusive='2025-12-31T23:00:00Z',
        chunk_strategy='UTC calendar months, plus terminal T+1 timestamp; immutable SHA256-verified cache pairs',
        generated_at=stamp(datetime.now(timezone.utc)), sources=sources, variables=VARIABLES,
        reference_pv=pv_metadata(), candidate_angles=list(DEFAULT_CONFIG.candidate_angles_deg),
        label_semantics='physics-derived AC kWh per 20-panel row per one-hour interval',
        splits=splits, exclusions=exclusion_provenance(coverage)['exclusions'],
        exclusion_provenance=exclusion_provenance(coverage), source_code_commit=code,
        source_code_note='Generator may be uncommitted; exact source hashes below identify executed code',
        source_sha256={p:digest((repo/p).read_bytes()) for p in code_paths},
        limitations=['Reference simulation, not measured generation', 'Archived stitched forecasts lack fixed forecast lead time',
            'Hourly mean irradiance with midpoint solar position; horizon crossing approximation',
            'No dynamic snow/shading/soiling/bifacial/degradation; generic loss 14% once',
            'POA used as effective irradiance; no separate spectral/IAM correction',
            'Historical offline quality checks do not assert operational freshness'],
        output_sha256={p.name:digest(p.read_bytes()) for p in staging.iterdir() if p.is_file()})
    write_json(staging/'manifest.json', manifest)
    for name in names:
        (staging/name).replace(root/name)
    print('READY FOR FULL MODEL TUNING', flush=True)


def check_rows(df, physics, coverage):
    if tuple(df.columns) != WEATHER_COLUMNS or df.empty:
        raise ValueError('Invalid CSV schema or empty data')
    if 'actual_kwh' in FEATURE_COLUMNS or 'timestamp' in FEATURE_COLUMNS:
        raise ValueError('Inference feature leakage')
    for row in df.to_dict('records'):
        validate_weather_row(row)
    if df.isna().any().any() or df.duplicated(['timestamp','panel_angle_deg']).any():
        raise ValueError('Missing values or duplicate pairs')
    groups = df.groupby('timestamp', sort=False).panel_angle_deg.agg(list)
    if not all(v == list(DEFAULT_CONFIG.candidate_angles_deg) for v in groups):
        raise ValueError('Incomplete angle grouping')
    if list(groups.index) != sorted(groups.index):
        raise ValueError('Unordered timestamps')
    timestamps = pd.to_datetime(df.timestamp, utc=True)
    excluded = {pd.Timestamp(x['timestamp']) for r in coverage.get('months', []) for x in r['exclusions']}
    if set(timestamps)&excluded:
        raise ValueError('Excluded weather hour was published')
    splits = {}
    for year, split in zip(YEARS, ('train','validation','test')):
        part = df[timestamps.dt.year==year]
        expected = coverage['years'][str(year)]['accepted_hours']
        if part.timestamp.nunique()!=expected or len(part)!=expected*7:
            raise ValueError('Incomplete year or split')
        splits[split] = dict(year=year, rows=len(part), hours=expected,
                             first=part.timestamp.min(), last=part.timestamp.max())
    if len(df)!=sum(s['rows'] for s in splits.values()):
        raise ValueError('Unexpected split year')
    if len(physics)!=len(df):
        raise ValueError('Missing physics diagnostics')
    for row, diag in zip(df.to_dict('records'), physics):
        if (row['timestamp'],row['panel_angle_deg'])!=(diag['timestamp'],diag['panel_angle_deg']) or row['actual_kwh']!=diag['ac_w']/1000:
            raise ValueError('Physics/label mismatch')
    night = df.sun_elevation_deg<=0
    if (df.loc[night,'actual_kwh']!=0).any():
        raise ValueError('Nonzero nighttime output')
    if df.actual_kwh.max()*1000 > pv_metadata()['inverter_ac_w']+1e-6:
        raise ValueError('Inverter ceiling exceeded')
    clipped = sum(d['clipped'] for d in physics)
    correlations = {name: (df[name].corr(df.actual_kwh)
                          if df[name].nunique()>1 and df.actual_kwh.nunique()>1 else None)
                    for name in ('ghi_wm2','dni_wm2','dhi_wm2','sun_elevation_deg',
                                 'panel_angle_deg','temperature_c','cloud_cover_pct')}
    return dict(status='PASS', row_count=len(df), schema=list(df.columns), missing_values=0,
        duplicate_pairs=0, target_excluded_from_features=True, split_overlap=0,
        fixed_physics_parameters_not_fitted=True, exclusion_provenance=exclusion_provenance(coverage),
        actual_kwh=dict(min=float(df.actual_kwh.min()), median=float(df.actual_kwh.median()),
                        mean=float(df.actual_kwh.mean()), max=float(df.actual_kwh.max())),
        nighttime_rows=int(night.sum()), nighttime_nonzero=0,
        daytime_zero=int(((~night)&(df.actual_kwh==0)).sum()),
        clipping_rows=clipped, clipping_pct=100*clipped/len(df), maximum_ac_w=float(df.actual_kwh.max()*1000),
        mean_by_angle={str(k):float(v) for k,v in df.groupby('panel_angle_deg').actual_kwh.mean().items()},
        mean_by_month=df.groupby(df.timestamp.str[:7]).actual_kwh.mean().to_dict(),
        mean_by_year=df.groupby(df.timestamp.str[:4]).actual_kwh.mean().to_dict(),
        pearson_target_correlations={k:None if pd.isna(v) else float(v) for k,v in correlations.items()}), splits


def handoff_text():
    return '''# Calgary fixed-GEM historical modeling dataset

Use train.csv (2023), validation.csv (2024), test.csv (2025). full_dataset.csv
contains their chronological union; do not randomly split it.

Target: actual_kwh, physics-derived AC kWh for one 20-panel row over one hour.
This is NOT measured solar-farm production. Models learn a reference simulation.

Features: temperature_c, cloud_cover_pct, precipitation_mm, wind_speed_kmh,
wind_gust_kmh, ghi_wm2, dni_wm2, dhi_wm2, sun_elevation_deg, sun_azimuth_deg,
panel_angle_deg. Never include actual_kwh as an inference feature.

Timestamp: UTC interval start, for chronological ordering/grouping. Do NOT
automatically treat it as a raw numeric feature. Keep all seven tilt variants
of an hour together. Build any temporal sequences on actual hourly timestamps,
not on the seven successive angle rows as though they were successive hours.

Policy A excludes 54 complete weather hours (378 angle rows) with invalid
negative GHI/DHI. These small timestamp gaps are intentional. Sequence models
must respect actual timestamp continuity and pad missing history; neighboring
CSV rows are not necessarily consecutive physical hours. Raw provider caches
are preserved unchanged, with no interpolation, clamping or source substitution.
Exact exclusions, raw values and before/after coverage are in both manifest.json
and quality_report.json. Accepted hours: 8739 / 8768 / 8743; modeling rows:
61173 / 61376 / 61201 (183750 total).

Fit preprocessing only on training data. Tune with training and validation;
do not fit preprocessing on validation/test. Keep test held out of all tuning.
Generation uses fixed approved physics parameters, not fitted parameters.

Read manifest.json, quality_report.json, split_summary.json.
The manifest records source hashes, assumptions and limitations. Verify byte
hashes without converting line endings. Raw provider caches are not ML features.
Unknown forecast issuance is allowed only for offline historical validation;
operational freshness policy is unchanged. Gust below wind is a nonblocking
diagnostic because the fields have different temporal semantics.
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-only', action='store_true')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    observations, sources, coverage = audit(ROOT, args.offline)
    if coverage['status'] != 'PASS':
        raise SystemExit('NOT READY: coverage gate failed. Inspect coverage_report.json; no canonical CSVs published.')
    if not args.audit_only:
        generate(ROOT, observations, sources, coverage)


if __name__ == '__main__':
    main()
