"""
Phase 2.11: Bridge Track Finder.
Given a source track and a target subgenre/BPM, find 1-3 stepping stones
that move the set gradually toward the target.
"""

from sqlalchemy.orm import Session
from database import Track
from recommender import get_cache, camelot_distance, CAMELOT_SCORE
from moods import get_profile, track_fits_subgenre, get_subgenre_compatibility
from transitions import score_transition


def find_bridge_tracks(db: Session, from_id: int,
                       target_subgenre: str = None,
                       target_bpm: float = None,
                       max_steps: int = 3) -> dict:
    """
    Find 1-3 bridge tracks that gradually move from source track
    toward a target subgenre/BPM.
    """
    cache = get_cache(db)
    if not cache:
        return {"error": "No tracks in database"}

    source = db.query(Track).filter(Track.id == from_id).first()
    if not source:
        return {"error": f"Track {from_id} not found"}

    tracks = cache["tracks"]
    target_profile = get_profile(target_subgenre) if target_subgenre else None
    final_bpm = target_bpm or (sum(target_profile["bpm_range"]) / 2 if target_profile else source.bpm or 130)

    bridge = []
    current = source
    used_ids = {source.id}

    for step in range(max_steps):
        # Progress fraction: how far toward target we should be
        progress = (step + 1) / (max_steps + 1)

        # Interpolate BPM target
        step_bpm = (current.bpm or 130) + progress * (final_bpm - (current.bpm or 130))

        candidates = []
        for t in tracks:
            if t.id in used_ids or t.bpm is None:
                continue

            # BPM should be moving toward target
            bpm_diff = abs(t.bpm - step_bpm)
            if bpm_diff > 10:
                continue

            bpm_score = max(0, 1.0 - bpm_diff / 10)

            # Harmonic compatibility with current
            dist = camelot_distance(current.camelot_code or "", t.camelot_code or "")
            harmonic_score = CAMELOT_SCORE.get(dist, 0.05)

            # Energy continuity
            energy_score = 0.5
            if current.energy and t.energy:
                ratio = t.energy / current.energy
                if 0.75 <= ratio <= 1.35:
                    energy_score = 1.0
                elif 0.60 <= ratio <= 1.50:
                    energy_score = 0.7

            # Subgenre affinity toward target
            sg_score = 0.5
            if target_subgenre:
                # Prefer tracks that partially fit the target subgenre
                if track_fits_subgenre(t, target_subgenre):
                    sg_score = 1.0
                else:
                    # Check compatible subgenres as intermediate steps
                    target_compat = target_profile.get("compatible_subgenres", []) if target_profile else []
                    for compat_sg in target_compat:
                        if track_fits_subgenre(t, compat_sg):
                            sg_score = 0.75
                            break

            score = 0.30 * bpm_score + 0.25 * harmonic_score + 0.20 * energy_score + 0.25 * sg_score
            candidates.append((score, t))

        if not candidates:
            break

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_track = candidates[0]

        used_ids.add(best_track.id)

        bridge.append({
            "step": step + 1,
            "id": best_track.id,
            "title": best_track.title,
            "artist": best_track.artist,
            "bpm": best_track.bpm,
            "key": best_track.key,
            "camelot": best_track.camelot_code,
            "energy": best_track.energy,
            "energy_tag": getattr(best_track, "energy_tag", None),
            "score": round(best_score, 4),
        })

        current = best_track

    return {
        "from": {
            "id": source.id, "title": source.title, "artist": source.artist,
            "bpm": source.bpm, "key": source.key, "camelot": source.camelot_code,
        },
        "target_subgenre": target_subgenre,
        "target_bpm": final_bpm,
        "bridge_tracks": bridge,
        "steps_found": len(bridge),
    }
