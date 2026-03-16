import numpy as np
from sqlalchemy.orm import Session
from database import Track
from moods import get_profile, track_fits_subgenre
import threading

# 13-feature weights tuned for techno DJ mixing (Embedding Accuracy Plan Phase 1)
WEIGHTS = np.array([
    3.0,   # bpm
    2.0,   # energy
    1.5,   # danceability
    1.0,   # brightness
    0.5,   # loudness
    0.8,   # spectral_centroid — tonal character
    0.6,   # spectral_flux — rate of change
    0.7,   # spectral_rolloff — frequency ceiling
    0.4,   # zero_crossing_rate — percussiveness
    1.2,   # rhythm_strength — rhythmic coherence
    0.9,   # onset_rate — rhythmic density
    0.5,   # dynamic_complexity — dynamic variation
    0.7,   # hpss_harmonic_ratio — harmonic vs percussive balance
], dtype=np.float32)

# Blend weight: 60% scalar similarity + 40% MFCC timbral similarity (Phase 2)
SCALAR_WEIGHT = 0.60
MFCC_WEIGHT = 0.40

CAMELOT_SCORE = {0: 1.0, 1: 0.85, 2: 0.5, 3: 0.2}

_cache_lock = threading.Lock()
_vector_cache = None

# Whitelist of valid pgvector column names (prevents SQL injection)
_VALID_VEC_COLS = {"embedding_vec", "intro_vec", "outro_vec", "peak_vec"}


def camelot_distance(a: str, b: str) -> int:
    if not a or not b or a == "?" or b == "?" or a == "Unknown" or b == "Unknown":
        return 3
    try:
        mode_a, mode_b = a[-1], b[-1]
        num_a, num_b = int(a[:-1]), int(b[:-1])
        if mode_a != mode_b:
            return 2
        return min(abs(num_a - num_b), 12 - abs(num_a - num_b))
    except Exception:
        return 3


def track_to_raw_vector(track) -> np.ndarray:
    """Build 13-dim scalar feature vector."""
    return np.array([
        track.bpm or 130.0,
        track.energy or 0.0,
        track.danceability or 0.0,
        track.brightness or 0.0,
        abs(track.loudness or 0.0),
        getattr(track, 'spectral_centroid', None) or 0.0,
        getattr(track, 'spectral_flux', None) or 0.0,
        getattr(track, 'spectral_rolloff', None) or 0.0,
        getattr(track, 'zero_crossing_rate', None) or 0.0,
        getattr(track, 'rhythm_strength', None) or 0.0,
        getattr(track, 'onset_rate', None) or 0.0,
        getattr(track, 'dynamic_complexity', None) or 0.0,
        getattr(track, 'hpss_harmonic_ratio', None) or 0.0,
    ], dtype=np.float32)


def _get_mfcc_vector(track) -> np.ndarray:
    """Get 26-dim MFCC vector from track, or zeros if not available."""
    mfcc = getattr(track, 'mfcc_vector', None)
    if mfcc and len(mfcc) == 26:
        return np.array(mfcc, dtype=np.float32)
    return np.zeros(26, dtype=np.float32)


def _build_cache_unlocked(db: Session):
    """Build the vector cache. Must be called with _cache_lock already held."""
    global _vector_cache
    tracks = db.query(Track).filter(Track.bpm.isnot(None)).all()
    if not tracks:
        _vector_cache = None
        return
    # 13-dim scalar features
    raw = np.array([track_to_raw_vector(t) for t in tracks], dtype=np.float32)
    mean = raw.mean(axis=0)
    std = raw.std(axis=0)
    std[std == 0] = 1.0
    normalized = (raw - mean) / std
    weighted = normalized * WEIGHTS

    # 26-dim MFCC matrix (Phase 2)
    mfcc_raw = np.array([_get_mfcc_vector(t) for t in tracks], dtype=np.float32)
    mfcc_mean = mfcc_raw.mean(axis=0)
    mfcc_std = mfcc_raw.std(axis=0)
    mfcc_std[mfcc_std == 0] = 1.0
    mfcc_normalized = (mfcc_raw - mfcc_mean) / mfcc_std

    _vector_cache = {
        "tracks": tracks,
        "matrix": weighted,
        "mean": mean, "std": std,
        "mfcc_matrix": mfcc_normalized,
        "mfcc_mean": mfcc_mean, "mfcc_std": mfcc_std,
    }


