"""Owner: Duy. Movement cost and net benefit in kWh-equivalent per row per hour.

Every coefficient comes from `SimulationConfig` (PROTOTYPE SIMULATION
ASSUMPTIONS). Nothing here is hardware-calibrated and nothing is in currency.
"""

from src.common.config import SimulationConfig
from src.common.tool_contracts import MovementCost


def calculate_movement_cost(current_angle_deg: float, target_angle_deg: float, *, config: SimulationConfig) -> MovementCost:
    """Motor energy plus wear for moving one row between two tilt angles."""
    movement_degrees = abs(target_angle_deg - current_angle_deg)
    motor_energy_kwh = movement_degrees * config.motor_kwh_per_degree
    wear_kwh_equivalent = movement_degrees * config.wear_kwh_equivalent_per_degree
    return {
        "movement_degrees": movement_degrees,
        "motor_energy_kwh": motor_energy_kwh,
        "wear_kwh_equivalent": wear_kwh_equivalent,
        "movement_cost_kwh_equivalent": motor_energy_kwh + wear_kwh_equivalent,
    }


def calculate_net_benefit(energy_gain_kwh: float, movement_cost_kwh_equivalent: float) -> float:
    return energy_gain_kwh - movement_cost_kwh_equivalent
