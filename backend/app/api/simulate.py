from fastapi import APIRouter
from ..models.schemas import SimStepRequest, SimStepResponse
from ..core.state import sim_state, CONJUNCTION_THRESHOLD
from ..core.physics import propagate
from ..core.scheduler import execute_due_maneuvers, run_conjunction_assessment, update_station_keeping
from datetime import timedelta
import numpy as np
from loguru import logger

router = APIRouter()

@router.post("/api/simulate/step", response_model=SimStepResponse)
async def simulate_step(req: SimStepRequest):
    dt = req.step_seconds
    collisions = 0

    for sat_id, sat in sim_state.satellites.items():
        r, v = propagate(sat.r, sat.v, dt)
        sat.r = r
        sat.v = v

    for deb_id, deb in sim_state.debris.items():
        r, v = propagate(deb['r'], deb['v'], dt)
        deb['r'] = r
        deb['v'] = v

    for sat_id, sat in sim_state.satellites.items():
        for deb_id, deb in sim_state.debris.items():
            dist = float(np.linalg.norm(sat.r - deb['r']))
            if dist < CONJUNCTION_THRESHOLD:
                collisions += 1
                sim_state.collision_count += 1
                logger.critical(f"COLLISION: {sat_id} vs {deb_id} dist={dist:.4f}km")

    executed = execute_due_maneuvers(dt)
    update_station_keeping(dt)
    run_conjunction_assessment()

    sim_state.sim_elapsed += dt
    sim_state.current_time += timedelta(seconds=dt)

    logger.info(f"Step {dt}s complete — collisions={collisions} maneuvers={executed}")

    return SimStepResponse(
        status="STEP_COMPLETE",
        new_timestamp=sim_state.current_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        collisions_detected=collisions,
        maneuvers_executed=executed
    )