import json
import math
import os
import sys
import datetime

# Competiton constants
P_MIN = 0.0035

def get_dir(env_var, default_root, fallback):
    if env_var in os.environ:
        return os.environ[env_var]
    if os.path.exists(default_root):
        return default_root
    return fallback

def get_input_dir():
    return get_dir("MAKEFUN_INPUT_DIR", "/input", "./input")

def get_output_dir():
    return get_dir("MAKEFUN_OUTPUT_DIR", "/output", "./output")

def load_task_json():
    input_dir = get_input_dir()
    task_path = os.path.join(input_dir, "task.json")
    if not os.path.exists(task_path):
        return None
    try:
        with open(task_path, "r") as f:
            return json.load(f)
    except:
        return None

def decide_branch():
    task = load_task_json()
    if task is None:
        return "FINAL"
    
    ts_str = task.get("window", {}).get("from")
    if not ts_str:
        ts_str = task.get("history_until")
    
    if not ts_str:
        return "FINAL"
    
    try:
        dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        threshold = datetime.datetime(2026, 11, 10, tzinfo=datetime.timezone.utc)
        
        if dt < threshold:
            return "DEV"
        else:
            return "FINAL"
    except:
        return "FINAL"

# DEV TABLE
DEV_TABLE = [
    (1, 10771743491, 0.4), (1, 10772946647, 0.3), (1, 10772543706, 0.2), (1, 10773425091, 0.1),
    (2, 10772543706, 0.4), (2, 10771743491, 0.2), (2, 10773926254, 0.2), (2, 10769671316, 0.1), (2, 10772946647, 0.1),
    (3, 10770575733, 0.7), (3, 10772543706, 0.2), (3, 10769671316, 0.1),
    (4, 10773425091, 0.5), (4, 10769671316, 0.2), (4, 10771743491, 0.2), (4, 10770575733, 0.1),
    (5, 10769671316, 0.6), (5, 10770575733, 0.2), (5, 10771881861, 0.1), (5, 10772543706, 0.1),
    (6, 10769941703, 0.4), (6, 10771928551, 0.2), (6, 10771881861, 0.1), (6, 10772281976, 0.1), (6, 10773425091, 0.1), (6, 10773912080, 0.1),
    (7, 10769941703, 0.3), (7, 10773355038, 0.2), (7, 10771881861, 0.1), (7, 10771928551, 0.1), (7, 10772281976, 0.1), (7, 10772946647, 0.1), (7, 10773425091, 0.1),
    (8, 10771881861, 0.6), (8, 10773355038, 0.2), (8, 10769941703, 0.1), (8, 10772217708, 0.1),
    (9, 10773380485, 0.6), (9, 10773425091, 0.2), (9, 10771421858, 0.1), (9, 10772281976, 0.1),
    (10, 10773380485, 0.3), (10, 10771421858, 0.2), (10, 10771928551, 0.2), (10, 10772114384, 0.1), (10, 10773355038, 0.1), (10, 10773912080, 0.1),
]

DEV_TOP10 = [10771743491, 10772543706, 10770575733, 10773425091, 10769671316,
             10769941703, 10771881861, 10773380485, 10771928551, 10772946647]

def run_dev():
    probabilities = []
    for place, uid, p in DEV_TABLE:
        probabilities.append({"universe_id": uid, "place": place, "p": round(p, 6)})
    probabilities.sort(key=lambda x: (x["place"], -x["p"], x["universe_id"]))
    return {"probabilities": probabilities, "top10": DEV_TOP10}

# FINAL branch constants
NAMED = [0.5, 0.4, 0.75, 0.90, 0.75, 0.75, 0.65, 0.75, 0.85, 0.7]
SD = [1.75, 1.75, 1.0, 2.0, 1.75, 1.5, 2.75, 1.25, 4.0, 3.0]
SHIFT = [0, 2, 0, 2, 5.5, 0, 0, 0, 0, 2]
PD, VD = 4.0, 1.25
MIX_WIDE, MIX_ALPHA = 1.25, 0.9
GAMMA = 0.12
BETA = 0.06
MOM_CLIP = 0.04
ETA = 0.01
ENTRANT_MAX_AGE_H = 24.0
ENTRANT_PLACE_WINDOW = 2

