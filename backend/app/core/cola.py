import numpy as np
from .physics import (propagate, rtn_to_eci, compute_fuel_consumed,
                       hohmann_dv, MAX_DV, DRY_MASS, INITIAL_FUEL,
                       CONJUNCTION_THRESHOLD, COOLDOWN)

def compute_optimal_evasion(sat, conjunction):
    r = sat.r.copy()
    v = sat.v.copy()
    tca = conjunction['tca_seconds']
    miss = conjunction['miss_distance_km']

    burn_offset = max(60, tca - 600)
    if burn_offset < sat.last_burn_time + COOLDOWN:
        burn_offset = sat.last_burn_time + COOLDOWN + 10

    r_burn, v_burn = propagate(r, v, burn_offset)

    scale = min(1.0, max(0.3, CONJUNCTION_THRESHOLD * 2 / max(miss, 0.001)))
    dv_mag = min(MAX_DV * scale, sat.fuel_kg * 0.3 / sat.total_mass * 7.0)
    dv_mag = max(0.001, dv_mag)

    dv_rtn = np.array([0.0, dv_mag, 0.0])
    dv_eci = rtn_to_eci(r_burn, v_burn, dv_rtn)

    fuel_cost = compute_fuel_consumed(sat.total_mass, dv_mag)

    return {
        'burn_id': f'EVASION_{conjunction["deb_id"]}',
        'burn_time_offset': burn_offset,
        'deltaV_eci': dv_eci.tolist(),
        'dv_magnitude_km_s': dv_mag,
        'fuel_cost_kg': fuel_cost,
        'type': 'EVASION'
    }

def compute_optimal_recovery(sat, evasion_burn, nominal_slot):
    r = sat.r.copy()
    v = sat.v.copy()

    ev_offset = evasion_burn['burn_time_offset']
    r_ev, v_ev = propagate(r, v, ev_offset)
    dv_ev = np.array(evasion_burn['deltaV_eci'])
    v_ev_new = v_ev + dv_ev

    r_mag_current = np.linalg.norm(r_ev)
    r_mag_nominal = np.linalg.norm(nominal_slot) if nominal_slot is not None else r_mag_current

    dv1, dv2 = hohmann_dv(r_mag_current, r_mag_nominal)
    dv_recovery = min(dv2, MAX_DV * 0.8)

    recovery_offset = ev_offset + COOLDOWN + 60

    r_rec, v_rec = propagate(r_ev, v_ev_new, recovery_offset - ev_offset)
    dv_rtn = np.array([0.0, -dv_recovery, 0.0])
    dv_eci = rtn_to_eci(r_rec, v_rec, dv_rtn)

    fuel_cost = compute_fuel_consumed(sat.total_mass, dv_recovery)

    return {
        'burn_id': f'RECOVERY_{evasion_burn["burn_id"]}',
        'burn_time_offset': recovery_offset,
        'deltaV_eci': dv_eci.tolist(),
        'dv_magnitude_km_s': dv_recovery,
        'fuel_cost_kg': fuel_cost,
        'type': 'RECOVERY'
    }

def compute_graveyard_burn(sat):
    r = sat.r.copy()
    v = sat.v.copy()
    dv_rtn = np.array([0.0, -MAX_DV, 0.0])
    dv_eci = rtn_to_eci(r, v, dv_rtn)
    fuel_cost = compute_fuel_consumed(sat.total_mass, MAX_DV)
    return {
        'burn_id': 'GRAVEYARD_BURN',
        'burn_time_offset': 60,
        'deltaV_eci': dv_eci.tolist(),
        'dv_magnitude_km_s': MAX_DV,
        'fuel_cost_kg': fuel_cost,
        'type': 'GRAVEYARD'
    }

def apply_burn_to_satellite(sat, burn):
    dv = np.array(burn['deltaV_eci'])
    dv_mag = float(np.linalg.norm(dv))
    fuel_used = compute_fuel_consumed(sat.total_mass, dv_mag)
    sat.v = sat.v + dv
    sat.fuel_kg = max(0.0, sat.fuel_kg - fuel_used)
    sat.total_dv_used += dv_mag
    sat.last_burn_time = sat.last_burn_time
    sat.maneuver_history.append({
        'burn_id': burn.get('burn_id', 'UNKNOWN'),
        'dv_mag': dv_mag,
        'fuel_remaining': sat.fuel_kg,
        'type': burn.get('type', 'UNKNOWN')
    })
    return fuel_used