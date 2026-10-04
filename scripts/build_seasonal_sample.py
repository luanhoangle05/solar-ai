"""Bounded seasonal availability probe/sample only; never downloads full years."""
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import requests

from src.common.config import DEMO_LATITUDE_DEG, DEMO_LONGITUDE_DEG, DEFAULT_CONFIG
from src.common.schema import WEATHER_COLUMNS
from src.pipeline.client import VARIABLES, _map_response
from src.pipeline.reference_pv import expand_hour, pv_metadata, split_for_timestamp
from src.pipeline.validate import _inspect_weather
from scripts.audit_wind_semantics import WINDOWS, ROOT as AUDIT_ROOT, MODEL

ENDPOINT = 'https://historical-forecast-api.open-meteo.com/v1/forecast'
ROOT = Path(__file__).resolve().parents[1] / 'data' / 'generated' / 'gem_seasonal_sample'
SAMPLE_DATES = tuple(day for day, _ in WINDOWS)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    rows, diagnostics, exclusions, sources = [], [], [], []
    seen = set()
    diagnostic_hours = 0
    for day, days in WINDOWS:
        start = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
        end = start + timedelta(days=days)
        params = dict(latitude=DEMO_LATITUDE_DEG, longitude=DEMO_LONGITUDE_DEG,
                      hourly=','.join(VARIABLES), timezone='UTC', timeformat='unixtime',
                      temperature_unit='celsius', wind_speed_unit='kmh', precipitation_unit='mm',
                      models=MODEL, start_hour=start.strftime('%Y-%m-%dT%H:%M'), end_hour=end.strftime('%Y-%m-%dT%H:%M'))
        raw_path = AUDIT_ROOT / (day + '.json')
        meta_path = AUDIT_ROOT / (day + '.metadata.json')
        if raw_path.exists() and meta_path.exists():
            content = raw_path.read_bytes()
            source = json.loads(meta_path.read_text())
            source['request_parameters'] = source.pop('params')
            if source['request_parameters'] != params or source['sha256'] != hashlib.sha256(content).hexdigest():
                raise RuntimeError('Cached provider response integrity mismatch')
        else:
            raise RuntimeError('Run the bounded GEM audit first; sample generation never downloads data')
        payload = json.loads(content)
        source['sample_date'] = day
        source['null_counts'] = {k: sum(v is None for v in payload.get('hourly', {}).get(k, [])) for k in VARIABLES}
        source['returned_coordinates'] = {k: payload.get(k) for k in ('latitude', 'longitude')}
        source['hours_accepted'] = 0
        for hour in range(days * 24):
            instant = start + timedelta(hours=hour)
            try:
                weather = _map_response(payload, instant, instant+timedelta(hours=1),
                                        datetime.fromisoformat(source['fetched_at']), 'open-meteo-historical-forecast')
                issues, _ = _inspect_weather(weather)
                if issues:
                    raise ValueError('; '.join(issues))
            except (ValueError, RuntimeError) as exc:
                exclusions.append(dict(timestamp=instant.isoformat(), reason=str(exc)))
                continue
            if weather['timestamp'] in seen:
                raise RuntimeError('Duplicate interval')
            seen.add(weather['timestamp'])
            diagnostic_hours += int(weather['wind_gust_kmh'] < weather['wind_speed_kmh'])
            expanded, physics = expand_hour(weather, DEMO_LATITUDE_DEG, DEMO_LONGITUDE_DEG)
            rows.extend(expanded)
            diagnostics.extend(physics)
            source['hours_accepted'] += 1
        sources.append(source)
        print(day, 'accepted', source['hours_accepted'], '/', days*24, flush=True)
        if source['hours_accepted'] != days*24:
            (ROOT / 'coverage_blocker.json').write_text(json.dumps(dict(sources=sources, exclusions=exclusions), indent=2))
            raise SystemExit('STOP: sample contains hard quality failures. See coverage_blocker.json; no labeled CSV published.')
    for split in ('train', 'validation', 'test'):
        selected = [row for row in rows if split_for_timestamp(row['timestamp']) == split]
        with (ROOT / f'{split}_sample.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=WEATHER_COLUMNS)
            writer.writeheader()
            writer.writerows(selected)
    manifest = dict(site='Calgary, Alberta', latitude=DEMO_LATITUDE_DEG, longitude=DEMO_LONGITUDE_DEG,
        weather_source='real archived operational forecast-model data; not station measurements', historical_model=MODEL,
        energy_label_source='physics-derived / pvlib simulation', reference_system=pv_metadata(),
        label_source='physics_derived_pvwatts_ac', target='AC kWh per 20-panel row per one-hour interval',
        candidate_angles=list(DEFAULT_CONFIG.candidate_angles_deg), sample_dates=SAMPLE_DATES,
        split_boundaries={'train': '2023 UTC', 'validation': '2024 UTC', 'test': '2025 UTC'},
        generation_timestamp=datetime.now(timezone.utc).isoformat(), row_count=len(rows),
        hourly_observations=len(seen), missing_data_exclusions=exclusions, sources=sources,
        wind_order_diagnostic_hours=diagnostic_hours,
        coverage_status='Seasonal probes only; exhaustive 2023–2025 completeness NOT verified. Full download not authorized.',
        limitations=['Reference simulated PV row, not a real farm', 'No dynamic snow, shading, soiling, bifacial or degradation',
            'Fixed 14% generic loss applied once to DC', 'No separate spectral or incidence-angle optical model; POA used as effective irradiance',
            'Hourly mean radiation with midpoint sun position; sunrise/sunset approximation; midpoint below horizon forces zero',
            'Model accuracy measures agreement with physics simulation, not measured production',
            'Archived stitched forecasts do not preserve a fixed forecast lead time',
            'Unknown issue time allowed for historical offline quality checks; operational freshness policy unchanged'],
        max_ac_w=max(d['ac_w'] for d in diagnostics), clipping_count=sum(d['clipped'] for d in diagnostics),
        actual_kwh_statistics=dict(min=min(r['actual_kwh'] for r in rows),
                                   mean=sum(r['actual_kwh'] for r in rows)/len(rows),
                                   max=max(r['actual_kwh'] for r in rows)),
        nighttime_max_kwh=max((d['ac_w']/1000 for d in diagnostics if d['sun_elevation_deg']<=0), default=0),
        csv_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('*_sample.csv')})
    (ROOT/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (ROOT/'physics_diagnostics.json').write_text(json.dumps(diagnostics, indent=2), encoding='utf-8')
    print(json.dumps({k:manifest[k] for k in ('row_count','hourly_observations','max_ac_w','clipping_count','nighttime_max_kwh','coverage_status')}, indent=2))


if __name__ == '__main__':
    main()
