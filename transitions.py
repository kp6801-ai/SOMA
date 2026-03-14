import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import Track, LabelRelationship, TransitionScore
from recommender import camelot_distance, CAMELOT_SCORE
from moods import get_subgenre_compatibility

# Era compatibility mapping (Phase 2.9)
ERA_RANGES = {
    "classic": (1988, 1995),
    "second_wave": (1995, 2002),
    "modern": (2010, 2030),
}


def _era_compatibility(era_a: str, era_b: str) -> float:
    """Same era +0.05, adjacent era 0, crossing classic-modern -0.05."""
    if not era_a or not era_b:
        return 0.0
    if era_a == era_b:
        return 0.05
    eras = list(ERA_RANGES.keys())
    if era_a in eras and era_b in eras:
        dist = abs(eras.index(era_a) - eras.index(era_b))
        if dist == 1:
            return 0.0
        return -0.05
    return 0.0


def _label_compatibility(db: Session, label_a: str, label_b: str) -> float:
    """Query label_relationships table for compatibility score."""
    if not label_a or not label_b:
        return 0.5
    if label_a == label_b:
        return 1.0
    rel = db.query(LabelRelationship).filter(
        ((LabelRelationship.label_a == label_a) & (LabelRelationship.label_b == label_b)) |
        ((LabelRelationship.label_a == label_b) & (LabelRelationship.label_b == label_a))
    ).first()
    return rel.compatibility_score if rel else 0.5


def _structure_bonus(a, b) -> float:
    """Phase 3.5: Structural compatibility bonus."""
    clean_out_a = getattr(a, "has_clean_outro", None)
    clean_in_b = getattr(b, "has_clean_intro", None)

    if clean_out_a is None or clean_in_b is None:
        return 0.0
    if clean_out_a and clean_in_b:
        return 0.06  # Clean outro -> clean intro = ideal
    if not clean_out_a and not clean_in_b:
        return -0.04  # Mismatched = penalty
    return 0.0


def _timbral_similarity(a, b) -> float:
    """
    Phase 4: Outro→intro timbral match using segment MFCC vectors.
    If segment vectors available, compare A's outro to B's intro.
    Falls back to full-track MFCC comparison.
    """
    # Try segment vectors first (Phase 4)
    outro_a = getattr(a, "outro_vector", None)
    intro_b = getattr(b, "intro_vector", None)

    if outro_a and intro_b and len(outro_a) == len(intro_b):
        vec_a = np.array(outro_a, dtype=np.float32)
        vec_b = np.array(intro_b, dtype=np.float32)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a > 0 and norm_b > 0:
            return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

    # Fallback to full-track MFCC comparison (Phase 2)
    mfcc_a = getattr(a, "mfcc_vector", None)
    mfcc_b = getattr(b, "mfcc_vector", None)

    if mfcc_a and mfcc_b and len(mfcc_a) == len(mfcc_b):
        vec_a = np.array(mfcc_a, dtype=np.float32)
        vec_b = np.array(mfcc_b, dtype=np.float32)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a > 0 and norm_b > 0:
            return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

    return 0.5  # neutral when no timbral data


def _learned_score(db: Session, track_a_id: int, track_b_id: int) -> float:
    """
    Phase 5: Query transition_scores table for DJ-learned compatibility.
    Returns 0.0-1.0 based on how many real DJs have played this pair.
    """
    ts = db.query(TransitionScore).filter(
        ((TransitionScore.track_a_id == track_a_id) & (TransitionScore.track_b_id == track_b_id)) |
        ((TransitionScore.track_a_id == track_b_id) & (TransitionScore.track_b_id == track_a_id))
    ).first()

    if not ts:
        return 0.5  # neutral — no data

    # Scale by confidence and times played
    # 1 DJ played it = slight boost, 5+ = strong signal
    confidence = min(ts.confidence or 0.5, 1.0)
    play_boost = min(ts.times_played / 5.0, 1.0)
    return 0.5 + (0.5 * confidence * play_boost)


