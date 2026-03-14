"""
Phase 4.4: Tag tracks with era based on release_year.
- classic: 1988-1995
- second_wave: 1995-2002
- modern: 2010+
"""

import psycopg2

DB_URL = "postgresql://localhost/soma"


def tag_eras():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Tag based on release_year
    cur.execute("""
        UPDATE tracks SET era = 'classic'
        WHERE release_year IS NOT NULL AND release_year >= 1988 AND release_year < 1995
    """)
    classic = cur.rowcount

    cur.execute("""
        UPDATE tracks SET era = 'second_wave'
        WHERE release_year IS NOT NULL AND release_year >= 1995 AND release_year < 2002
    """)
    second_wave = cur.rowcount

    cur.execute("""
        UPDATE tracks SET era = 'modern'
        WHERE release_year IS NOT NULL AND release_year >= 2010
    """)
    modern = cur.rowcount

    # Tracks between 2002-2010 get tagged as second_wave (bridge era)
    cur.execute("""
        UPDATE tracks SET era = 'second_wave'
        WHERE release_year IS NOT NULL AND release_year >= 2002 AND release_year < 2010
        AND era IS NULL
    """)
    bridge = cur.rowcount

    conn.commit()

    # Report
    cur.execute("SELECT era, COUNT(*) FROM tracks WHERE era IS NOT NULL GROUP BY era ORDER BY era")
    rows = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM tracks WHERE era IS NULL")
    untagged = cur.fetchone()[0]

    print("Era tagging complete:")
    print(f"  classic (1988-1995):     {classic}")
    print(f"  second_wave (1995-2010): {second_wave + bridge}")
    print(f"  modern (2010+):          {modern}")
    print(f"  untagged:                {untagged}")
    print(f"\nBreakdown from DB:")
    for era, count in rows:
        print(f"  {era:<15} {count:>5}")

    conn.close()


if __name__ == "__main__":
    tag_eras()
