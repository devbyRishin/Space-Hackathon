from fastapi import APIRouter
from ..models.schemas import ManeuverRequest, ManeuverResponse, ManeuverValidation
from ..core.state import sim_state, DRY_MASS, INITIAL_FUEL
from ..core.physics import check_los, compute_fuel_consumed
from ..core.state import GROUND_STATIONS
import numpy as np

router = APIRouter()

@router.post("/api/maneuver/schedule", response_model=ManeuverResponse)
async def schedule_maneuver(req: ManeuverRequest):
    sat = sim_state.satellites.get(req.satelliteId)
    if not sat:
        return ManeuverResponse(
            status="REJECTED",
            validation=ManeuverValidation(
                ground_station_los=False,
                sufficient_fuel=False,
                projected_mass_remaining_kg=0.0
            )
        )

    sat_r = np.array(sat['r'])
    los = any(check_los(sat_r, gs) for gs in GROUND_STATIONS)
    fuel_kg = sat.get('fuel_kg', INITIAL_FUEL)
    total_dv = sum(
        np.linalg.norm([b.deltaV_vector.x, b.deltaV_vector.y, b.deltaV_vector.z])
        for b in req.maneuver_sequence
    )
    current_mass = DRY_MASS + fuel_kg
    fuel_needed = compute_fuel_consumed(current_mass, total_dv)
    sufficient = fuel_kg >= fuel_needed

    if sufficient:
        for burn in req.maneuver_sequence:
            sim_state.maneuver_queue.append({
                'satellite_id': req.satelliteId,
                'burn': {
                    'burn_id': burn.burn_id,
                    'burn_time_offset': 300,
                    'deltaV_eci': [burn.deltaV_vector.x, burn.deltaV_vector.y, burn.deltaV_vector.z]
                },
                'scheduled': True
            })
        sat['fuel_kg'] = max(0, fuel_kg - fuel_needed)

    return ManeuverResponse(
        status="SCHEDULED" if sufficient else "REJECTED",
        validation=ManeuverValidation(
            ground_station_los=los,
            sufficient_fuel=sufficient,
            projected_mass_remaining_kg=DRY_MASS + max(0, fuel_kg - fuel_needed)
        )
    )