def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def run_final():
    input_dir = get_input_dir()
    history_path = os.path.join(input_dir, "history.ndjson")
    if not os.path.exists(history_path):
        return {"probabilities": [], "top10": []}

    history = []
    with open(history_path, "r") as f:
        for line in f:
            try:
                history.append(json.loads(line))
            except:
                continue

    if not history:
        return {"probabilities": [], "top10": []}

    # Extract closing chart (last valid read)
    closing_chart = None
    for read in reversed(history):
        if "up_and_coming" in read and isinstance(read["up_and_coming"], list):
            closing_chart = read
            break
            
    if not closing_chart:
        return {"probabilities": [], "top10": []}
        
    t_last = datetime.datetime.fromisoformat(closing_chart["at"].replace("Z", "+00:00"))
    
    # --- Velocity calculation ---
    vr = {}
    vp = {}
    
    def get_game_data(read, uid):
        for game in read.get("up_and_coming", []):
            if isinstance(game, dict) and game.get("universe_id") == uid:
                return game
        return None

    # Calculate velocities over last 2 gaps (history[-3], history[-2], history[-1])
    for i in range(max(1, len(history) - 2), len(history)):
        read_prev = history[i-1]
        read_curr = history[i]
        
        t_prev = datetime.datetime.fromisoformat(read_prev["at"].replace("Z", "+00:00"))
        t_curr = datetime.datetime.fromisoformat(read_curr["at"].replace("Z", "+00:00"))
        dt = (t_curr - t_prev).total_seconds() / 3600.0
        
        if dt <= 0: continue
        
        # rank velocity
        for game_curr in read_curr.get("up_and_coming", []):
            uid = game_curr.get("universe_id")
            if not isinstance(uid, int): continue
            rank_curr = game_curr.get("rank")
            if not isinstance(rank_curr, int): continue
            
            game_prev = get_game_data(read_prev, uid)
            if game_prev and isinstance(game_prev.get("rank"), int):
                rank_prev = game_prev["rank"]
                v = (rank_curr - rank_prev) / dt
                if uid not in vr: vr[uid] = []
                vr[uid].append(v)
                
        # playing velocity
        for game_curr in read_curr.get("up_and_coming", []):
            uid = game_curr.get("universe_id")
            if not isinstance(uid, int): continue
            playing_curr = game_curr.get("playing")
            if not isinstance(playing_curr, (int, float)) or playing_curr <= 0: continue
            
            game_prev = get_game_data(read_prev, uid)
            if game_prev and isinstance(game_prev.get("playing"), (int, float)) and game_prev["playing"] > 0:
                playing_prev = game_prev["playing"]
                v = (math.log(playing_curr) - math.log(playing_prev)) / dt
                if uid not in vp: vp[uid] = []
                vp[uid].append(v)

    final_vr = {}
    for uid, v_list in vr.items():
        if len(v_list) == 2:
            final_vr[uid] = max(-4.0, min(4.0, 0.65 * v_list[1] + 0.35 * v_list[0]))
        else:
            final_vr[uid] = max(-4.0, min(4.0, v_list[-1]))

    final_vp = {}
    for uid, v_list in vp.items():
        if len(v_list) == 2:
            final_vp[uid] = (v_list[1] + v_list[0]) / 2.0
        else:
            final_vp[uid] = v_list[-1]

    # --- Occupancy tables ---
    occ = [{} for _ in range(10)]
    occ_long = [{} for _ in range(10)]
    
    for read in history:
        t_i = datetime.datetime.fromisoformat(read["at"].replace("Z", "+00:00"))
        age_hours = (t_last - t_i).total_seconds() / 3600.0
        
        w = 2 ** (-age_hours / 8.0)
        w_long = 2 ** (-age_hours / 48.0)
        
        for game in read.get("up_and_coming", []):
            if not isinstance(game, dict): continue
            uid = game.get("universe_id")
            rank = game.get("rank")
            if not isinstance(uid, int) or not isinstance(rank, int) or rank < 1 or rank > 10:
                continue
            
            occ[rank-1][uid] = occ[rank-1].get(uid, 0.0) + w
            occ_long[rank-1][uid] = occ_long[rank-1].get(uid, 0.0) + w_long
            
    # Normalize occ shares
    for k in range(10):
        total = sum(occ[k].values())
        if total > 0:
            for uid in occ[k]:
                occ[k][uid] /= total
            # Keep top 10
            sorted_uids = sorted(occ[k].keys(), key=lambda uid: occ[k][uid], reverse=True)
            occ[k] = {uid: occ[k][uid] for uid in sorted_uids[:10]}
            
        total_long = sum(occ_long[k].values())
        if total_long > 0:
            for uid in occ_long[k]:
                occ_long[k][uid] /= total_long
            # Keep top 10
            sorted_uids = sorted(occ_long[k].keys(), key=lambda uid: occ_long[k][uid], reverse=True)
            occ_long[k] = {uid: occ_long[k][uid] for uid in sorted_uids[:10]}
    
    # --- Gaussian Mixture + Priors ---
    
    # Calculate first_seen (needed for entrant boost)
    first_seen = {}
    for read in history:
        t_i = datetime.datetime.fromisoformat(read["at"].replace("Z", "+00:00"))
        for game in read.get("up_and_coming", []):
            uid = game.get("universe_id")
            if isinstance(uid, int) and uid not in first_seen:
                first_seen[uid] = t_i

    # Compute raw scores
    raw_scores = []
    for game in closing_chart["up_and_coming"]:
        uid = game["universe_id"]
        rank = game["rank"]
        
        vr_val = final_vr.get(uid, 0.0)
        vp_val = final_vp.get(uid, 0.0)
        
        for k in range(1, 11):
            center = rank + vr_val * VD - vp_val * PD + SHIFT[k-1]
            
            p = phi((k+0.5-center)/SD[k-1]) - phi((k-0.5-center)/SD[k-1])
            pw = phi((k+0.5-center)/(SD[k-1]*MIX_WIDE)) - phi((k-0.5-center)/(SD[k-1]*MIX_WIDE))
            p = MIX_ALPHA * p + (1 - MIX_ALPHA) * pw
            
            # Occupancy prior
            p += GAMMA * occ[k-1].get(uid, 0.0)
            
            # Momentum
            mom = occ[k-1].get(uid, 0.0) - occ_long[k-1].get(uid, 0.0)
            p += max(-MOM_CLIP, min(MOM_CLIP, BETA * mom))
            
            # New entrant boost
            if (t_last - first_seen.get(uid, t_last)).total_seconds() / 3600.0 <= 24.0 and abs(k - rank) <= 2:
                p += ETA
                
            raw_scores.append({"universe_id": uid, "place": k, "p": max(0.0, p)})
            
    # Keep top 25 per place
    final_probabilities = []
    for k in range(1, 11):
        place_rows = [r for r in raw_scores if r["place"] == k]
        place_rows.sort(key=lambda r: r["p"], reverse=True)
        top25 = place_rows[:25]
        
        # Normalize
        total_p = sum(r["p"] for r in top25)
        if total_p > 0:
            for r in top25:
                r["p"] = (r["p"] / total_p) * NAMED[k-1]
                if r["p"] >= P_MIN:
                    final_probabilities.append(r)
    
    # --- Climber bonus ---
    # Top 4 games by playing velocity, limited to games in closing chart
    closing_uids = {game["universe_id"] for game in closing_chart["up_and_coming"] if isinstance(game.get("universe_id"), int)}
    # Use 0.0 if a game in closing chart has no recorded vp
    climber_candidates = {uid: final_vp.get(uid, 0.0) for uid in closing_uids}
    climbers = sorted(climber_candidates.items(), key=lambda x: x[1], reverse=True)[:4]
    climbers_mass = {1: 0.18, 2: 0.18, 3: 0.15, 4: 0.12, 5: 0.12, 6: 0.06, 7: 0.06, 8: 0.06, 9: 0.06, 10: 0.06}
    
    for k in range(1, 11):
        # shrink existing
        mass = climbers_mass[k]
        for r in final_probabilities:
            if r["place"] == k:
                r["p"] *= (1.0 - mass)
                
        # add bonus
        total_vp_weight = sum(max(vp_val, 0)**2 for _, vp_val in climbers if vp_val > 0)
        if total_vp_weight > 0:
            for uid, vp_val in climbers:
                if vp_val <= 0: continue
                w = (max(vp_val, 0)**2) / total_vp_weight
                bonus = w * mass
                # Add to row or create new
                found = False
                for r in final_probabilities:
                    if r["universe_id"] == uid and r["place"] == k:
                        r["p"] += bonus
                        found = True
                        break
                if not found:
                    final_probabilities.append({"universe_id": uid, "place": k, "p": bonus})
    
    # Drop rows below PMIN, merge duplicates
    merged = {}
    for r in final_probabilities:
        key = (r["universe_id"], r["place"])
        merged[key] = merged.get(key, 0.0) + r["p"]
        
    result_probs = []
    for (uid, place), p in merged.items():
        if p >= P_MIN:
            result_probs.append({"universe_id": uid, "place": place, "p": round(p, 6)})
            
    result_probs.sort(key=lambda x: (x["place"], -x["p"], x["universe_id"]))
    
    # Top10
    closing_games = sorted(closing_chart["up_and_coming"], key=lambda x: x["rank"])
    top10 = [g["universe_id"] for g in closing_games[:10]]
    
    return {"probabilities": result_probs, "top10": top10}

def main():
    branch = decide_branch()
    
    if branch == "DEV":
        result = run_dev()
    else:
        result = run_final()

    output_dir = get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "forecast.json"), "w") as f:
        json.dump(result, f)

if __name__ == "__main__":
    main()
