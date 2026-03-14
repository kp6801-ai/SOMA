"""
Phase 3.4: Classify all tracks as warmup/groove/peak/closer based on energy percentiles.
- warmup: <30th percentile
- groove: 30-60th percentile
- peak: 60-85th percentile
- closer: >85th percentile OR falling energy pattern
"""

import psycopg2
import numpy as np

DB_URL = "postgresql://localhost/soma"


def tag_energy():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Get all tracks with energy
    cur.execute("SELECT id, energy FROM tracks WHERE energy IS NOT NULL ORDER BY energy")
    rows = cur.fetchall()

    if not rows:
        print("No tracks with energy data found.")
        conn.close()
        return

    energies = np.array([r[1] for r in rows])
    p30 = np.percentile(energies, 30)
    p60 = np.percentile(energies, 60)
    p85 = np.percentile(energies, 85)

    print(f"Energy percentiles: P30={p30:.2f}  P60={p60:.2f}  P85={p85:.2f}")
    print(f"Total tracks: {len(rows)}\n")

    counts = {"warmup": 0, "groove": 0, "peak": 0, "closer": 0}

    for track_id, energy in rows:
        if energy < p30:
            tag = "warmup"
        elif energy < p60:
            tag = "groove"
        elif energy < p85:
            tag = "peak"
        else:
            tag = "closer"

        cur.execute("UPDATE tracks SET energy_tag = %s WHERE id = %s", (tag, track_id))
        counts[tag] += 1

    conn.commit()
    conn.close()

    print("Energy tags assigned:")
    for tag, count in counts.items():
        pct = count / len(rows) * 100
        bar = "█" * int(pct / 2)
        print(f"  {tag:<8} {count:>4} ({pct:>5.1f}%) {bar}")

    print(f"\nTotal: {sum(counts.values())} tracks tagged")


if __name__ == "__main__":
    tag_energy()
