import unittest
from unittest.mock import patch

from typing import get_type_hints
from src.common.schema import WEATHER_COLUMNS, WeatherFeatures, validate_weather_row
from src.pipeline.reference_pv import (REFERENCE_PV, ac_from_poa, expand_hour,
                                       pv_metadata, split_for_timestamp)
from tests.pipeline.weather_fixtures import weather_fixture


class ReferencePVTests(unittest.TestCase):
    def test_sizing_and_provenance(self):
        self.assertEqual(REFERENCE_PV.row_dc_w, 10000)
        self.assertAlmostEqual(REFERENCE_PV.inverter_ac_w, 9090.909090909)
        self.assertAlmostEqual(REFERENCE_PV.inverter_pdc0_w * .96, REFERENCE_PV.inverter_ac_w)
        self.assertEqual(pv_metadata()['label_source'], 'physics_derived_pvwatts_ac')

    def test_power_temperature_and_clipping(self):
        low = ac_from_poa(200, 20, 10)
        high = ac_from_poa(800, 20, 10)
        hot = ac_from_poa(800, 40, 10)
        self.assertGreater(high['ac_w'], low['ac_w'])
        self.assertLess(hot['ac_w'], high['ac_w'])
        self.assertTrue(ac_from_poa(2000, -10, 30)['clipped'])
        self.assertEqual(ac_from_poa(0, 20, 10)['ac_w'], 0)
        self.assertAlmostEqual(high['net_dc_w'], high['dc_w'] * .86)

    def test_expansion_schema_reuse_repeatability_and_target_exclusion(self):
        solar = {'sun_elevation_deg': 45, 'sun_azimuth_deg': 180}
        with patch('src.pipeline.reference_pv.calculate_solar_position', return_value=solar) as calculate:
            first = expand_hour(weather_fixture(), 51.0447, -114.0719)
            calculate.assert_called_once()
            second = expand_hour(weather_fixture(), 51.0447, -114.0719)
        self.assertEqual(first, second)
        rows, diagnostics = first
        self.assertEqual(len(rows), 7)
        self.assertEqual(len({(r['timestamp'],r['panel_angle_deg']) for r in rows}), 7)
        self.assertEqual(len({r['timestamp'] for r in rows}), 1)
        for row in rows:
            self.assertEqual(tuple(row), tuple(WEATHER_COLUMNS))
            validate_weather_row(row)
            self.assertGreaterEqual(row['actual_kwh'], 0)
        self.assertNotIn('actual_kwh', get_type_hints(WeatherFeatures))

    def test_night_and_year_boundaries(self):
        with patch('src.pipeline.reference_pv.calculate_solar_position', return_value={'sun_elevation_deg': -5, 'sun_azimuth_deg': 0}):
            rows, _ = expand_hour(weather_fixture(), 51.0447, -114.0719)
        self.assertTrue(all(row['actual_kwh'] == 0 for row in rows))
        self.assertEqual(split_for_timestamp('2023-12-31T23:00:00Z'), 'train')
        self.assertEqual(split_for_timestamp('2024-01-01T00:00:00Z'), 'validation')
        self.assertEqual(split_for_timestamp('2025-01-01T00:00:00Z'), 'test')
