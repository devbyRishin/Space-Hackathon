import numpy as np
from datetime import timedelta
from .physics import check_los, propagate, COOLDOWN, FUEL_EOL_THRESHOLD
from .state import GROUND_STATIONS, sim_state
from .cola import (compute_optimal_evasion, compute_optimal_recovery,
                   compute_graveyard_burn, apply_burn_to_satellite)
from .kdtree import find_conjunctions
from loguru import logger

def satellite_has_los(sat):
    return any(check_los(sat.r, gs) for gs in GROUND_STATIONS)

def precheck_blackout_window(sat, burn_offset):
    for t in range(0, int(burn_offset), 300):
        r_prop, _ = propagate(sat.r, sat.v, t)
        if any(check_los(r_prop, gs) for gs in GROUND_STATIONS):
            return True, t
    return False, 0

def run_conjunction_assessment():
    warnings = find_conjunctions(sim_state.satellites, sim_state.debris)
    sim_state.cdm_warnings = warnings

    for w in warnings:
        sat_id = w['sat_id']
        sat = sim_state.satellites.get(sat_id)
        if not sat:
            continue

        already_scheduled = any(
            m['satellite_id'] == sat_id and
            m['burn'].get('type') == 'EVASION' and
            w['deb_id'] in m['burn'].get('burn_id', '')
            for m in sim_state.maneuver_queue
        )
        if already_scheduled:
            continue

        if sat.fuel_pct <= FUEL_EOL_THRESHOLD:
            if sat.status != 'EOL':
                logger.warning(f"{sat_id} fuel critical — scheduling graveyard burn")
                burn = compute_graveyard_burn(sat)
                _enqueue(sat_id, burn)
                sat.status = 'EOL'
            continue

        if not w['critical'] and w['miss_distance_km'] > 1.0:
            continue

        logger.info(f"CDM: {sat_id} vs {w['deb_id']} miss={w['miss_distance_km']:.3f}km tca={w['tca_seconds']}s")

        evasion = compute_optimal_evasion(sat, w)

        has_los, upload_window = precheck_blackout_window(sat, evasion['burn_time_offset'])

        if has_los or upload_window > 0:
            recovery = compute_optimal_recovery(sat, evasion, sat.nominal_slot)
            total_fuel = evasion['fuel_cost_kg'] + recovery['fuel_cost_kg']

            if total_fuel <= sat.fuel_kg * 0.8:
                _enqueue(sat_id, evasion)
                _enqueue(sat_id, recovery)
                sim_state.conjunctions_avoided += 1
                logger.info(f"Scheduled evasion+recovery for {sat_id} — fuel cost: {total_fuel:.3f}kg")
            else:
                logger.warning(f"{sat_id} insufficient fuel for full maneuver sequence")
        else:
            logger.warning(f"{sat_id} in blackout — pre-uploading evasion")
            _enqueue(sat_id, evasion)

    return warnings

def _enqueue(sat_id, burn):
    sat = sim_state.satellites.get(sat_id)
    if not sat:
        return
    offset = burn.get('burn_time_offset', 0)
    if offset < 10:
        burn['burn_time_offset'] = 10
    dv = burn.get('dv_magnitude_km_s', 0)
    if dv > 0.015:
        burn['dv_magnitude_km_s'] = 0.015
        import numpy as np
        dv_eci = np.array(burn['deltaV_eci'])
        dv_norm = dv_eci / np.linalg.norm(dv_eci) * 0.015
        burn['deltaV_eci'] = dv_norm.tolist()
    sim_state.maneuver_queue.append({
        'satellite_id': sat_id,
        'burn': burn,
        'scheduled_at': sim_state.sim_elapsed
    })

def execute_due_maneuvers(step_seconds):
    executed = 0
    remaining = []

    for m in sim_state.maneuver_queue:
        offset = m['burn'].get('burn_time_offset', 0)
        if offset <= step_seconds:
            sat_id = m['satellite_id']
            sat = sim_state.satellites.get(sat_id)
            if sat and sat.fuel_kg > 0:
                fuel_used = apply_burn_to_satellite(sat, m['burn'])
                sat.last_burn_time = sim_state.sim_elapsed
                sim_state.executed_maneuvers.append({
                    'satellite_id': sat_id,
                    'burn_id': m['burn'].get('burn_id'),
                    'type': m['burn'].get('type'),
                    'fuel_used': fuel_used,
                    'time': sim_state.sim_elapsed
                })
                sim_state.total_dv_fleet += m['burn'].get('dv_magnitude_km_s', 0)
                executed += 1
                logger.info(f"Executed {m['burn'].get('burn_id')} for {sat_id}")
        else:
            m['burn']['burn_time_offset'] = offset - step_seconds
            remaining.append(m)

    sim_state.maneuver_queue = remaining
    return executed

def update_station_keeping(step_seconds):
    for sat_id, sat in sim_state.satellites.items():
        if sat.status == 'EOL':
            continue
        if sat.in_station_keeping():
            sat.uptime_seconds += step_seconds
            sat.status = 'NOMINAL'
        else:
            sat.outage_seconds += step_seconds
            sat.status = 'OUTAGE'