"""
Phase 0.3: Verify feature consistency across all tracks.
SELECT MIN/MAX/AVG/STDDEV for each feature.
Flag outlier tracks > 3 standard deviations from mean.
"""

import psycopg2
import sys

DB_URL = "postgresql://localhost/soma"

FEATURES = ["energy", "bpm", "danceability", "brightness", "loudness"]


def verify():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("=" * 70)
    print("SOMA Feature Verification Report")
    print("=" * 70)

    # Overall stats
    cur.execute("SELECT COUNT(*) FROM tracks")
    total = cur.fetchone()[0]
    print(f"\nTotal tracks: {total}\n")

    if total == 0:
        print("No tracks in database. Nothing to verify.")
        conn.close()
        return

    # Feature statistics
    print(f"{'Feature':<15} {'MIN':>10} {'MAX':>10} {'AVG':>10} {'STDDEV':>10}")
    print("-" * 55)

    stats = {}
    for feat in FEATURES:
        cur.execute(f"""
            SELECT MIN({feat}), MAX({feat}),
                   ROUND(AVG({feat})::numeric, 4),
                   ROUND(STDDEV({feat})::numeric, 4)
            FROM tracks WHERE {feat} IS NOT NULL
        """)
        row = cur.fetchone()
        stats[feat] = {"min": row[0], "max": row[1], "avg": float(row[2] or 0), "std": float(row[3] or 0)}
        print(f"{feat:<15} {row[0]:>10.4f} {row[1]:>10.4f} {row[2]:>10} {row[3]:>10}")

    # NULL check
    print(f"\n{'Feature':<15} {'NULL count':>10} {'% NULL':>10}")
    print("-" * 35)
    for feat in FEATURES:
        cur.execute(f"SELECT COUNT(*) FROM tracks WHERE {feat} IS NULL")
        null_count = cur.fetchone()[0]
        pct = (null_count / total * 100) if total > 0 else 0
        print(f"{feat:<15} {null_count:>10} {pct:>9.1f}%")

    # Outlier detection: > 3 standard deviations from mean
    print(f"\n{'=' * 70}")
    print("OUTLIER TRACKS (> 3 std deviations from mean)")
    print("=" * 70)

    outlier_count = 0
    for feat in FEATURES:
        avg = stats[feat]["avg"]
        std = stats[feat]["std"]
        if std == 0:
            continue

        lower = avg - 3 * std
        upper = avg + 3 * std

        cur.execute(f"""
            SELECT id, title, artist, {feat}
            FROM tracks
            WHERE {feat} IS NOT NULL AND ({feat} < %s OR {feat} > %s)
            ORDER BY ABS({feat} - %s) DESC
            LIMIT 20
        """, (lower, upper, avg))

        rows = cur.fetchall()
        if rows:
            print(f"\n  {feat.upper()} outliers (range: {lower:.4f} - {upper:.4f}):")
            for row in rows:
                deviation = abs(row[3] - avg) / std
                print(f"    ID {row[0]:>4} | {row[1][:30]:<30} | {feat}={row[3]:.4f} ({deviation:.1f}σ)")
                outlier_count += 1

    if outlier_count == 0:
        print("\n  No outliers found.")

    # Version check
    print(f"\n{'=' * 70}")
    print("VERSION TRACKING")
    print("=" * 70)
    cur.execute("""
        SELECT analysis_version, feature_extractor_version, COUNT(*)
        FROM tracks
        GROUP BY analysis_version, feature_extractor_version
    """)
    rows = cur.fetchall()
    if rows:
        print(f"\n  {'Analysis Ver':<15} {'Extractor Ver':<15} {'Count':>8}")
        print("  " + "-" * 40)
        for row in rows:
            print(f"  {str(row[0] or 'NULL'):<15} {str(row[1] or 'NULL'):<15} {row[2]:>8}")
    else:
        print("\n  No version data found (tracks may need re-extraction).")

    # Structural features coverage
    print(f"\n{'=' * 70}")
    print("STRUCTURAL FEATURES COVERAGE")
    print("=" * 70)
    for col in ["intro_bars", "outro_bars", "has_clean_intro", "has_clean_outro",
                "first_breakdown_bar", "drop_bar", "groove_stability", "energy_tag"]:
        cur.execute(f"SELECT COUNT(*) FROM tracks WHERE {col} IS NOT NULL")
        count = cur.fetchone()[0]
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {col:<25} {count:>6} / {total} ({pct:.0f}%)")

    conn.close()
    print(f"\n{'=' * 70}")
    print(f"Total outliers flagged: {outlier_count}")
    print("=" * 70)


if __name__ == "__main__":
    verify()
