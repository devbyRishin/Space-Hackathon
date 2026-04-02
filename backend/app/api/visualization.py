from fastapi import APIRouter
from ..core.state import sim_state
from ..core.physics import eci_to_latlon
import numpy as np

router = APIRouter()

@router.get("/api/visualization/snapshot")
async def get_snapshot():
    satellites = []
    for sat_id, sat in sim_state.satellites.items():
        lat, lon, alt = eci_to_latlon(sat.r)
        uptime_pct = 0.0
        total = sat.uptime_seconds + sat.outage_seconds
        if total > 0:
            uptime_pct = round(sat.uptime_seconds / total * 100, 1)
        satellites.append({
            "id": sat_id,
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "alt": round(alt, 2),
            "fuel_kg": round(sat.fuel_kg, 3),
            "fuel_pct": round(sat.fuel_pct * 100, 1),
            "status": sat.status,
            "total_dv_used": round(sat.total_dv_used * 1000, 4),
            "uptime_pct": uptime_pct,
            "in_slot": sat.in_station_keeping()
        })

    debris_cloud = []
    for deb_id, deb in sim_state.debris.items():
        lat, lon, alt = eci_to_latlon(deb['r'])
        debris_cloud.append([deb_id, round(lat, 3), round(lon, 3), round(alt, 2)])

    fleet_fuel_avg = 0.0
    if sim_state.satellites:
        fleet_fuel_avg = round(
            sum(s.fuel_kg for s in sim_state.satellites.values()) /
            len(sim_state.satellites), 2
        )

    return {
        "timestamp": sim_state.current_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "satellites": satellites,
        "debris_cloud": debris_cloud,
        "cdm_warnings": sim_state.cdm_warnings[:30],
        "collision_count": sim_state.collision_count,
        "conjunctions_avoided": sim_state.conjunctions_avoided,
        "total_dv_fleet_m_s": round(sim_state.total_dv_fleet * 1000, 4),
        "fleet_fuel_avg_kg": fleet_fuel_avg,
        "executed_maneuvers": sim_state.executed_maneuvers[-20:],
        "sim_elapsed_seconds": sim_state.sim_elapsed
    }

@router.get("/api/status")
async def get_status():
    return {
        "satellites_tracked": len(sim_state.satellites),
        "debris_tracked": len(sim_state.debris),
        "maneuvers_queued": len(sim_state.maneuver_queue),
        "maneuvers_executed": len(sim_state.executed_maneuvers),
        "collisions": sim_state.collision_count,
        "conjunctions_avoided": sim_state.conjunctions_avoided,
        "total_dv_m_s": round(sim_state.total_dv_fleet * 1000, 4),
        "sim_elapsed_s": sim_state.sim_elapsed
    }
