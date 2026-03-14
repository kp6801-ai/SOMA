"""
Phase 3: Build 39-dim embeddings for all tracks and store in PostgreSQL.
Combines 13 scalar features + 26 MFCC values into a single normalized embedding.

Usage:
    python scripts/build_embeddings.py              # build all missing embeddings
    python scripts/build_embeddings.py --rebuild     # rebuild all embeddings
    python scripts/build_embeddings.py --pgvector    # also create pgvector index

Requires: pgvector extension installed in PostgreSQL
    CREATE EXTENSION IF NOT EXISTS vector;
"""

import sys
import argparse
import numpy as np
import psycopg2
import psycopg2.extras

DB_URL = "postgresql://localhost/soma"

EMBEDDING_DIM = 39  # 13 scalar + 26 MFCC


def ensure_pgvector(conn):
    """Install pgvector extension and add vector column + index."""
    cur = conn.cursor()
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
        print("✓ pgvector extension enabled")
    except Exception as e:
        conn.rollback()
        print(f"⚠ Could not enable pgvector: {e}")
        print("  Install pgvector: https://github.com/pgvector/pgvector")
        return False

    # Add vector column if not exists
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tracks' AND column_name = 'embedding_vec'
            ) THEN
                ALTER TABLE tracks ADD COLUMN embedding_vec vector(39);
            END IF;
        END $$;
    """)

    # Add segment vector columns
    for col in ['intro_vec', 'peak_vec', 'outro_vec']:
        cur.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'tracks' AND column_name = '{col}'
                ) THEN
                    ALTER TABLE tracks ADD COLUMN {col} vector(39);
                END IF;
            END $$;
        """)

    conn.commit()
    print("✓ Vector columns created")
    return True


def create_ivfflat_index(conn):
    """Create IVFFlat index for fast approximate nearest neighbor search."""
    cur = conn.cursor()

    # Check track count for optimal list size
    cur.execute("SELECT COUNT(*) FROM tracks WHERE embedding_vec IS NOT NULL")
    count = cur.fetchone()[0]

    if count < 100:
        print(f"⚠ Only {count} tracks with embeddings — skipping IVFFlat index (need 100+)")
        print("  Using exact search (brute force) for now")
        return

    # IVFFlat lists = sqrt(n) as rule of thumb
    n_lists = max(1, int(np.sqrt(count)))

    cur.execute("DROP INDEX IF EXISTS idx_tracks_embedding_ivf;")
    cur.execute(f"""
        CREATE INDEX idx_tracks_embedding_ivf
        ON tracks USING ivfflat (embedding_vec vector_cosine_ops)
        WITH (lists = {n_lists});
    """)

    # Segment vector indexes
    for col in ['intro_vec', 'peak_vec', 'outro_vec']:
        idx_name = f"idx_tracks_{col}_ivf"
        cur.execute(f"DROP INDEX IF EXISTS {idx_name};")
        cur.execute(f"""
            CREATE INDEX {idx_name}
            ON tracks USING ivfflat ({col} vector_cosine_ops)
            WITH (lists = {n_lists});
        """)

    conn.commit()
    print(f"✓ IVFFlat indexes created (lists={n_lists} for {count} tracks)")


def normalize_embedding(vec):
    """L2-normalize a vector for cosine similarity via inner product."""
    arr = np.array(vec, dtype=np.float64)
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr = arr / norm
    return arr.tolist()