def score_transition(db: Session, track_a_id: int, track_b_id: int,
                     subgenre_a: str = None, subgenre_b: str = None) -> dict:
    """
    Score transition from A to B.
    8 dimensions: BPM 25%, Harmonic 22%, Energy 15%, Subgenre 10%,
                  Label 8%, Timbral 12%, Learned 8%
    Plus era bonus and structure bonus.
    """
    a = db.query(Track).filter(Track.id == track_a_id).first()
    b = db.query(Track).filter(Track.id == track_b_id).first()

    if not a:
        return {"error": f"Track {track_a_id} not found"}
    if not b:
        return {"error": f"Track {track_b_id} not found"}

    # BPM Score
    bpm_delta = abs((a.bpm or 130) - (b.bpm or 130))
    if bpm_delta <= 2:
        bpm_score, bpm_label = 1.0, "Perfect"
    elif bpm_delta <= 5:
        bpm_score, bpm_label = 0.85, "Easy"
    elif bpm_delta <= 10:
        bpm_score, bpm_label = 0.60, "Manageable"
    elif bpm_delta <= 15:
        bpm_score, bpm_label = 0.30, "Difficult"
    else:
        bpm_score, bpm_label = 0.05, "Train wreck"

    # Harmonic Score
    dist = camelot_distance(a.camelot_code or "", b.camelot_code or "")
    harmonic_score = CAMELOT_SCORE.get(dist, 0.05)
    harmonic_labels = {0: "Same key", 1: "Adjacent key", 2: "Relative major/minor", 3: "Risky"}
    harmonic_label = harmonic_labels.get(dist, "Incompatible")

    # Energy Score
    energy_a = a.energy or 0
    energy_b = b.energy or 0
    if energy_a == 0:
        energy_score, energy_label, energy_ratio = 0.5, "Unknown", 1.0
    else:
        energy_ratio = energy_b / energy_a
        if 0.85 <= energy_ratio <= 1.15:
            energy_score, energy_label = 1.0, "Matched"
        elif 0.70 <= energy_ratio <= 1.30:
            energy_score, energy_label = 0.75, "Slight shift"
        elif energy_ratio > 1.30:
            energy_score, energy_label = 0.55, "Big energy jump"
        else:
            energy_score, energy_label = 0.50, "Energy drop"

    # Subgenre compatibility
    sg_score = 1.0
    sg_label = "Same subgenre"
    if subgenre_a and subgenre_b and subgenre_a != subgenre_b:
        sg_score = get_subgenre_compatibility(subgenre_a, subgenre_b)
        sg_label = f"{subgenre_a} -> {subgenre_b}"
    elif subgenre_a and subgenre_b:
        sg_label = subgenre_a

    # Label compatibility (Phase 2.8)
    label_score = _label_compatibility(db, getattr(a, "label", None), getattr(b, "label", None))

    # Era compatibility bonus (Phase 2.9)
    era_bonus = _era_compatibility(getattr(a, "era", None), getattr(b, "era", None))

    # Structure bonus (Phase 3.5)
    struct_bonus = _structure_bonus(a, b)

    # Phase 4: Timbral similarity (outro A → intro B)
    timbral_score = _timbral_similarity(a, b)
    timbral_label = "Unknown"
    if timbral_score >= 0.85:
        timbral_label = "Very similar timbre"
    elif timbral_score >= 0.65:
        timbral_label = "Compatible timbre"
    elif timbral_score >= 0.45:
        timbral_label = "Neutral timbre"
    else:
        timbral_label = "Contrasting timbre"

    # Phase 5: Learned DJ transition score
    learned = _learned_score(db, track_a_id, track_b_id)
    learned_label = "No DJ data"
    if learned > 0.75:
        learned_label = "DJ-proven transition"
    elif learned > 0.55:
        learned_label = "Some DJ support"

    # Final weighted score: 8 dimensions
    # BPM 25%, Harmonic 22%, Energy 15%, Subgenre 10%,
    # Label 8%, Timbral 12%, Learned 8%
    overall = round(
        0.25 * bpm_score +
        0.22 * harmonic_score +
        0.15 * energy_score +
        0.10 * sg_score +
        0.08 * label_score +
        0.12 * timbral_score +
        0.08 * learned +
        era_bonus +
        struct_bonus,
        4
    )
    overall = max(0.0, min(1.0, overall))

    if overall >= 0.90:
        verdict = "Smooth — auto-mix safe"
    elif overall >= 0.75:
        verdict = "Workable — needs skill"
    elif overall >= 0.50:
        verdict = "Risky — avoid in peak time"
    else:
        verdict = "Incompatible — do not mix"

    return {
        "from": {"id": a.id, "title": a.title, "artist": a.artist,
                 "bpm": a.bpm, "key": a.key, "camelot": a.camelot_code,
                 "energy": a.energy, "subgenre": subgenre_a,
                 "label": getattr(a, "label", None), "era": getattr(a, "era", None),
                 "energy_tag": getattr(a, "energy_tag", None)},
        "to": {"id": b.id, "title": b.title, "artist": b.artist,
               "bpm": b.bpm, "key": b.key, "camelot": b.camelot_code,
               "energy": b.energy, "subgenre": subgenre_b,
               "label": getattr(b, "label", None), "era": getattr(b, "era", None),
               "energy_tag": getattr(b, "energy_tag", None)},
        "breakdown": {
            "bpm_delta": round(bpm_delta, 2),
            "bpm_score": bpm_score,
            "bpm_label": bpm_label,
            "harmonic_distance": dist,
            "harmonic_score": harmonic_score,
            "harmonic_label": harmonic_label,
            "energy_ratio": round(energy_ratio, 3),
            "energy_score": energy_score,
            "energy_label": energy_label,
            "subgenre_score": sg_score,
            "subgenre_label": sg_label,
            "label_score": label_score,
            "timbral_score": round(timbral_score, 4),
            "timbral_label": timbral_label,
            "learned_score": round(learned, 4),
            "learned_label": learned_label,
            "era_bonus": era_bonus,
            "structure_bonus": struct_bonus,
        },
        "overall_score": overall,
        "verdict": verdict,
        "auto_mix_safe": overall >= 0.90,
    }
