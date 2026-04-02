import numpy as np
from scipy.spatial import KDTree
from .physics import propagate, compute_probability_of_collision, CONJUNCTION_THRESHOLD

LOOKAHEAD_SECONDS = 86400
CHECK_INTERVALS = [0, 300, 600, 900, 1800, 3600, 7200, 14400, 28800, 43200, 86400]

def build_debris_tree(debris_dict):
    if not debris_dict:
        return None, []
    ids = list(debris_dict.keys())
    positions = np.array([debris_dict[i]['r'] for i in ids])
    tree = KDTree(positions)
    return tree, ids

def find_conjunctions(satellites, debris_dict):
    warnings = []
    if not debris_dict or not satellites:
        return warnings

    tree, debris_ids = build_debris_tree(debris_dict)
    if tree is None:
        return warnings

    seen = set()

    for sat_id, sat in satellites.items():
        r = sat.r.copy()
        v = sat.v.copy()

        best_miss = float('inf')
        best_tca = 0
        best_deb = None

        for t in CHECK_INTERVALS:
            if t == 0:
                r_prop, v_prop = r, v
            else:
                r_prop, v_prop = propagate(r, v, t)

            idxs = tree.query_ball_point(r_prop, r=50.0)

            for idx in idxs:
                deb_id = debris_ids[idx]
                key = f"{sat_id}_{deb_id}"
                deb = debris_dict[deb_id]
                deb_r = deb['r'].copy()
                deb_v = deb['v'].copy()

                if t == 0:
                    deb_r_prop = deb_r
                else:
                    deb_r_prop, _ = propagate(deb_r, deb_v, t)

                miss = float(np.linalg.norm(r_prop - deb_r_prop))

                if miss < best_miss:
                    best_miss = miss
                    best_tca = t
                    best_deb = deb_id

        if best_deb and best_miss < 50.0:
            pc = compute_probability_of_collision(best_miss)
            risk = 'CRITICAL' if best_miss < CONJUNCTION_THRESHOLD else \
                   'WARNING' if best_miss < 1.0 else \
                   'CAUTION' if best_miss < 5.0 else 'MONITOR'

            warnings.append({
                'sat_id': sat_id,
                'deb_id': best_deb,
                'tca_seconds': best_tca,
                'miss_distance_km': round(best_miss, 4),
                'probability_of_collision': round(pc, 6),
                'risk_level': risk,
                'critical': best_miss < CONJUNCTION_THRESHOLD
            })

    warnings.sort(key=lambda w: w['miss_distance_km'])
    return warnings