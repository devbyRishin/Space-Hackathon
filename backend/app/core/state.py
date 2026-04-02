from datetime import datetime
import numpy as np

GROUND_STATIONS = [
    {"id":"GS-001","name":"ISTRAC_Bengaluru","lat":13.0333,"lon":77.5167,"elev":820,"min_el":5.0},
    {"id":"GS-002","name":"Svalbard","lat":78.2297,"lon":15.4077,"elev":400,"min_el":5.0},
    {"id":"GS-003","name":"Goldstone","lat":35.4266,"lon":-116.890,"elev":1000,"min_el":10.0},
    {"id":"GS-004","name":"Punta_Arenas","lat":-53.150,"lon":-70.9167,"elev":30,"min_el":5.0},
    {"id":"GS-005","name":"IIT_Delhi","lat":28.5450,"lon":77.1926,"elev":225,"min_el":15.0},
    {"id":"GS-006","name":"McMurdo","lat":-77.8463,"lon":166.6682,"elev":10,"min_el":5.0},
]

MU = 398600.4418
RE = 6378.137
J2 = 1.08263e-3
G0 = 9.80665
ISP = 300.0
DRY_MASS = 500.0
INITIAL_FUEL = 50.0
MAX_DV = 0.015
COOLDOWN = 600
CONJUNCTION_THRESHOLD = 0.100
FUEL_EOL_THRESHOLD = 0.05
STATION_KEEPING_RADIUS = 10.0

class SatelliteState:
    def __init__(self, sat_id, r, v):
        self.id = sat_id
        self.r = np.array(r, dtype=float)
        self.v = np.array(v, dtype=float)
        self.fuel_kg = INITIAL_FUEL
        self.dry_mass = DRY_MASS
        self.status = 'NOMINAL'
        self.nominal_slot = np.array(r, dtype=float)
        self.last_burn_time = -9999.0
        self.total_dv_used = 0.0
        self.uptime_seconds = 0.0
        self.outage_seconds = 0.0
        self.maneuver_history = []

    @property
    def total_mass(self):
        return self.dry_mass + self.fuel_kg

    @property
    def fuel_pct(self):
        return self.fuel_kg / INITIAL_FUEL

    def in_station_keeping(self):
        return float(np.linalg.norm(self.r - self.nominal_slot)) <= STATION_KEEPING_RADIUS

class SimulationState:
    def __init__(self):
        self.current_time: datetime = datetime.utcnow()
        self.sim_elapsed: float = 0.0
        self.satellites: dict = {}
        self.debris: dict = {}
        self.maneuver_queue: list = []
        self.executed_maneuvers: list = []
        self.cdm_warnings: list = []
        self.collision_count: int = 0
        self.total_dv_fleet: float = 0.0
        self.conjunctions_avoided: int = 0

    def add_satellite(self, sat_id, r, v):
        if sat_id not in self.satellites:
            self.satellites[sat_id] = SatelliteState(sat_id, r, v)
        else:
            self.satellites[sat_id].r = np.array(r, dtype=float)
            self.satellites[sat_id].v = np.array(v, dtype=float)

    def add_debris(self, deb_id, r, v):
        self.debris[deb_id] = {
            'id': deb_id,
            'r': np.array(r, dtype=float),
            'v': np.array(v, dtype=float)
        }

sim_state = SimulationState()