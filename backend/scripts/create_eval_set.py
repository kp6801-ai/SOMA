"""
Phase 5.1: Create evaluation set.
Generate 100 track pairs from DB for manual human judgment.
Covers: same-subgenre, cross-subgenre, warmup-to-peak, BPM cliff pairs,
peak-to-ambient failures, known good DJ transitions.
"""

import random
import psycopg2

DB_URL = "postgresql://localhost/soma"

# Transition types to cover
TRANSITION_TYPES = [
    "same_subgenre",       # 30 pairs
    "cross_subgenre",      # 25 pairs
    "warmup_to_peak",      # 15 pairs
    "bpm_cliff",           # 10 pairs
    "peak_to_ambient",     # 10 pairs
    "adjacent_key",        # 10 pairs
]


def create_eval_set():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Ensure evaluation_pairs table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_pairs (
            id SERIAL PRIMARY KEY,
            track_a_id INTEGER REFERENCES tracks(id),
            track_b_id INTEGER REFERENCES tracks(id),
            human_score TEXT,
            transition_type TEXT,
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_eval_pair_tracks ON evaluation_pairs(track_a_id, track_b_id);
    """)
    conn.commit()

    # Get all tracks
    cur.execute("""
        SELECT id, bpm, energy, camelot_code, energy_tag
        FROM tracks WHERE bpm IS NOT NULL
    """)
    tracks = cur.fetchall()
    if len(tracks) < 10:
        print("Not enough tracks in database. Need at least 10.")
        conn.close()
        return

    random.seed(42)
    pairs = []

    # Same subgenre pairs: similar BPM tracks
    print("Generating same-subgenre pairs...")
    for _ in range(30):
        a = random.choice(tracks)
        candidates = [t for t in tracks if t[0] != a[0] and abs(t[1] - a[1]) <= 5]
        if candidates:
            b = random.choice(candidates)
            pairs.append((a[0], b[0], "same_subgenre"))

    # Cross subgenre: different BPM ranges
    print("Generating cross-subgenre pairs...")
    for _ in range(25):
        a = random.choice(tracks)
        candidates = [t for t in tracks if t[0] != a[0] and abs(t[1] - a[1]) > 5]
        if candidates:
            b = random.choice(candidates)
            pairs.append((a[0], b[0], "cross_subgenre"))

    # Warmup to peak: low energy -> high energy
    print("Generating warmup-to-peak pairs...")
    sorted_by_energy = sorted(tracks, key=lambda t: t[2] or 0)
    low_energy = sorted_by_energy[:len(sorted_by_energy)//3]
    high_energy = sorted_by_energy[2*len(sorted_by_energy)//3:]
    for _ in range(15):
        if low_energy and high_energy:
            a = random.choice(low_energy)
            b = random.choice(high_energy)
            pairs.append((a[0], b[0], "warmup_to_peak"))

    # BPM cliff: >15 BPM apart
    print("Generating BPM cliff pairs...")
    for _ in range(10):
        a = random.choice(tracks)
        candidates = [t for t in tracks if t[0] != a[0] and abs(t[1] - a[1]) > 15]
        if candidates:
            b = random.choice(candidates)
            pairs.append((a[0], b[0], "bpm_cliff"))

    # Peak to ambient: high energy to very low
    print("Generating peak-to-ambient pairs...")
    for _ in range(10):
        if high_energy and low_energy:
            a = random.choice(high_energy)
            b = random.choice(low_energy)
            pairs.append((a[0], b[0], "peak_to_ambient"))

    # Adjacent key: Camelot distance = 1
    print("Generating adjacent-key pairs...")
    for _ in range(10):
        a = random.choice(tracks)
        if a[3]:
            candidates = [t for t in tracks if t[0] != a[0] and t[3] and _camelot_dist(a[3], t[3]) == 1]
            if candidates:
                b = random.choice(candidates)
                pairs.append((a[0], b[0], "adjacent_key"))

    # Insert pairs (human_score left NULL for manual judging)
    inserted = 0
    for track_a_id, track_b_id, transition_type in pairs[:100]:
        try:
            cur.execute("""
                INSERT INTO evaluation_pairs (track_a_id, track_b_id, transition_type)
                VALUES (%s, %s, %s)
            """, (track_a_id, track_b_id, transition_type))
            inserted += 1
        except Exception:
            conn.rollback()

    conn.commit()
    conn.close()

    print(f"\nCreated {inserted} evaluation pairs.")
    print("Now manually judge each pair as: bad / usable / strong / excellent")
    print("Run: psql soma -c \"UPDATE evaluation_pairs SET human_score='strong' WHERE id=1\"")


def _camelot_dist(a: str, b: str) -> int:
    try:
        mode_a, mode_b = a[-1], b[-1]
        num_a, num_b = int(a[:-1]), int(b[:-1])
        if mode_a != mode_b:
            return 2
        return min(abs(num_a - num_b), 12 - abs(num_a - num_b))
    except Exception:
        return 3


if __name__ == "__main__":
    create_eval_set()