def build_cache(db: Session):
    with _cache_lock:
        _build_cache_unlocked(db)


def get_cache(db: Session):
    global _vector_cache
    # Fast path — no lock needed for a read if already populated
    if _vector_cache is not None:
        return _vector_cache
    # Slow path — double-checked locking
    with _cache_lock:
        if _vector_cache is None:
            _build_cache_unlocked(db)
    return _vector_cache


def invalidate_cache():
    global _vector_cache
    with _cache_lock:
        _vector_cache = None


def cosine_similarity_batch(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1)
    query_norm = np.linalg.norm(query_vec)
    denom = norms * query_norm
    denom[denom == 0] = 1e-9
    return (matrix @ query_vec) / denom


def query_to_vector(cache, bpm, energy=None, danceability=None, brightness=None, loudness=None,
                    spectral_centroid=None, spectral_flux=None, spectral_rolloff=None,
                    zero_crossing_rate=None, rhythm_strength=None, onset_rate=None,
                    dynamic_complexity=None, hpss_harmonic_ratio=None):
    """Build 13-dim query vector with fallbacks to population mean."""
    mean, std = cache["mean"], cache["std"]
    raw = np.array([
        bpm,
        energy if energy is not None else mean[1],
        danceability if danceability is not None else mean[2],
        brightness if brightness is not None else mean[3],
        abs(loudness) if loudness is not None else mean[4],
        spectral_centroid if spectral_centroid is not None else mean[5],
        spectral_flux if spectral_flux is not None else mean[6],
        spectral_rolloff if spectral_rolloff is not None else mean[7],
        zero_crossing_rate if zero_crossing_rate is not None else mean[8],
        rhythm_strength if rhythm_strength is not None else mean[9],
        onset_rate if onset_rate is not None else mean[10],
        dynamic_complexity if dynamic_complexity is not None else mean[11],
        hpss_harmonic_ratio if hpss_harmonic_ratio is not None else mean[12],
    ], dtype=np.float32)
    return ((raw - mean) / std) * WEIGHTS


