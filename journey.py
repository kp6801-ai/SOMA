import numpy as np
from sqlalchemy.orm import Session
from database import Track
from recommender import get_cache, camelot_distance, CAMELOT_SCORE
from moods import get_profile, track_fits_subgenre


def _get_expected_energy_tag(step_num: int, total_steps: int) -> str:
    """Default arc: warmup -> groove -> peak -> closer."""
    pct = step_num / max(total_steps - 1, 1)
    if pct < 0.2:
        return "warmup"
    elif pct < 0.5:
        return "groove"
    elif pct < 0.85:
        return "peak"
    return "closer"


def _arc_penalty(journey: list, candidate_tag: str) -> float:
    """
    Phase 3.6: Arc logic penalties.
    - No two peak tracks back-to-back
    - No same energy_tag 3 in a row
    """
    if not journey:
        return 0.0

    penalty = 0.0
    last_tag = journey[-1].get("energy_tag")

    # No two peak tracks back-to-back
    if candidate_tag == "peak" and last_tag == "peak":
        penalty -= 0.15

    # No same energy_tag 3 in a row
    if len(journey) >= 2:
        prev_tag = journey[-2].get("energy_tag")
        if candidate_tag == last_tag == prev_tag:
            penalty -= 0.20

    return penalty


def bpm_journey(db, start_bpm, end_bpm, steps=10,
                subgenre=None, min_score=0.9) -> dict:
    """
    BPM journey with subgenre constraint, 90% match floor, and energy arc logic.
    Enforces warmup -> groove -> peak arc by default.
    """
    cache = get_cache(db)
    if not cache:
        return {"error": "No tracks in database"}

    tracks = cache["tracks"]
    profile = get_profile(subgenre) if subgenre else None
    tolerance = profile["bpm_tolerance"] if profile else 5.0
    waypoints = np.linspace(start_bpm, end_bpm, steps)

    journey = []
    used_ids = set()
    last_camelot = None
    last_energy = None

    for step_num, target_bpm in enumerate(waypoints):
        expected_tag = _get_expected_energy_tag(step_num, steps)
        candidates = []

        for t in tracks:
            if t.id in used_ids or t.bpm is None:
                continue

            # Subgenre hard filter
            if subgenre and not track_fits_subgenre(t, subgenre):
                continue

            bpm_diff = abs(t.bpm - target_bpm)
            if bpm_diff > tolerance:
                continue

            # Score this candidate
            bpm_score = 1.0 - (bpm_diff / tolerance) * 0.3

            harmonic_score = 1.0
            if last_camelot and t.camelot_code:
                dist = camelot_distance(last_camelot, t.camelot_code)
                harmonic_score = CAMELOT_SCORE.get(dist, 0.05)

            energy_score = 1.0
            if last_energy and t.energy:
                ratio = t.energy / last_energy
                if 0.80 <= ratio <= 1.20:
                    energy_score = 1.0
                elif 0.65 <= ratio <= 1.35:
                    energy_score = 0.75
                else:
                    energy_score = 0.40

            score = 0.40 * bpm_score + 0.35 * harmonic_score + 0.25 * energy_score

            # Arc bonus: prefer tracks matching expected energy tag
            t_tag = getattr(t, "energy_tag", None)
            if t_tag and t_tag == expected_tag:
                score += 0.05

            # Arc penalty: avoid bad sequences
            arc_pen = _arc_penalty(journey, t_tag)
            score += arc_pen

            candidates.append((score, t))

        if not candidates:
            # Expand tolerance 2x and retry once
            for t in tracks:
                if t.id in used_ids or t.bpm is None:
                    continue
                if subgenre and not track_fits_subgenre(t, subgenre):
                    continue
                bpm_diff = abs(t.bpm - target_bpm)
                if bpm_diff <= tolerance * 2:
                    candidates.append((0.5, t))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_track = candidates[0]

            used_ids.add(best_track.id)
            last_camelot = best_track.camelot_code
            last_energy = best_track.energy

            journey.append({
                "step": step_num + 1,
                "id": best_track.id,
                "title": best_track.title,
                "artist": best_track.artist,
                "bpm": best_track.bpm,
                "key": best_track.key,
                "camelot": best_track.camelot_code,
                "energy": best_track.energy,
                "energy_tag": getattr(best_track, "energy_tag", None),
                "target_bpm": round(float(target_bpm), 1),
                "score": round(best_score, 4),
                "meets_threshold": bool(best_score >= min_score),
            })

    return {
        "subgenre": subgenre,
        "start_bpm": start_bpm,
        "end_bpm": end_bpm,
        "steps": steps,
        "found": len(journey),
        "high_quality_steps": sum(1 for s in journey if s["meets_threshold"]),
        "journey": journey,
    }
