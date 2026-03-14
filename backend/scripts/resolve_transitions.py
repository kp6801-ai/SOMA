"""
Phase 5: Resolve scraped DJ transitions to local tracks.
Uses fuzzy matching on title + artist to link dj_transitions to tracks.
Aggregates into transition_scores table.

Usage:
    python scripts/resolve_transitions.py              # resolve unresolved transitions
    python scripts/resolve_transitions.py --rebuild     # re-resolve all + rebuild scores
    python scripts/resolve_transitions.py --threshold 80  # custom fuzzy match threshold
"""

import sys
import argparse
import psycopg2
import psycopg2.extras
from difflib import SequenceMatcher

DB_URL = "postgresql://localhost/soma"

DEFAULT_THRESHOLD = 75  # fuzzy match percentage threshold


def _normalize_text(text: str) -> str:
    """Normalize text for fuzzy matching."""
    if not text:
        return ""
    return text.lower().strip().replace("  ", " ")


def _fuzzy_score(a: str, b: str) -> float:
    """Return fuzzy match score 0-100."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, _normalize_text(a), _normalize_text(b)).ratio() * 100


def _find_best_match(title: str, artist: str, tracks: list, threshold: float) -> int:
    """Find the best matching track ID from local database."""
    best_id = None
    best_score = 0.0

    for track in tracks:
        # Weighted: 60% title match + 40% artist match
        title_score = _fuzzy_score(title, track["title"])
        artist_score = _fuzzy_score(artist, track["artist"])
        combined = 0.6 * title_score + 0.4 * artist_score

        if combined > best_score and combined >= threshold:
            best_score = combined
            best_id = track["id"]

    return best_id


def resolve_transitions(conn, threshold: float = DEFAULT_THRESHOLD, rebuild: bool = False):
    """Match scraped transitions to local tracks using fuzzy matching."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Load all local tracks for matching
    cur.execute("SELECT id, title, artist FROM tracks")
    local_tracks = [dict(row) for row in cur.fetchall()]
    print(f"Local tracks: {len(local_tracks)}")

    if not local_tracks:
        print("⚠ No tracks in database — run extract_features.py first")
        return 0

    # Fetch unresolved transitions
    if rebuild:
        cur.execute("SELECT id, track_a_title, track_a_artist, track_b_title, track_b_artist FROM dj_transitions")
    else:
        cur.execute("""
            SELECT id, track_a_title, track_a_artist, track_b_title, track_b_artist
            FROM dj_transitions WHERE resolved = FALSE
        """)

    transitions = cur.fetchall()
    print(f"Transitions to resolve: {len(transitions)}")

    resolved = 0
    update_cur = conn.cursor()

    for t in transitions:
        a_id = _find_best_match(t["track_a_title"], t["track_a_artist"], local_tracks, threshold)
        b_id = _find_best_match(t["track_b_title"], t["track_b_artist"], local_tracks, threshold)

        is_resolved = a_id is not None and b_id is not None and a_id != b_id

        update_cur.execute("""
            UPDATE dj_transitions SET
                track_a_id = %s, track_b_id = %s, resolved = %s
            WHERE id = %s
        """, (a_id, b_id, is_resolved, t["id"]))

        if is_resolved:
            resolved += 1

    conn.commit()
    print(f"✓ Resolved: {resolved}/{len(transitions)} transitions")
    return resolved


def build_transition_scores(conn):
    """Aggregate resolved transitions into transition_scores table."""
    cur = conn.cursor()

    # Clear existing scores if rebuilding
    cur.execute("DELETE FROM transition_scores")

    # Aggregate: count how many DJs played each pair, compute avg position
    cur.execute("""
        INSERT INTO transition_scores (track_a_id, track_b_id, times_played, avg_position_pct, confidence)
        SELECT
            track_a_id,
            track_b_id,
            COUNT(DISTINCT tracklist_id) as times_played,
            AVG(
                CASE WHEN position_in_set IS NOT NULL
                THEN position_in_set::float / GREATEST(
                    (SELECT MAX(d2.position_in_set) FROM dj_transitions d2
                     WHERE d2.tracklist_id = dj_transitions.tracklist_id), 1
                )
                ELSE 0.5 END
            ) as avg_position_pct,
            -- Confidence: sqrt(count) / 5, capped at 1.0
            LEAST(SQRT(COUNT(DISTINCT tracklist_id)::float) / 5.0, 1.0) as confidence
        FROM dj_transitions
        WHERE resolved = TRUE AND track_a_id IS NOT NULL AND track_b_id IS NOT NULL
        GROUP BY track_a_id, track_b_id
        ON CONFLICT (track_a_id, track_b_id) DO UPDATE SET
            times_played = EXCLUDED.times_played,
            avg_position_pct = EXCLUDED.avg_position_pct,
            confidence = EXCLUDED.confidence
    """)

    cur.execute("SELECT COUNT(*) FROM transition_scores")
    count = cur.fetchone()[0]
    conn.commit()

    print(f"✓ {count} unique transition scores computed")
    return count


def main():
    parser = argparse.ArgumentParser(description="Resolve DJ transitions to local tracks")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help=f"Fuzzy match threshold (0-100, default {DEFAULT_THRESHOLD})")
    parser.add_argument("--rebuild", action="store_true",
                        help="Re-resolve all transitions and rebuild scores")
    args = parser.parse_args()

    conn = psycopg2.connect(DB_URL)

    # Ensure tables exist
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transition_scores (
            id SERIAL PRIMARY KEY,
            track_a_id INTEGER NOT NULL REFERENCES tracks(id),
            track_b_id INTEGER NOT NULL REFERENCES tracks(id),
            times_played INTEGER DEFAULT 1,
            avg_position_pct FLOAT,
            confidence FLOAT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_trans_score_pair
            ON transition_scores(track_a_id, track_b_id);
    """)
    conn.commit()

    # Step 1: Resolve transitions
    resolved = resolve_transitions(conn, args.threshold, args.rebuild)

    # Step 2: Build aggregated scores
    if resolved > 0 or args.rebuild:
        build_transition_scores(conn)

    conn.close()
    print("\n✅ Done")


if __name__ == "__main__":
    main()
