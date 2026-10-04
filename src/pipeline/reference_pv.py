"""Approved reference-row simulation, not measured production or a real installation."""
from dataclasses import asdict, dataclass
from datetime import timedelta
import math

import pvlib

from src.common.config import DEFAULT_CONFIG, PANELS_PER_ROW
from src.common.schema import WEATHER_COLUMNS, validate_weather_row
from src.common.tool_contracts import WeatherRequest, ToolError
from src.pipeline.solar_position import calculate_solar_position
from src.pipeline.transform import transform_weather
from src.pipeline.validate import _parse_timestamp


@dataclass(frozen=True)
class ReferencePVConfig:
    panels: int = PANELS_PER_ROW
    panel_dc_w: float = 500
    surface_azimuth_deg: float = 180
    albedo: float = 0.20
    gamma_pdc: float = -0.0035
    dc_ac_ratio: float = 1.10
    inverter_efficiency: float = 0.96
    system_loss_fraction: float = 0.14
    temperature_parameters: str = "open_rack_glass_glass"

    @property
    def row_dc_w(self):
        return self.panels * self.panel_dc_w

    @property
    def inverter_ac_w(self):
        return self.row_dc_w / self.dc_ac_ratio

    @property
    def inverter_pdc0_w(self):
        return self.inverter_ac_w / self.inverter_efficiency


REFERENCE_PV = ReferencePVConfig()


def ac_from_poa(poa, ambient_c, wind_kmh, config=REFERENCE_PV):
    """Apply loss once to DC before inverter. No separate ModelChain loss pass."""
    cell = float(pvlib.temperature.sapm_cell(
        poa, ambient_c, wind_kmh / 3.6,
        **pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm'][config.temperature_parameters]))
    dc = max(0.0, float(pvlib.pvsystem.pvwatts_dc(poa, cell, config.row_dc_w, config.gamma_pdc)))
    net_dc = dc * (1 - config.system_loss_fraction)
    ac = max(0.0, float(pvlib.inverter.pvwatts(net_dc, config.inverter_pdc0_w,
                                          eta_inv_nom=config.inverter_efficiency)))
    if not all(math.isfinite(x) for x in (cell, dc, net_dc, ac)):
        raise ToolError('Nonfinite reference PV output')
    return dict(cell_temperature_c=cell, dc_w=dc, net_dc_w=net_dc, ac_w=ac,
                clipped=math.isclose(ac, config.inverter_ac_w, abs_tol=1e-6))


def expand_hour(weather, latitude, longitude, config=REFERENCE_PV):
    request = WeatherRequest(latitude, longitude, weather['timestamp'], 60)
    solar = calculate_solar_position(request)
    midpoint = _parse_timestamp(weather['timestamp'], 'timestamp') + timedelta(minutes=30)
    extra = float(pvlib.irradiance.get_extra_radiation(midpoint))
    rows, diagnostics = [], []
    for angle in DEFAULT_CONFIG.candidate_angles_deg:
        features = transform_weather(weather, solar, panel_angle_deg=angle)
        if solar['sun_elevation_deg'] <= 0:
            poa = 0.0
        else:
            components = pvlib.irradiance.get_total_irradiance(
                angle, config.surface_azimuth_deg, 90 - solar['sun_elevation_deg'],
                solar['sun_azimuth_deg'], weather['dni_wm2'], weather['ghi_wm2'],
                weather['dhi_wm2'], dni_extra=extra, albedo=config.albedo, model='haydavies')
            poa = max(0.0, float(components['poa_global']))
        if not math.isfinite(poa):
            raise ToolError('Nonfinite plane-of-array irradiance')
        physics = ac_from_poa(poa, weather['temperature_c'], weather['wind_speed_kmh'], config)
        row = dict(features, actual_kwh=physics['ac_w'] / 1000)  # exactly one hour
        validate_weather_row(row)
        rows.append({name: row[name] for name in WEATHER_COLUMNS})
        diagnostics.append(dict(timestamp=row['timestamp'], panel_angle_deg=angle,
                                poa_wm2=poa, sun_elevation_deg=solar['sun_elevation_deg'], **physics))
    return rows, diagnostics


def split_for_timestamp(timestamp):
    year = _parse_timestamp(timestamp, 'timestamp').year
    if year not in (2023, 2024, 2025):
        raise ToolError('Timestamp outside approved split years')
    return {2023: 'train', 2024: 'validation', 2025: 'test'}[year]


def pv_metadata():
    return dict(asdict(REFERENCE_PV), row_dc_w=REFERENCE_PV.row_dc_w,
                inverter_ac_w=REFERENCE_PV.inverter_ac_w,
                inverter_pdc0_w=REFERENCE_PV.inverter_pdc0_w,
                transposition='haydavies', dc_model='pvwatts_dc', ac_model='pvwatts',
                pvlib_version=pvlib.__version__, label_source='physics_derived_pvwatts_ac',
                temperature_coefficients=pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass'])
