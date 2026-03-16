"""
M2 Session Service — creates a fully planned session arc upfront.
"""

from sqlalchemy.orm import Session as DBSession
from database import SomaSession, SessionTrack, Track
from arc_presets import get_preset, tracks_for_duration, build_bpm_steps
from recommender import recommend_tracks


def create_session(db: DBSession, arc_type: str, duration_min: int) -> dict:
    """
    Plan a full session:
    1. Look up arc preset → get BPM shape
    2. Generate one target BPM per track slot
    3. Pick a track for each slot using the recommender
    4. Save session + all track slots to Postgres
    5. Return the full session payload
    """
    preset = get_preset(arc_type)
    n_tracks = tracks_for_duration(duration_min)
    bpm_steps = build_bpm_steps(preset, n_tracks)

    # Create the session row
    session = SomaSession(
        arc_type=arc_type.lower().replace(" ", "_"),
        duration_min=duration_min,
        bpm_start=preset["bpm_start"],
        bpm_peak=preset["bpm_peak"],
        bpm_end=preset["bpm_end"],
        total_tracks=n_tracks,
        status="active",
    )
    db.add(session)
    db.flush()  # get session.id before inserting session_tracks

    # Pick one track per BPM step
    used_ids: set[int] = set()
    slots = []

    try:
        for position, target_bpm in enumerate(bpm_steps, start=1):
            # Get candidates, exclude already-used tracks
            candidates = recommend_tracks(db, bpm=target_bpm, limit=20)
            candidates = [c for c in candidates if c["id"] not in used_ids]

            if not candidates:
                # Relax: allow reuse if we've exhausted the catalog
                candidates = recommend_tracks(db, bpm=target_bpm, limit=5)

            if not candidates:
                continue

            chosen = candidates[0]
            used_ids.add(chosen["id"])

            slot = SessionTrack(
                session_id=session.id,
                track_id=chosen["id"],
                position=position,
                target_bpm=target_bpm,
                status="pending",
            )
            db.add(slot)
            slots.append({
                "position": position,
                "target_bpm": target_bpm,
                "track_id": chosen["id"],
                "title": chosen["title"],
                "artist": chosen["artist"],
                "bpm": chosen["bpm"],
                "camelot": chosen.get("camelot"),
                "energy": chosen.get("energy"),
                "score": chosen.get("score"),
            })

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "session_id": session.id,
        "arc_type": session.arc_type,
        "arc_label": preset["label"],
        "duration_min": duration_min,
        "bpm_start": preset["bpm_start"],
        "bpm_peak": preset["bpm_peak"],
        "bpm_end": preset["bpm_end"],
        "total_tracks": len(slots),
        "status": "active",
        "tracks": slots,
    }


def get_session(db: DBSession, session_id: int) -> dict:
    """Return a session with its full track list and current statuses."""
    session = db.query(SomaSession).filter(SomaSession.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}

    slot_rows = (
        db.query(SessionTrack, Track)
        .join(Track, SessionTrack.track_id == Track.id)
        .filter(SessionTrack.session_id == session_id)
        .order_by(SessionTrack.position)
        .all()
    )

    tracks = [
        {
            "position": st.position,
            "target_bpm": st.target_bpm,
            "status": st.status,
            "resonance_rating": st.resonance_rating,
            "track_id": t.id,
            "title": t.title,
            "artist": t.artist,
            "bpm": t.bpm,
            "camelot": t.camelot_code,
            "energy": t.energy,
        }
        for st, t in slot_rows
    ]

    return {
        "session_id": session.id,
        "arc_type": session.arc_type,
        "duration_min": session.duration_min,
        "bpm_start": session.bpm_start,
        "bpm_peak": session.bpm_peak,
        "bpm_end": session.bpm_end,
        "status": session.status,
        "total_tracks": session.total_tracks,
        "created_at": session.created_at.isoformat(),
        "tracks": tracks,
    }


def next_track(db: DBSession, session_id: int) -> dict:
    """Return the next pending track in the session."""
    slot = (
        db.query(SessionTrack)
        .filter(
            SessionTrack.session_id == session_id,
            SessionTrack.status == "pending",
        )
        .order_by(SessionTrack.position)
        .first()
    )

    if not slot:
        return {"done": True, "message": "Session complete — no more tracks."}

    track = db.query(Track).filter(Track.id == slot.track_id).first()
    from datetime import datetime
    slot.status = "playing"
    slot.played_at = datetime.utcnow()
    db.commit()

    return {
        "position": slot.position,
        "target_bpm": slot.target_bpm,
        "track_id": track.id,
        "title": track.title,
        "artist": track.artist,
        "bpm": track.bpm,
        "camelot": track.camelot_code,
        "energy": track.energy,
        "duration": track.duration,
        "audio_url": getattr(track, "source_url", None),
    }


def record_event(db: DBSession, session_id: int, event: str,
                 position: int, rating: int | None = None) -> dict:
    """
    Record a playback event for a track slot.
    event: "completed" | "skipped"
    """
    from datetime import datetime

    slot = (
        db.query(SessionTrack)
        .filter(
            SessionTrack.session_id == session_id,
            SessionTrack.position == position,
        )
        .first()
    )

    if not slot:
        return {"error": f"No slot at position {position} in session {session_id}"}

    slot.status = event  # "completed" or "skipped"
    slot.ended_at = datetime.utcnow()
    if rating is not None:
        if not (1 <= rating <= 5):
            return {"error": "Rating must be between 1 and 5"}
        slot.resonance_rating = rating

    db.commit()
    return {"session_id": session_id, "position": position, "status": slot.status}


def get_summary(db: DBSession, session_id: int) -> dict:
    """Session summary — stats on what was played, skipped, rated."""
    from datetime import datetime

    session = db.query(SomaSession).filter(SomaSession.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}

    slots = (
        db.query(SessionTrack)
        .filter(SessionTrack.session_id == session_id)
        .all()
    )

    completed = [s for s in slots if s.status == "completed"]
    skipped = [s for s in slots if s.status == "skipped"]
    ratings = [s.resonance_rating for s in slots if s.resonance_rating is not None]

    # Mark session as completed
    if session.status == "active":
        session.status = "completed"
        session.ended_at = datetime.utcnow()
        db.commit()

    return {
        "session_id": session_id,
        "arc_type": session.arc_type,
        "duration_min": session.duration_min,
        "total_tracks": session.total_tracks,
        "completed": len(completed),
        "skipped": len(skipped),
        "avg_resonance": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "status": session.status,
    }
