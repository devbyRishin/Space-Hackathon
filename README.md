# Autonomous Constellation Manager (ACM)

Submission for the National Space Hackathon 2026, hosted by IIT Delhi (Tryst'26).

---

## What this project does

Managing a fleet of satellites in Low Earth Orbit is not straightforward. Debris is everywhere, and a single collision can trigger a chain reaction that makes entire orbital shells unusable. Right now, most operators rely on manual ground control to dodge debris — which simply doesn't scale when you're managing hundreds of satellites.

This project is our attempt at solving that. The ACM is a ground-based software system that watches over a satellite fleet, predicts potential collisions up to 24 hours in advance, and automatically fires the right thruster burns to avoid them — without needing a human to approve every decision.

The backend handles all the physics and decision-making. The frontend gives you a live view of what's happening across the fleet.

---

## Running it

You need Docker installed. That's the only dependency.

```bash
git clone https://github.com/YOURUSERNAME/space-hackathon.git
cd space-hackathon
docker build -t acm-system .
docker run -d -p 8000:8000 --name acm acm-system
```

Open your browser at `http://localhost:8000` and you should see the dashboard.

To stop it:
```bash
docker stop acm && docker rm acm
```

---

## Feeding data to the system

The system starts empty. You need to send satellite and debris positions through the telemetry API to see anything happen.

**Send a safe scenario (debris far away):**
```bash
curl -X POST http://localhost:8000/api/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-03-12T08:00:00.000Z",
    "objects": [
      {
        "id": "SAT-Alpha-01",
        "type": "SATELLITE",
        "r": {"x": 6500.0, "y": 1200.0, "z": 800.0},
        "v": {"x": -1.5, "y": 6.8, "z": 3.1}
      },
      {
        "id": "DEB-001",
        "type": "DEBRIS",
        "r": {"x": 7200.0, "y": 500.0, "z": 1200.0},
        "v": {"x": 0.5, "y": 7.2, "z": 1.8}
      }
    ]
  }'
```

**Send a critical scenario (debris within 80 meters — below the 100m threshold):**
```bash
curl -X POST http://localhost:8000/api/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-03-12T08:00:00.000Z",
    "objects": [
      {
        "id": "SAT-Alpha-01",
        "type": "SATELLITE",
        "r": {"x": 6500.0, "y": 1200.0, "z": 800.0},
        "v": {"x": -1.5, "y": 6.8, "z": 3.1}
      },
      {
        "id": "DEB-CRIT-01",
        "type": "DEBRIS",
        "r": {"x": 6500.07, "y": 1200.04, "z": 800.03},
        "v": {"x": -1.51, "y": 6.81, "z": 3.11}
      }
    ]
  }'
```

This will trigger a CRITICAL conjunction alert on the dashboard and automatically schedule an evasion maneuver.

**Advance the simulation:**
```bash
curl -X POST http://localhost:8000/api/simulate/step \
  -H "Content-Type: application/json" \
  -d '{"step_seconds": 3600}'
```

---

## API endpoints

| Endpoint | Method | What it does |
|---|---|---|
| `/api/telemetry` | POST | Send satellite and debris state vectors |
| `/api/maneuver/schedule` | POST | Schedule a manual burn sequence |
| `/api/simulate/step` | POST | Advance simulation time by N seconds |
| `/api/visualization/snapshot` | GET | Get current fleet state for the dashboard |
| `/api/status` | GET | Fleet health summary |
| `/health` | GET | Basic health check |

---

## How the system works

### Collision detection

Every time telemetry arrives, the system checks every satellite against the debris field. The naive way to do this is O(N²) — check every satellite against every piece of debris. With tens of thousands of debris objects, that's too slow.

We use a KD-tree (from SciPy) to index the debris field spatially. For each satellite, we only check debris within a 50km search radius, which cuts the computation down dramatically. Conjunctions are checked at 11 time intervals up to 24 hours ahead.

A conjunction becomes CRITICAL when the predicted miss distance drops below 100 meters.

### Physics

Orbits aren't perfect ellipses. Earth's equatorial bulge causes satellites to drift over time. We account for this using the J2 perturbation model, integrated numerically using a 4th-order Runge-Kutta solver. All positions and velocities are in the Earth-Centered Inertial (ECI) frame.

### Evasion maneuvers

When a critical conjunction is detected, the system calculates a burn in the satellite's local RTN frame (Radial, Transverse, Normal). We prefer transverse burns — prograde or retrograde — because they're the most fuel-efficient way to change orbital phase.

After the evasion, the satellite is no longer in its assigned slot. The system calculates a Hohmann transfer to bring it back. Both burns are scheduled as a sequence, respecting the 600-second cooldown between burns and the 15 m/s per-burn limit.

### Fuel tracking

Every burn depletes fuel according to the Tsiolkovsky rocket equation:

```
Δm = m_current × (1 − e^(−|Δv| / (Isp × g₀)))
```

We use Isp = 300s, dry mass = 500 kg, initial fuel = 50 kg. As the satellite burns fuel, it gets lighter, so future burns become slightly more efficient. The system tracks this per satellite.

When fuel hits 5%, the satellite is flagged as end-of-life and a graveyard burn is scheduled automatically to lower its orbit and prevent it from becoming uncontrolled debris.

### Ground station coverage

Maneuver commands can only be sent when a satellite has line-of-sight with at least one ground station. We check elevation angles against six stations: ISTRAC Bengaluru, Svalbard, Goldstone, Punta Arenas, IIT Delhi, and McMurdo. If a conjunction is predicted over a blackout zone, the system pre-uploads the evasion sequence before the satellite loses contact.

---

## Dashboard

The frontend is a single HTML file using Three.js for the 3D globe and Canvas 2D for the other panels. It polls `/api/visualization/snapshot` every two seconds and updates everything in real time.

**Globe** — Rotating 3D Earth. Cyan dots are satellites, orange dots are debris. Color shifts to orange/red as fuel depletes.

**Conjunction bullseye** — Polar chart showing how close debris is to a selected satellite. Green ring is 5km, orange is 1km, red is 100m.

**Fuel gauges** — One bar per satellite showing remaining propellant. Turns orange below 40%, red below 15%.

**Ground track** — 2D Mercator map with real terminator line (day/night boundary), orbit trails, and predicted trajectory for the next pass.

**Gantt timeline** — Shows evasion and recovery burns as colored blocks, with the 600-second cooldown periods marked in between.

**System log** — Live event feed showing conjunctions detected, maneuvers executed, and fuel consumed.

---

## Project structure

```
space-hackathon/
├── Dockerfile
├── docker-compose.yml
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── app/
│       ├── api/
│       │   ├── telemetry.py
│       │   ├── maneuver.py
│       │   ├── simulate.py
│       │   └── visualization.py
│       ├── core/
│       │   ├── physics.py       # RK4 + J2 propagator
│       │   ├── kdtree.py        # Conjunction detection
│       │   ├── cola.py          # Evasion and recovery burns
│       │   ├── scheduler.py     # Maneuver queue and LOS checks
│       │   └── state.py         # Simulation state
│       └── models/
│           └── schemas.py
└── frontend/
    └── index.html
```

---

## Constants used

| Parameter | Value |
|---|---|
| Earth's gravitational parameter (μ) | 398,600.4418 km³/s² |
| Earth radius (RE) | 6,378.137 km |
| J2 coefficient | 1.08263 × 10⁻³ |
| Standard gravity (g₀) | 9.80665 m/s² |
| Specific impulse (Isp) | 300 s |
| Satellite dry mass | 500 kg |
| Initial fuel mass | 50 kg |
| Max ΔV per burn | 15 m/s |
| Thruster cooldown | 600 s |
| Conjunction threshold | 100 m |
| Station-keeping radius | 10 km |
| EOL fuel threshold | 5% |

---

## Tech stack

- Python 3.11, FastAPI, Uvicorn
- NumPy, SciPy (KD-tree)
- Three.js r128 (3D globe)
- Docker (ubuntu:22.04)
