from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from database import get_db, Track
from camelot import get_camelot, compatible_keys
from recommender import recommend_tracks, similar_tracks, pgvector_similar, invalidate_cache
from moods import list_moods, get_profile, SUBGENRE_PROFILES
from transitions import score_transition
from journey import bpm_journey as _bpm_journey
from bridge import find_bridge_tracks
from arc_presets import ARC_PRESETS
import session_service
from pydantic import BaseModel
from typing import Optional
import tempfile
import shutil
import os

router = APIRouter()


class BridgeRequest(BaseModel):
    from_id: int
    target_subgenre: Optional[str] = None
    target_bpm: Optional[float] = None
    max_steps: Optional[int] = 3


class SessionCreateRequest(BaseModel):
    arc_type: str
    duration_min: int


class SessionEventRequest(BaseModel):
    event: str
    position: int
    rating: Optional[int] = None


# ---------------------------------------------------------------------------
# M2 Session routes
# ---------------------------------------------------------------------------

@router.get("/sessions/arc-types")
def get_arc_types():
    """List all available arc types the user can pick from."""
    return {
        "arc_types": [
            {
                "key": key,
                "label": v["label"],
                "bpm_start": v["bpm_start"],
                "bpm_peak": v["bpm_peak"],
                "bpm_end": v["bpm_end"],
                "description": v["description"],
            }
            for key, v in ARC_PRESETS.items()
        ]
    }