def build_embeddings(conn, rebuild=False):
    """Build 39-dim embeddings from existing scalar features + MFCC vectors."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Fetch tracks that need embeddings
    if rebuild:
        cur.execute("""
            SELECT id, bpm, energy, danceability, brightness, loudness,
                   spectral_centroid, spectral_flux, spectral_rolloff,
                   zero_crossing_rate, rhythm_strength, onset_rate,
                   dynamic_complexity, hpss_harmonic_ratio,
                   mfcc_vector, embedding,
                   intro_vector, peak_vector, outro_vector
            FROM tracks WHERE bpm IS NOT NULL
        """)
    else:
        cur.execute("""
            SELECT id, bpm, energy, danceability, brightness, loudness,
                   spectral_centroid, spectral_flux, spectral_rolloff,
                   zero_crossing_rate, rhythm_strength, onset_rate,
                   dynamic_complexity, hpss_harmonic_ratio,
                   mfcc_vector, embedding,
                   intro_vector, peak_vector, outro_vector
            FROM tracks WHERE bpm IS NOT NULL AND embedding_vec IS NULL
        """)

    rows = cur.fetchall()
    if not rows:
        print("✓ All tracks already have embeddings")
        return 0

    print(f"Building embeddings for {len(rows)} tracks...")

    # First pass: collect all raw vectors for z-score normalization
    raw_scalars = []
    raw_mfccs = []
    for row in rows:
        scalar = [
            row['bpm'] or 130.0,
            row['energy'] or 0.0,
            row['danceability'] or 0.0,
            row['brightness'] or 0.0,
            abs(row['loudness'] or 0.0),
            row['spectral_centroid'] or 0.0,
            row['spectral_flux'] or 0.0,
            row['spectral_rolloff'] or 0.0,
            row['zero_crossing_rate'] or 0.0,
            row['rhythm_strength'] or 0.0,
            row['onset_rate'] or 0.0,
            row['dynamic_complexity'] or 0.0,
            row['hpss_harmonic_ratio'] or 0.0,
        ]
        raw_scalars.append(scalar)

        mfcc = row['mfcc_vector']
        if mfcc and len(mfcc) == 26:
            raw_mfccs.append(mfcc)
        else:
            raw_mfccs.append([0.0] * 26)

    raw_scalars = np.array(raw_scalars, dtype=np.float64)
    raw_mfccs = np.array(raw_mfccs, dtype=np.float64)

    # Z-score normalize
    scalar_mean = raw_scalars.mean(axis=0)
    scalar_std = raw_scalars.std(axis=0)
    scalar_std[scalar_std == 0] = 1.0

    mfcc_mean = raw_mfccs.mean(axis=0)
    mfcc_std = raw_mfccs.std(axis=0)
    mfcc_std[mfcc_std == 0] = 1.0

    norm_scalars = (raw_scalars - scalar_mean) / scalar_std
    norm_mfccs = (raw_mfccs - mfcc_mean) / mfcc_std

    # Build and store embeddings
    updated = 0
    update_cur = conn.cursor()
    for i, row in enumerate(rows):
        # Combine 13 scalar + 26 MFCC = 39-dim
        combined = np.concatenate([norm_scalars[i], norm_mfccs[i]])
        embedding_vec = normalize_embedding(combined)

        # Segment vectors: normalize using same stats
        segment_updates = {}
        for seg_col, vec_col in [('intro_vector', 'intro_vec'),
                                  ('peak_vector', 'peak_vec'),
                                  ('outro_vector', 'outro_vec')]:
            seg = row[seg_col]
            if seg and len(seg) == 39:
                seg_scalar = np.array(seg[:13], dtype=np.float64)
                seg_mfcc = np.array(seg[13:], dtype=np.float64)
                seg_norm = np.concatenate([
                    (seg_scalar - scalar_mean) / scalar_std,
                    (seg_mfcc - mfcc_mean) / mfcc_std,
                ])
                segment_updates[vec_col] = normalize_embedding(seg_norm)
            else:
                segment_updates[vec_col] = None

        # Update the track
        update_cur.execute("""
            UPDATE tracks SET
                embedding_vec = %s::vector,
                intro_vec = %s::vector,
                peak_vec = %s::vector,
                outro_vec = %s::vector
            WHERE id = %s
        """, (
            str(embedding_vec),
            str(segment_updates['intro_vec']) if segment_updates['intro_vec'] else None,
            str(segment_updates['peak_vec']) if segment_updates['peak_vec'] else None,
            str(segment_updates['outro_vec']) if segment_updates['outro_vec'] else None,
            row['id'],
        ))
        updated += 1
        if updated % 50 == 0:
            conn.commit()
            print(f"  [{updated}/{len(rows)}] embeddings built...")

    conn.commit()
    print(f"✓ {updated} embeddings built and stored")
    return updated


def main():
    parser = argparse.ArgumentParser(description="Build 39-dim track embeddings")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild all embeddings")
    parser.add_argument("--pgvector", action="store_true", help="Setup pgvector + IVFFlat index")
    args = parser.parse_args()

    conn = psycopg2.connect(DB_URL)

    # Always ensure pgvector is available
    has_pgvector = ensure_pgvector(conn)

    if not has_pgvector:
        print("\n⚠ pgvector not available — embeddings stored as FLOAT[] only")
        print("  Install pgvector for native vector similarity search")

    # Build embeddings
    if has_pgvector:
        updated = build_embeddings(conn, rebuild=args.rebuild)

        # Create IVFFlat index if requested
        if args.pgvector and updated > 0:
            create_ivfflat_index(conn)
    else:
        print("Skipping vector operations — install pgvector first")

    conn.close()
    print("\n✅ Done")


if __name__ == "__main__":
    main()
