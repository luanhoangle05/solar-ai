"""Offline tests for fixed-model cache identity, coverage and publication gates."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from scripts import build_full_dataset as full
from tests.pipeline.test_open_meteo import provider_fixture


class FullDatasetTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        self.end = self.start + timedelta(hours=1)
        self.payload = provider_fixture()
        self.payload['hourly']['time'] = [int(self.start.timestamp()), int(self.end.timestamp())]
        self.meta = {'fetched_at': '2026-10-01T00:00:00Z'}

    def test_month_boundaries_leap_year_and_terminal_hour(self):
        chunks = list(full.months())
        self.assertEqual(len(chunks),36)
        self.assertEqual(chunks[-1][1],datetime(2026,1,1,tzinfo=timezone.utc))
        self.assertTrue(all(a[1]==b[0] for a,b in zip(chunks,chunks[1:])))
        hours = {year:sum(int((b-a)/full.HOUR) for a,b in chunks if a.year==year) for year in full.YEARS}
        self.assertEqual(hours,{2023:8760,2024:8784,2025:8760})
        params = full.parameters(*chunks[0])
        self.assertEqual(params['models'],'gem_seamless')
        self.assertEqual(params['end_hour'],'2023-02-01T00:00')
        self.assertEqual(params['latitude'],full.DEMO_LATITUDE_DEG)

    def test_cache_resumes_without_network_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            response=Mock(status_code=200,content=json.dumps(self.payload).encode())
            with patch.object(full.requests,'get',return_value=response) as get:
                first=full.acquire(root,self.start,self.end)
                self.assertEqual(full.acquire(root,self.start,self.end,offline=True),first)
                get.assert_called_once()
                self.assertFalse(get.call_args.kwargs['allow_redirects'])
            response.close.assert_called_once()
            (root/'provider_responses/2023-01.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'integrity'):
                full.acquire(root,self.start,self.end)

    def test_cache_identity_and_partial_pair_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            response=Mock(status_code=200,content=json.dumps(self.payload).encode())
            with patch.object(full.requests,'get',return_value=response):
                full.acquire(root,self.start,self.end)
            with self.assertRaisesRegex(ValueError,'identity'):
                full.acquire(root,self.start,self.end+full.HOUR)
            (root/'provider_responses/2023-01.metadata.json').unlink()
            with self.assertRaisesRegex(ValueError,'Incomplete'):
                full.acquire(root,self.start,self.end)

    def test_http_failure_is_not_cached_and_offline_never_downloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            response=Mock(status_code=429)
            with patch.object(full.requests,'get',return_value=response) as get:
                with self.assertRaisesRegex(ValueError,'429'):
                    full.acquire(root,self.start,self.end)
                with self.assertRaisesRegex(ValueError,'offline'):
                    full.acquire(root,self.start,self.end,offline=True)
                self.assertEqual(get.call_count,1)
            self.assertEqual(list((root/'provider_responses').iterdir()),[])
            response.close.assert_called_once()

    def test_mapping_unchanged_and_gust_order_nonblocking(self):
        self.payload['hourly']['wind_speed_10m'][0]=15
        self.payload['hourly']['wind_gusts_10m'][1]=8
        rows,report=full.audit_chunk(self.payload,self.meta,self.start,self.end)
        self.assertEqual(report['accepted_hours'],1)
        self.assertEqual(report['wind_gust_diagnostic_hours'],1)
        self.assertEqual(rows[0]['ghi_wm2'],850)
        self.assertEqual(rows[0]['wind_gust_kmh'],8)

    def test_null_ranges_missing_terminal_and_duplicates_block(self):
        for mutation in ('null','negative','irradiance','cloud','terminal','duplicate'):
            with self.subTest(mutation=mutation):
                p=deepcopy(self.payload)
                if mutation=='null': p['hourly']['shortwave_radiation'][1]=None
                if mutation=='negative': p['hourly']['wind_speed_10m'][0]=-1
                if mutation=='irradiance': p['hourly']['shortwave_radiation'][1]=-0.5
                if mutation=='cloud': p['hourly']['cloud_cover'][0]=101
                if mutation=='terminal':
                    for values in p['hourly'].values(): values.pop()
                if mutation=='duplicate': p['hourly']['time'][1]=p['hourly']['time'][0]
                rows,report=full.audit_chunk(p,self.meta,self.start,self.end)
                self.assertEqual(rows,[])
                self.assertEqual(report['hard_validation_failures'],1)
                if mutation=='duplicate': self.assertEqual(report['duplicate_timestamps'],1)
                if mutation=='null': self.assertEqual(report['invalid_required_value_counts']['ghi_wm2'],1)

    def test_missing_gap_and_failed_chunk_report_no_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(full,'months',return_value=iter([(self.start,self.end)])), \
                 patch.object(full,'YEARS',(2023,)), \
                 patch.object(full,'acquire',side_effect=ValueError('Missing cache in offline mode')):
                rows,sources,report=full.audit(root,offline=True)
            self.assertEqual(report['status'],'NOT READY')
            self.assertEqual(report['years']['2023']['missing_hours'],1)
            self.assertEqual(report['years']['2023']['longest_unusable_gap_hours'],1)
            self.assertEqual(len(report['failed_chunks']),1)
            with self.assertRaisesRegex(ValueError,'Coverage gate'):
                full.generate(root,rows,sources,report)
            self.assertFalse((root/'full_dataset.csv').exists())

    def test_gap_ranges_cross_month_boundary(self):
        start=datetime(2024,1,31,23,tzinfo=timezone.utc)
        gaps=full.gap_ranges([start,start+full.HOUR,start+3*full.HOUR])
        self.assertEqual([g['hours'] for g in gaps],[2,1])

    def test_publication_guard_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'train.csv').write_text('preserve')
            with self.assertRaisesRegex(ValueError,'already exists'):
                full.generate(root,[],[],{'status':'PASS'})
            self.assertEqual((root/'train.csv').read_text(),'preserve')

    def test_handoff_leakage_guidance(self):
        text=full.handoff_text()
        for expected in ('Never include actual_kwh','Fit preprocessing only on training data',
                         'Keep test held out','NOT measured','Do NOT'):
            self.assertIn(expected,text)

    def small_complete_fixture(self):
        observations=[]
        coverage={'status':'PASS','years':{str(y):{'expected_hours':1,'accepted_hours':1} for y in full.YEARS}}
        for year in full.YEARS:
            start=datetime(year,1,1,tzinfo=timezone.utc)
            payload=deepcopy(self.payload)
            payload['hourly']['time']=[int(start.timestamp()),int((start+full.HOUR).timestamp())]
            rows,_=full.audit_chunk(payload,self.meta,start,start+full.HOUR)
            observations.extend(rows)
        return observations,coverage

    def test_small_end_to_end_exports_hashes_splits_and_determinism(self):
        observations,coverage=self.small_complete_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            full.generate(root,observations,[],coverage)
            manifest=json.loads((root/'manifest.json').read_text())
            for name,sha in manifest['output_sha256'].items():
                self.assertEqual(full.digest((root/name).read_bytes()),sha)
            self.assertEqual(len(pd.read_csv(root/'full_dataset.csv')),21)
            for name in ('train','validation','test'):
                self.assertEqual(len(pd.read_csv(root/f'{name}.csv')),7)
            quality=json.loads((root/'quality_report.json').read_text())
            self.assertTrue(quality['deterministic_full_regeneration'])
            self.assertTrue(quality['target_excluded_from_features'])
            self.assertEqual(quality['split_overlap'],0)

    def test_quality_rejects_duplicates_wrong_schema_and_angle_groups(self):
        observations,coverage=self.small_complete_fixture()
        rows,physics=[],[]
        for weather in observations:
            r,p=full.expand_hour(weather,full.DEMO_LATITUDE_DEG,full.DEMO_LONGITUDE_DEG)
            rows.extend(r); physics.extend(p)
        frame=pd.DataFrame(rows,columns=full.WEATHER_COLUMNS)
        for bad in (pd.concat([frame,frame.iloc[:1]],ignore_index=True),
                    frame.drop(columns=['actual_kwh']),frame.iloc[1:]):
            with self.assertRaises(ValueError):
                full.check_rows(bad,physics,coverage)

    def test_policy_a_preserves_raw_values_and_rejects_other_failures(self):
        for extra in (None, 'wind_speed_10m', 'direct_normal_irradiance'):
            with self.subTest(extra=extra):
                payload=deepcopy(self.payload)
                payload['hourly']['shortwave_radiation'][1]=-0.5
                payload['hourly']['diffuse_radiation'][1]=-46
                if extra:
                    payload['hourly'][extra]=[-1,-1]
                original=deepcopy(payload)
                rows,report=full.audit_chunk(payload,self.meta,self.start,self.end)
                self.assertEqual(rows,[])
                self.assertEqual(payload,original)
                exclusion=report['exclusions'][0]
                self.assertEqual(exclusion['policy_a_eligible'],extra is None)
                self.assertEqual(exclusion['raw_ghi_wm2'],-0.5)
                self.assertEqual(exclusion['raw_dhi_wm2'],-46)
                self.assertEqual(exclusion['timestamp'],'2023-01-01T00:00:00Z')
                self.assertEqual(exclusion['month'],'2023-01')

    def test_policy_gate_exact_counts_and_other_failures(self):
        reports=[]
        yearly={}
        for start,end in full.months():
            count=int((end-start)/full.HOUR)
            excluded=({2023:21,2024:16,2025:17}[start.year] if start.month==1 else 0)
            reports.append(dict(expected_hours=count,retrieved_hours=count,duplicate_timestamps=0,
                invalid_required_value_counts={},accepted_hours=count-excluded,
                exclusions=[dict(timestamp=full.stamp(start+i*full.HOUR),policy_a_eligible=True)
                            for i in range(excluded)]))
            yearly.setdefault(str(start.year),dict(accepted_hours=0))['accepted_hours']+=count-excluded
        self.assertTrue(full.publication_allowed(reports,yearly,[]))
        for mutation in ('count','reason','null','duplicate','missing','failed','duplicate_exclusion'):
            with self.subTest(mutation=mutation):
                r,y=deepcopy(reports),deepcopy(yearly)
                failures=[]
                if mutation=='count': y['2023']['accepted_hours']-=1
                if mutation=='reason': r[0]['exclusions'][0]['policy_a_eligible']=False
                if mutation=='null': r[0]['invalid_required_value_counts']={'ghi_wm2':1}
                if mutation=='duplicate': r[0]['duplicate_timestamps']=1
                if mutation=='missing': r[0]['retrieved_hours']-=1
                if mutation=='failed': failures=['HTTP failure']
                if mutation=='duplicate_exclusion': r[0]['exclusions'][1]=r[0]['exclusions'][0]
                self.assertFalse(full.publication_allowed(r,y,failures))

    def test_exclusion_provenance_and_no_angle_rows_for_rejected_hour(self):
        observations,coverage=self.small_complete_fixture()
        rejected='2023-01-01T01:00:00Z'
        exclusion=dict(timestamp=rejected,reason='ghi_wm2: cannot be negative',
                       raw_ghi_wm2=-1,raw_dhi_wm2=0,year=2023,month='2023-01',policy_a_eligible=True)
        coverage['months']=[dict(exclusions=[exclusion])]
        coverage['years']['2023']['expected_hours']=2
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            full.generate(root,observations,[],coverage)
            frame=pd.read_csv(root/'full_dataset.csv')
            self.assertNotIn(rejected,frame.timestamp.values)
            manifest=json.loads((root/'manifest.json').read_text())
            quality=json.loads((root/'quality_report.json').read_text())
            provenance=quality['exclusion_provenance']
            self.assertEqual(provenance,manifest['exclusion_provenance'])
            self.assertEqual(provenance['rows_lost'],7)
            self.assertEqual(provenance['exclusions'],[exclusion])
            self.assertEqual(provenance['coverage_by_year']['2023']['after_exclusion_pct'],50)
        rows,physics=[],[]
        for weather in observations:
            r,p=full.expand_hour(weather,full.DEMO_LATITUDE_DEG,full.DEMO_LONGITUDE_DEG)
            rows.extend(r); physics.extend(p)
        coverage['months'][0]['exclusions'][0]['timestamp']=rows[0]['timestamp']
        with self.assertRaisesRegex(ValueError,'Excluded weather hour'):
            full.check_rows(pd.DataFrame(rows,columns=full.WEATHER_COLUMNS),physics,coverage)


if __name__=='__main__':
    unittest.main()
