import numpy as np

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

def j2_acceleration(r):
    x, y, z = r
    r_mag = np.linalg.norm(r)
    factor = (3/2) * J2 * MU * RE**2 / r_mag**5
    ax = factor * x * (5*z**2/r_mag**2 - 1)
    ay = factor * y * (5*z**2/r_mag**2 - 1)
    az = factor * z * (5*z**2/r_mag**2 - 3)
    return np.array([ax, ay, az])

def derivatives(state):
    r = state[:3]
    v = state[3:]
    r_mag = np.linalg.norm(r)
    a_grav = -MU / r_mag**3 * r
    a_j2 = j2_acceleration(r)
    return np.concatenate([v, a_grav + a_j2])

def rk4_step(state, dt):
    k1 = derivatives(state)
    k2 = derivatives(state + 0.5*dt*k1)
    k3 = derivatives(state + 0.5*dt*k2)
    k4 = derivatives(state + dt*k3)
    return state + (dt/6.0)*(k1 + 2*k2 + 2*k3 + k4)

def propagate(r, v, dt_seconds, steps=None):
    if dt_seconds == 0:
        return np.array(r), np.array(v)
    if steps is None:
        steps = max(1, int(dt_seconds / 60))
    state = np.concatenate([np.array(r), np.array(v)])
    dt = dt_seconds / steps
    for _ in range(steps):
        state = rk4_step(state, dt)
    return state[:3], state[3:]

def eci_to_latlon(r):
    x, y, z = r
    r_mag = np.linalg.norm(r)
    lat = float(np.degrees(np.arcsin(np.clip(z / r_mag, -1, 1))))
    lon = float(np.degrees(np.arctan2(y, x)))
    alt = float(r_mag - RE)
    return lat, lon, alt

def compute_fuel_consumed(current_mass, dv_km_s):
    dv_m_s = abs(dv_km_s) * 1000
    if dv_m_s < 1e-9:
        return 0.0
    dm = current_mass * (1 - np.exp(-dv_m_s / (ISP * G0)))
    return float(dm)

def rtn_to_eci(r, v, dv_rtn):
    r = np.array(r)
    v = np.array(v)
    r_hat = r / np.linalg.norm(r)
    h = np.cross(r, v)
    n_hat = h / np.linalg.norm(h)
    t_hat = np.cross(n_hat, r_hat)
    rotation = np.column_stack([r_hat, t_hat, n_hat])
    return rotation @ np.array(dv_rtn)

def check_los(sat_r, gs):
    sat_r = np.array(sat_r)
    gs_lat = np.radians(gs['lat'])
    gs_lon = np.radians(gs['lon'])
    gs_alt = gs['elev'] / 1000.0
    gs_r = (RE + gs_alt) * np.array([
        np.cos(gs_lat)*np.cos(gs_lon),
        np.cos(gs_lat)*np.sin(gs_lon),
        np.sin(gs_lat)
    ])
    diff = sat_r - gs_r
    dist = np.linalg.norm(diff)
    if dist < 1e-9:
        return True
    gs_r_mag = np.linalg.norm(gs_r)
    cos_el = np.dot(gs_r/gs_r_mag, diff/dist)
    el_deg = float(np.degrees(np.arcsin(np.clip(cos_el, -1, 1))))
    return el_deg >= gs['min_el']

def orbital_period(r):
    r_mag = np.linalg.norm(r)
    return 2 * np.pi * np.sqrt(r_mag**3 / MU)

def hohmann_dv(r1_mag, r2_mag):
    v1 = np.sqrt(MU / r1_mag)
    v_transfer_peri = np.sqrt(2 * MU * r2_mag / (r1_mag * (r1_mag + r2_mag)))
    dv1 = abs(v_transfer_peri - v1)
    v2 = np.sqrt(MU / r2_mag)
    v_transfer_apo = np.sqrt(2 * MU * r1_mag / (r2_mag * (r1_mag + r2_mag)))
    dv2 = abs(v2 - v_transfer_apo)
    return dv1, dv2

def compute_probability_of_collision(miss_km, combined_covariance_km=0.05):
    sigma = combined_covariance_km
    pc = np.exp(-0.5 * (miss_km / sigma)**2)
    return float(np.clip(pc, 0, 1))