@router.post("/sessions")
def create_session(req: SessionCreateRequest, db: Session = Depends(get_db)):
    """Create a new session. Plans the full arc and picks all tracks upfront."""
    if req.duration_min < 5 or req.duration_min > 480:
        raise HTTPException(status_code=400, detail="duration_min must be between 5 and 480")
    try:
        result = session_service.create_session(db, req.arc_type, req.duration_min)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.get("/sessions/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)):
    """Get a session with its full track list."""
    result = session_service.get_session(db, session_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/sessions/{session_id}/next-track")
def get_next_track(session_id: int, db: Session = Depends(get_db)):
    """Return the next pending track and mark it as playing."""
    result = session_service.next_track(db, session_id)
    return result


@router.post("/sessions/{session_id}/events")
def post_event(session_id: int, req: SessionEventRequest, db: Session = Depends(get_db)):
    """Record a skip or completion event for a track slot."""
    if req.event not in ("completed", "skipped"):
        raise HTTPException(status_code=400, detail="event must be 'completed' or 'skipped'")
    result = session_service.record_event(db, session_id, req.event, req.position, req.rating)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/sessions/{session_id}/summary")
def get_summary(session_id: int, db: Session = Depends(get_db)):
    """Get session summary and mark it completed."""
    result = session_service.get_summary(db, session_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/tracks")
def get_tracks(db: Session = Depends(get_db)):
    tracks = db.query(Track).all()
    return {
        "tracks": [
            {"id": t.id, "title": t.title, "artist": t.artist, "bpm": t.bpm,
             "key": t.key, "camelot": t.camelot_code, "energy": t.energy,
             "danceability": t.danceability, "brightness": t.brightness,
             "duration": t.duration, "energy_tag": t.energy_tag,
             "label": t.label, "era": t.era,
             "intro_bars": t.intro_bars, "outro_bars": t.outro_bars,
             "has_clean_intro": t.has_clean_intro, "has_clean_outro": t.has_clean_outro,
             "spectral_centroid": t.spectral_centroid,
             "spectral_flux": t.spectral_flux,
             "rhythm_strength": t.rhythm_strength,
             "onset_rate": t.onset_rate,
             "hpss_harmonic_ratio": t.hpss_harmonic_ratio,
             "has_embedding": t.embedding is not None,
             "has_mfcc": t.mfcc_vector is not None,
             "has_segments": t.intro_vector is not None}
            for t in tracks
        ],
        "count": len(tracks),
    }

@router.get("/compatible/{camelot}")
def get_compatible(camelot: str):
    keys = compatible_keys(camelot)
    return {"camelot": camelot, "compatible_keys": keys}

@router.get("/recommend")
def get_recommendations(
    bpm: float = None,
    camelot: str = None,
    energy: float = None,
    mood: str = None,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    tracks = recommend_tracks(db, bpm=bpm, camelot=camelot, energy=energy, mood=mood, limit=limit)
    return {"recommendations": tracks, "count": len(tracks)}

@router.get("/mood/{mood}")
def get_by_mood(mood: str, limit: int = 10, db: Session = Depends(get_db)):
    tracks = recommend_tracks(db, mood=mood, limit=limit)
    return {"mood": mood, "recommendations": tracks, "count": len(tracks)}

@router.get("/moods")
def get_moods():
    moods = []
    for name in sorted(SUBGENRE_PROFILES.keys()):
        profile = SUBGENRE_PROFILES[name]
        moods.append({
            "name": name,
            "bpm_range": profile["bpm_range"],
            "description": profile["description"],
            "compatible_subgenres": profile.get("compatible_subgenres", []),
        })
    return {"moods": moods}

@router.get("/similar/{track_id}")
def get_similar(track_id: int, limit: int = 5,
                method: str = "auto", db: Session = Depends(get_db)):
    """
    Find similar tracks. Methods:
    - auto: Use pgvector if available, fallback to in-memory
    - pgvector: Force pgvector cosine similarity
    - memory: Force in-memory NumPy similarity
    - outro_intro: pgvector outro→intro segment matching (Phase 4)
    """
    if method == "memory":
        result = similar_tracks(db, track_id, limit=limit)
    elif method == "outro_intro":
        result = pgvector_similar(db, track_id, limit=limit, use_segment="outro_intro")
    else:
        # Auto: try pgvector first, fallback to memory
        result = pgvector_similar(db, track_id, limit=limit)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.post("/tracks/upload")
async def upload_track(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".mp3"):
        raise HTTPException(status_code=400, detail="Only MP3 files are supported")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        from scripts.extract_features import extract_features
        features = extract_features(tmp_path)

        features["file_path"] = f"upload:{file.filename}"
        # Parse artist/title from original filename (not temp path)
        stem = file.filename.rsplit(".", 1)[0]
        if " - " in stem:
            artist, title = stem.split(" - ", 1)
            features["artist"] = artist.strip()
            features["title"] = title.strip()
        else:
            features["artist"] = "Unknown"
            features["title"] = stem

        track = db.query(Track).filter(Track.file_path == features["file_path"]).first()
        if not track:
            # Store all available features including new spectral/MFCC/embedding data
            track_cols = [
                "file_path", "title", "artist", "bpm", "key", "camelot_code",
                "energy", "loudness", "danceability", "brightness", "duration",
                "analysis_version", "feature_extractor_version", "normalization_version",
                "spectral_centroid", "spectral_flux", "spectral_rolloff",
                "zero_crossing_rate", "rhythm_strength", "onset_rate",
                "dynamic_complexity", "hpss_harmonic_ratio",
                "mfcc_vector", "embedding",
                "intro_vector", "peak_vector", "outro_vector",
                "intro_bars", "outro_bars", "has_clean_intro", "has_clean_outro",
                "first_breakdown_bar", "drop_bar", "groove_stability",
            ]
            track_data = {k: features.get(k) for k in track_cols if k in features}
            track = Track(**track_data)
            db.add(track)
            db.commit()
            db.refresh(track)

        invalidate_cache()

        result = similar_tracks(db, track.id, limit=10)

        return {
            "track": {
                "id": track.id, "title": track.title, "artist": track.artist,
                "bpm": track.bpm, "key": track.key, "camelot": track.camelot_code,
                "energy": track.energy, "danceability": track.danceability,
                "brightness": track.brightness, "duration": track.duration,
            },
            "similar": result.get("similar", []),
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        os.unlink(tmp_path)

@router.get("/journey")
def get_bpm_journey(
    start_bpm: float = 120.0,
    end_bpm: float = 145.0,
    steps: int = 10,
    subgenre: str = None,
    min_score: float = 0.9,
    db: Session = Depends(get_db),
):
    if steps < 2 or steps > 30:
        raise HTTPException(status_code=400, detail="steps must be between 2 and 30")
    if not (60 <= start_bpm <= 200) or not (60 <= end_bpm <= 200):
        raise HTTPException(status_code=400, detail="BPM must be between 60 and 200")
    result = _bpm_journey(db, start_bpm, end_bpm, steps, subgenre, min_score)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.get("/transition")
def get_transition(
    track_a: int,
    track_b: int,
    subgenre_a: str = None,
    subgenre_b: str = None,
    db: Session = Depends(get_db),
):
    result = score_transition(db, track_a, track_b, subgenre_a, subgenre_b)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.post("/bridge")
def post_bridge(req: BridgeRequest, db: Session = Depends(get_db)):
    """Phase 2.11: Find 1-3 bridge tracks to transition between subgenres."""
    result = find_bridge_tracks(
        db, from_id=req.from_id,
        target_subgenre=req.target_subgenre,
        target_bpm=req.target_bpm,
        max_steps=req.max_steps or 3,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/dig")
def dig_tracks(
    label: str = None,
    era: str = None,
    subgenre: str = None,
    bpm_min: float = None,
    bpm_max: float = None,
    energy_tag: str = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Phase 4.5: Pure metadata query returning matching tracks."""
    query = db.query(Track)

    if label:
        query = query.filter(Track.label.ilike(f"%{label}%"))
    if era:
        query = query.filter(Track.era == era)
    if bpm_min:
        query = query.filter(Track.bpm >= bpm_min)
    if bpm_max:
        query = query.filter(Track.bpm <= bpm_max)
    if energy_tag:
        query = query.filter(Track.energy_tag == energy_tag)
    if subgenre:
        # Filter by subgenre BPM/energy envelope
        from moods import track_fits_subgenre as _fits
        tracks = query.limit(500).all()
        tracks = [t for t in tracks if _fits(t, subgenre)][:limit]
    else:
        tracks = query.limit(limit).all()

    return {
        "tracks": [
            {"id": t.id, "title": t.title, "artist": t.artist, "bpm": t.bpm,
             "key": t.key, "camelot": t.camelot_code, "energy": t.energy,
             "energy_tag": t.energy_tag, "label": t.label, "era": t.era,
             "duration": t.duration}
            for t in tracks
        ],
        "count": len(tracks),
        "filters": {"label": label, "era": era, "subgenre": subgenre,
                     "bpm_min": bpm_min, "bpm_max": bpm_max, "energy_tag": energy_tag},
    }


@router.post("/cache/invalidate")
def invalidate():
    invalidate_cache()
    return {"status": "ok"}
