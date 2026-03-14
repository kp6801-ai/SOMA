import numpy as np
from sqlalchemy.orm import Session
from database import Track
from recommender import get_cache, camelot_distance, CAMELOT_SCORE

def build_bpm_journey(db, start_bpm, end_bpm, steps=10, bpm_tolerance=5.0):
    cache = get_cache(db)
    if not cache:
        return {"error": "No tracks in database"}

    tracks = cache["tracks"]
    bpm_targets = np.linspace(start_bpm, end_bpm, steps)
    journey = []
    used_ids = set()
    last_camelot = None

    for i, target_bpm in enumerate(bpm_targets):
        candidates = []
        for t in tracks:
            if t.id in used_ids or t.bpm is None:
                continue
            bpm_diff = abs(t.bpm - target_bpm)
            if bpm_diff > bpm_tolerance:
                continue
            bpm_score = 1.0 - (bpm_diff / bpm_tolerance)
            harmonic = CAMELOT_SCORE.get(camelot_distance(last_camelot or "", t.camelot_code or ""), 0.1) if last_camelot else 1.0
            candidates.append((0.6 * bpm_score + 0.4 * harmonic, t))

        if not candidates:
            for t in tracks:
                if t.id in used_ids or t.bpm is None:
                    continue
                if abs(t.bpm - target_bpm) <= bpm_tolerance * 2:
                    candidates.append((0.1, t))

        if not candidates:
            continue

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_track = candidates[0]

        journey.append({
            "step": i + 1,
            "target_bpm": round(float(target_bpm), 1),
            "id": best_track.id,
            "title": best_track.title,
            "artist": best_track.artist,
            "bpm": best_track.bpm,
            "key": best_track.key,
            "camelot": best_track.camelot_code,
            "energy": best_track.energy,
            "score": round(best_score, 4),
        })
        used_ids.add(best_track.id)
        last_camelot = best_track.camelot_code

    return {"start_bpm": start_bpm, "end_bpm": end_bpm, "steps": len(journey), "journey": journey}
