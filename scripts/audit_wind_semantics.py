"""Bounded fixed-GEM audit. Produces diagnostics only, never ML labels."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import requests

from src.common.config import DEMO_LATITUDE_DEG, DEMO_LONGITUDE_DEG
from src.pipeline.client import VARIABLES, _map_response
from src.pipeline.validate import _inspect_weather

ENDPOINT = 'https://historical-forecast-api.open-meteo.com/v1/forecast'
MODEL = 'gem_seamless'
WINDOWS = (('2023-01-15',7), ('2023-04-15',7), ('2023-07-15',7),
           ('2023-10-15',7), ('2024-01-15',1), ('2025-01-15',1))
ROOT = Path(__file__).resolve().parents[1] / 'data/generated/gem_wind_audit'
RELATION = 'wind_gust_kmh: below sustained wind_speed_kmh'


def distribution(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return {'count': 0}
    negative = values[values < 0]
    return dict(count=len(values), below_zero=int(len(negative)),
                fraction_below_zero=float(len(negative)/len(values)),
                quantiles_kmh=dict(zip(('min','p05','p25','median','p75','p95','max'),
                                      map(float,np.quantile(values,[0,.05,.25,.5,.75,.95,1])))),
                negative_bins={'[-0.1,0)': int(np.sum((values >= -.10000001)&(values < 0))),
                               '[-1,-0.1)':int(np.sum((values >= -1)&(values < -.10000001))),
                               '[-5,-1)':int(np.sum((values >= -5)&(values < -1))),
                               'below_-5':int(np.sum(values < -5))})


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    results=[]
    for day, days in WINDOWS:
        start=datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
        stop=start+timedelta(days=days)
        params=dict(latitude=DEMO_LATITUDE_DEG, longitude=DEMO_LONGITUDE_DEG,
                    hourly=','.join(VARIABLES), timezone='UTC', timeformat='unixtime',
                    temperature_unit='celsius', wind_speed_unit='kmh', precipitation_unit='mm',
                    models=MODEL, start_hour=start.strftime('%Y-%m-%dT%H:%M'),
                    end_hour=stop.strftime('%Y-%m-%dT%H:%M'))
        raw=ROOT/(day+'.json'); meta=ROOT/(day+'.metadata.json')
        if raw.exists() and meta.exists():
            content=raw.read_bytes(); provenance=json.loads(meta.read_text())
            if provenance['params']!=params or provenance['sha256']!=hashlib.sha256(content).hexdigest():
                raise RuntimeError('Audit cache integrity mismatch')
        else:
            with requests.get(ENDPOINT,params=params,timeout=40,allow_redirects=False) as response:
                response.raise_for_status(); content=response.content
            provenance=dict(params=params,endpoint=ENDPOINT,fetched_at=datetime.now(timezone.utc).isoformat(),
                            sha256=hashlib.sha256(content).hexdigest())
            raw.write_bytes(content); meta.write_text(json.dumps(provenance,indent=2),encoding='utf-8')
        payload=json.loads(content); hourly=payload.get('hourly',{})
        counts=Counter(); rejected=[]; differences={'A_start_wind_end_gust':[], 'B_start_same_timestamp':[], 'B_end_same_timestamp':[]}
        times=hourly.get('time',[]); index={t:i for i,t in enumerate(times)}
        nulls=Counter(); missing=Counter()
        for offset in range(days*24):
            t=start+timedelta(hours=offset); e=t+timedelta(hours=1)
            for name,(_,_,aggregate) in VARIABLES.items():
                values=hourly.get(name)
                if values is None:
                    missing[name]+=1
                else:
                    i=index.get(int((e if aggregate else t).timestamp()))
                    if i is not None and i<len(values) and values[i] is None: nulls[name]+=1
            try:
                weather=_map_response(payload,t,e,datetime.fromisoformat(provenance['fetched_at']), 'open-meteo-gem-historical')
                issues,_=_inspect_weather(weather)
                for issue in issues: counts[issue]+=1
                if issues: rejected.append(dict(timestamp=t.isoformat(),issues=issues))
            except (ValueError,RuntimeError) as exc:
                counts[str(exc)]+=1; rejected.append(dict(timestamp=t.isoformat(),issues=[str(exc)]))
            a=index.get(int(t.timestamp())); b=index.get(int(e.timestamp()))
            if a is not None and b is not None:
                wind=hourly.get('wind_speed_10m',[]); gust=hourly.get('wind_gusts_10m',[])
                for name, wi, gi in (('A_start_wind_end_gust',a,b),('B_start_same_timestamp',a,a),('B_end_same_timestamp',b,b)):
                    if wi<len(wind) and gi<len(gust) and all(type(v) in (int,float) for v in (wind[wi],gust[gi])):
                        differences[name].append(gust[gi]-wind[wi])
        result=dict(start=day,end_exclusive=stop.isoformat(),total_intervals=days*24,
                    returned_timestamps=len(times), missing_field_counts=dict(missing),null_counts=dict(nulls),
                    rejected_by_rule=dict(counts), rejected_intervals=len(rejected),
                    rejected_only_by_wind_relation=sum(r['issues']==[RELATION] for r in rejected),
                    invalid_range_rule_counts={k:v for k,v in counts.items() if 'negative' in k or 'within' in k},
                    comparisons={k:distribution(v) for k,v in differences.items()},rejections=rejected,
                    returned_coordinates={k:payload.get(k) for k in ('latitude','longitude')})
        results.append(result)
        print(json.dumps({k:result[k] for k in ('start','total_intervals','missing_field_counts','null_counts','rejected_by_rule','rejected_only_by_wind_relation','comparisons')}),flush=True)
    (ROOT/'audit.json').write_text(json.dumps(dict(model=MODEL,probes=results,
          note='Bounded probes, not exhaustive multi-year coverage. No production mapping or validation changes.'),indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
