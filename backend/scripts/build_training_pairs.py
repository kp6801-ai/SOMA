"""
build_training_pairs.py — Resolve fingerprinted transitions to SOMA track IDs.

Usage:
  python build_training_pairs.py --transitions-file ./dj_sets/all_transitions.json
  python build_training_pairs.py --transitions-file ./dj_sets/all_transitions.json --insert-stubs

What it does:
  1. Fuzzy-matches track title+artist to existing tracks in the DB
  2. Inserts/updates dj_transitions rows
  3. Upserts transition_scores (times_played, confidence)
  4. Optionally inserts stub Track rows for unrecognized tracks
"""

import argparse
import json
import logging
import os
import sys
from difflib import SequenceMatcher
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Allow running from scripts/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal, Track, DJTransition, TransitionScore


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def find_track(db, title: str, artist: str, threshold: float = 0.70) -> Track | None:
    """Fuzzy-match title+artist against all tracks in DB."""
    # Fast path: exact match
    exact = db.query(Track).filter(
        Track.title.ilike(title),
        Track.artist.ilike(artist)
    ).first()
    if exact:
        return exact

    # Slow path: load all and fuzzy match (fine for small catalogs < 10k)
    candidates = db.query(Track).all()
    best_score = 0.0
    best_track = None

    for t in candidates:
        title_sim = similarity(title, t.title or "")
        artist_sim = similarity(artist, t.artist or "")
        combined = 0.6 * title_sim + 0.4 * artist_sim
        if combined > best_score:
            best_score = combined
            best_track = t

    if best_score >= threshold:
        return best_track
    return None


def upsert_transition_score(db, track_a_id: int, track_b_id: int):
    """Increment times_played and update confidence in transition_scores."""
    ts = db.query(TransitionScore).filter(
        TransitionScore.track_a_id == track_a_id,
        TransitionScore.track_b_id == track_b_id,
    ).first()

    if ts:
        ts.times_played = (ts.times_played or 0) + 1
        # Confidence increases as more DJs confirm the same transition
        ts.confidence = min(1.0, (ts.confidence or 0.5) + 0.1)
    else:
        db.add(TransitionScore(
            track_a_id=track_a_id,
            track_b_id=track_b_id,
            times_played=1,
            confidence=0.5,
        ))


def main():
    parser = argparse.ArgumentParser(description="Build DB training pairs from fingerprinted transitions")
    parser.add_argument("--transitions-file", required=True, help="all_transitions.json from fingerprint_tracks.py")
    parser.add_argument("--insert-stubs", action="store_true",
                        help="Insert stub Track rows for unmatched tracks (title+artist only)")
    parser.add_argument("--match-threshold", type=float, default=0.70,
                        help="Fuzzy match threshold 0-1 (default 0.70)")
    args = parser.parse_args()

    with open(args.transitions_file) as f:
        transitions = json.load(f)

    log.info(f"Loaded {len(transitions)} transitions from {args.transitions_file}")

    db = SessionLocal()
    total = resolved = unresolved = stubs_inserted = 0

    try:
        for t in transitions:
            total += 1
            a_title = t.get("track_a_title", "")
            a_artist = t.get("track_a_artist", "")
            b_title = t.get("track_b_title", "")
            b_artist = t.get("track_b_artist", "")

            track_a = find_track(db, a_title, a_artist, args.match_threshold)
            track_b = find_track(db, b_title, b_artist, args.match_threshold)

            # Optionally insert stubs for unrecognized tracks
            if not track_a and args.insert_stubs and a_title:
                track_a = Track(title=a_title, artist=a_artist, source_platform="youtube")
                db.add(track_a)
                db.flush()
                stubs_inserted += 1
                log.debug(f"  Stub inserted: {a_artist} - {a_title}")

            if not track_b and args.insert_stubs and b_title:
                track_b = Track(title=b_title, artist=b_artist, source_platform="youtube")
                db.add(track_b)
                db.flush()
                stubs_inserted += 1
                log.debug(f"  Stub inserted: {b_artist} - {b_title}")

            if track_a and track_b:
                resolved += 1

                # Insert dj_transitions row
                db.add(DJTransition(
                    tracklist_id=t.get("video_id", "youtube"),
                    dj_name=t.get("dj_name", "Unknown"),
                    event_name=t.get("set_title", ""),
                    position_in_set=int(t.get("track_a_start_sec", 0) // 60),
                    track_a_title=a_title,
                    track_a_artist=a_artist,
                    track_b_title=b_title,
                    track_b_artist=b_artist,
                    track_a_id=track_a.id,
                    track_b_id=track_b.id,
                    resolved=True,
                ))

                # Upsert transition_scores
                upsert_transition_score(db, track_a.id, track_b.id)

            else:
                unresolved += 1
                log.debug(
                    f"  Unresolved: '{a_artist} - {a_title}' → '{b_artist} - {b_title}' "
                    f"(a_found={track_a is not None}, b_found={track_b is not None})"
                )

            if total % 100 == 0:
                db.commit()
                log.info(f"  Progress: {total}/{len(transitions)} | resolved={resolved}")

        db.commit()

    except Exception as e:
        db.rollback()
        log.error(f"DB error: {e}")
        raise
    finally:
        db.close()

    resolve_pct = (resolved / total * 100) if total else 0
    log.info(f"\n{'='*50}")
    log.info(f"Total pairs:       {total}")
    log.info(f"Resolved:          {resolved} ({resolve_pct:.1f}%)")
    log.info(f"Unresolved:        {unresolved}")
    if args.insert_stubs:
        log.info(f"Stubs inserted:    {stubs_inserted}")
    log.info(f"\nNext step:\n  python generate_negatives.py")
    log.info(f"  python train_transition_model.py")


if __name__ == "__main__":
    main()