def mfcc_similarity(query_mfcc: np.ndarray, mfcc_matrix: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between a query MFCC and all tracks' MFCCs."""
    return cosine_similarity_batch(query_mfcc, mfcc_matrix)


def _compute_momentum(history: list[dict]) -> dict:
    """
    Compute the direction of travel from play history.
    Returns: {bpm_trend, energy_trend} — positive = rising, negative = falling
    """
    if len(history) < 2:
        return {"bpm_trend": 0.0, "energy_trend": 0.0}
    bpms = [h.get("bpm", 130) for h in history if h.get("bpm")]
    energies = [h.get("energy", 0) for h in history if h.get("energy")]
    bpm_trend = (bpms[-1] - bpms[0]) / len(bpms) if len(bpms) > 1 else 0.0
    energy_trend = (energies[-1] - energies[0]) / len(energies) if len(energies) > 1 else 0.0
    return {"bpm_trend": bpm_trend, "energy_trend": energy_trend}


def _momentum_alignment(track, momentum: dict) -> float:
    """
    Score how well a track continues the current momentum direction.
    Rising energy set -> prefer higher energy tracks.
    """
    score = 0.5  # neutral
    if momentum["bpm_trend"] > 1.0 and track.bpm and track.bpm > 130:
        score += 0.3
    elif momentum["bpm_trend"] < -1.0 and track.bpm and track.bpm < 130:
        score += 0.3
    if momentum["energy_trend"] > 5000 and track.energy and track.energy > 80000:
        score += 0.2
    elif momentum["energy_trend"] < -5000 and track.energy and track.energy < 80000:
        score += 0.2
    return min(score, 1.0)


def recommend_tracks(db: Session, bpm: float = None, camelot: str = None,
                     energy: float = None, mood: str = None,
                     limit: int = 10, exclude_id: int = None,
                     min_score: float = 0.9,
                     history: list[dict] = None,
                     _depth: int = 0) -> list[dict]:
    """
    Precision subgenre-aware recommendations.
    - Filters by subgenre envelope first (hard constraints)
    - Uses per-subgenre feature weights
    - Tracks energy/BPM momentum from history
    - Enforces min_score floor, expands radius if needed
    - history: last 3-5 tracks played [{bpm, energy, camelot, subgenre}]
    """
    cache = get_cache(db)
    if cache is None:
        return []

    source_bpm = bpm or 130.0
    profile = get_profile(mood) if mood else get_profile("berlin")

    # Detect momentum from play history
    momentum = _compute_momentum(history or [])

    # Build query vector (13-dim scalar)
    query_vec = query_to_vector(cache, source_bpm, energy)
    cos_scores = cosine_similarity_batch(query_vec, cache["matrix"])

    # MFCC similarity scores (Phase 2: timbral matching)
    mfcc_matrix = cache.get("mfcc_matrix")
    has_mfcc = mfcc_matrix is not None and len(mfcc_matrix) > 0
    if has_mfcc:
        # Use population mean as query MFCC when no specific track is given
        query_mfcc = cache["mfcc_mean"] / (cache["mfcc_std"] + 1e-9)
        mfcc_scores = mfcc_similarity(query_mfcc, mfcc_matrix)
    else:
        mfcc_scores = np.zeros(len(cache["tracks"]))

    # Per-subgenre weights
    key_w = profile.get("key_weight", 0.25)
    bpm_tol = profile.get("bpm_tolerance", 5.0)

    results = []
    for i, t in enumerate(cache["tracks"]):
        if exclude_id and t.id == exclude_id:
            continue

        # Hard subgenre envelope filter
        if mood and not track_fits_subgenre(t, mood):
            continue

        # BPM gate using subgenre tolerance
        bpm_diff = abs((t.bpm or 130) - source_bpm)
        if bpm_diff > bpm_tol * 2:
            continue
        bpm_penalty = max(0.0, 1.0 - (bpm_diff / (bpm_tol * 2)) * 0.2)

        # Harmonic score
        dist = camelot_distance(camelot or "", t.camelot_code or "")
        harmonic = CAMELOT_SCORE.get(dist, 0.05)

        # Momentum alignment bonus
        momentum_bonus = _momentum_alignment(t, momentum)

        # Blended similarity: 60% scalar + 40% MFCC (Phase 2)
        cos_component = float(cos_scores[i])
        mfcc_component = float(mfcc_scores[i]) if has_mfcc else cos_component
        blended_sim = SCALAR_WEIGHT * cos_component + MFCC_WEIGHT * mfcc_component

        # Weighted final score using subgenre weights
        final = (
            (1.0 - key_w - 0.1) * blended_sim +
            key_w * harmonic +
            0.1 * momentum_bonus
        ) * bpm_penalty

        results.append((final, t))

    # Sort and enforce score floor
    results.sort(key=lambda x: x[0], reverse=True)

    # If best result is below min_score, relax constraints and retry (max 3 times)
    if results and results[0][0] < min_score and mood and _depth < 3:
        return recommend_tracks(db, bpm=bpm, camelot=camelot, energy=energy,
                                mood=mood, limit=limit, exclude_id=exclude_id,
                                min_score=min_score * 0.85,
                                history=history, _depth=_depth + 1)

    # Build results with explanation payload (Phase 2.6)
    output = []
    for s, t in results[:limit]:
        reasons = []
        bpm_diff = abs((t.bpm or 130) - source_bpm)
        if bpm_diff <= 2:
            reasons.append(f"BPM difference only {bpm_diff:.1f}")
        elif bpm_diff <= 5:
            reasons.append(f"BPM close ({bpm_diff:.1f} apart)")

        dist = camelot_distance(camelot or "", t.camelot_code or "")
        if dist == 0:
            reasons.append("Same key — perfect harmonic match")
        elif dist == 1:
            reasons.append("Camelot-adjacent keys")
        elif dist == 2:
            reasons.append("Relative major/minor key")

        if mood and track_fits_subgenre(t, mood):
            reasons.append(f"Fits {mood} energy envelope")

        if momentum.get("bpm_trend", 0) > 1 and t.bpm and t.bpm > source_bpm:
            reasons.append("Continues rising BPM momentum")
        elif momentum.get("bpm_trend", 0) < -1 and t.bpm and t.bpm < source_bpm:
            reasons.append("Continues falling BPM momentum")

        if t.energy_tag:
            reasons.append(f"Energy tag: {t.energy_tag}")

        output.append({
            "id": t.id, "title": t.title, "artist": t.artist,
            "bpm": t.bpm, "key": t.key, "camelot": t.camelot_code,
            "energy": t.energy, "danceability": t.danceability,
            "brightness": t.brightness, "duration": t.duration,
            "energy_tag": getattr(t, "energy_tag", None),
            "score": round(s, 4),
            "meets_threshold": bool(s >= min_score),
            "reasons": reasons,
        })
    return output


def similar_tracks(db: Session, track_id: int, limit: int = 10) -> dict:
    cache = get_cache(db)
    if cache is None:
        return {"error": "No tracks in database"}

    tracks = cache["tracks"]
    source_idx = next((i for i, t in enumerate(tracks) if t.id == track_id), None)
    if source_idx is None:
        return {"error": "Track not found"}

    source = tracks[source_idx]
    cos_scores = cosine_similarity_batch(cache["matrix"][source_idx], cache["matrix"])

    # MFCC similarity for timbral matching (Phase 2)
    mfcc_matrix = cache.get("mfcc_matrix")
    has_mfcc = mfcc_matrix is not None and len(mfcc_matrix) > 0
    if has_mfcc:
        mfcc_scores = mfcc_similarity(mfcc_matrix[source_idx], mfcc_matrix)
    else:
        mfcc_scores = np.zeros(len(tracks))

    results = []
    for i, t in enumerate(tracks):
        if t.id == track_id:
            continue
        bpm_diff = abs((t.bpm or 130) - (source.bpm or 130))
        if bpm_diff > 15:
            continue
        bpm_penalty = max(0.0, 1.0 - (bpm_diff / 15.0) * 0.3)
        dist = camelot_distance(source.camelot_code or "", t.camelot_code or "")
        harmonic = CAMELOT_SCORE.get(dist, 0.1)
        # Blended: 60% scalar + 40% MFCC for similarity component
        blended = SCALAR_WEIGHT * float(cos_scores[i]) + MFCC_WEIGHT * float(mfcc_scores[i]) if has_mfcc else float(cos_scores[i])
        final = (0.7 * blended + 0.3 * harmonic) * bpm_penalty
        results.append((final, t))

    results.sort(key=lambda x: x[0], reverse=True)
    return {
        "source": _track_to_dict(source),
        "similar": [_track_to_dict(t, s) for s, t in results[:limit]],
    }


def pgvector_similar(db: Session, track_id: int, limit: int = 10,
                     use_segment: str = None) -> dict:
    """
    Phase 3: pgvector-powered nearest neighbor search.
    Falls back to in-memory cosine similarity if pgvector is not available.

    Args:
        track_id: source track ID
        limit: max results
        use_segment: None=full track, "outro_intro"=outro(A)->intro(B) matching
    """
    from sqlalchemy import text

    source = db.query(Track).filter(Track.id == track_id).first()
    if not source:
        return {"error": "Track not found"}

    # Determine which vector column to use
    if use_segment == "outro_intro":
        # Phase 4: Match source outro to candidate intros
        vec_col_source = "outro_vec"
        vec_col_target = "intro_vec"
    else:
        vec_col_source = "embedding_vec"
        vec_col_target = "embedding_vec"

    # Validate column names against whitelist to prevent SQL injection
    if vec_col_source not in _VALID_VEC_COLS or vec_col_target not in _VALID_VEC_COLS:
        return similar_tracks(db, track_id, limit)

    try:
        # Try pgvector cosine distance query
        result = db.execute(text(f"""
            SELECT t.id, t.title, t.artist, t.bpm, t.key, t.camelot_code,
                   t.energy, t.danceability, t.brightness, t.duration,
                   t.energy_tag, t.spectral_centroid, t.spectral_flux,
                   t.rhythm_strength, t.onset_rate, t.hpss_harmonic_ratio,
                   1 - (t.{vec_col_target} <=> s.{vec_col_source}) as similarity
            FROM tracks t, tracks s
            WHERE s.id = :source_id
                AND t.id != :source_id
                AND t.{vec_col_target} IS NOT NULL
                AND s.{vec_col_source} IS NOT NULL
                AND ABS(t.bpm - s.bpm) <= 15
            ORDER BY t.{vec_col_target} <=> s.{vec_col_source}
            LIMIT :limit
        """), {"source_id": track_id, "limit": limit * 2})  # fetch extra for harmonic filter

        rows = result.fetchall()
        if not rows:
            # Fallback to in-memory
            return similar_tracks(db, track_id, limit)

        # Post-filter with harmonic scoring
        results = []
        source_camelot = source.camelot_code or ""
        for row in rows:
            dist = camelot_distance(source_camelot, row.camelot_code or "")
            harmonic = CAMELOT_SCORE.get(dist, 0.1)
            bpm_diff = abs((row.bpm or 130) - (source.bpm or 130))
            bpm_penalty = max(0.0, 1.0 - (bpm_diff / 15.0) * 0.3)
            # Blend vector similarity with harmonic score
            final = (0.7 * float(row.similarity) + 0.3 * harmonic) * bpm_penalty
            results.append({
                "id": row.id, "title": row.title, "artist": row.artist,
                "bpm": row.bpm, "key": row.key, "camelot": row.camelot_code,
                "energy": row.energy, "danceability": row.danceability,
                "brightness": row.brightness, "duration": row.duration,
                "energy_tag": row.energy_tag,
                "spectral_centroid": row.spectral_centroid,
                "spectral_flux": row.spectral_flux,
                "rhythm_strength": row.rhythm_strength,
                "onset_rate": row.onset_rate,
                "hpss_harmonic_ratio": row.hpss_harmonic_ratio,
                "vector_similarity": round(float(row.similarity), 4),
                "score": round(final, 4),
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return {
            "source": _track_to_dict(source),
            "similar": results[:limit],
            "method": "pgvector",
        }
    except Exception:
        # pgvector not available — fall back to in-memory
        return similar_tracks(db, track_id, limit)


def _track_to_dict(track, score=None) -> dict:
    d = {
        "id": track.id,
        "title": track.title,
        "artist": track.artist,
        "bpm": track.bpm,
        "key": track.key,
        "camelot": track.camelot_code,
        "energy": track.energy,
        "danceability": track.danceability,
        "brightness": track.brightness,
        "duration": track.duration,
        "spectral_centroid": getattr(track, "spectral_centroid", None),
        "spectral_flux": getattr(track, "spectral_flux", None),
        "rhythm_strength": getattr(track, "rhythm_strength", None),
        "onset_rate": getattr(track, "onset_rate", None),
        "hpss_harmonic_ratio": getattr(track, "hpss_harmonic_ratio", None),
        "energy_tag": getattr(track, "energy_tag", None),
    }
    if score is not None:
        d["score"] = round(score, 4)
    return d
