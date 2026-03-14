"""
Phase 4.1: Discogs ingestion.
Fetch 50 releases per label for 15 key techno labels.
Populate discogs_tracks with label, year, artist, style, cover_url.
Requires DISCOGS_TOKEN env var (personal access token).
"""

import os
import sys
import time
import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "postgresql://localhost/soma")
DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN", "")
BASE_URL = "https://api.discogs.com"
HEADERS = {
    "User-Agent": "SOMA/1.0",
    "Authorization": f"Discogs token={DISCOGS_TOKEN}" if DISCOGS_TOKEN else "",
}

LABELS = [
    "Tresor", "Ostgut Ton", "Hardwax", "Drumcode", "Kompakt",
    "Perlon", "Mute", "R&S Records", "Planet E", "Minus",
    "CLR", "Soma", "Cocoon", "Bpitch Control", "Delsin",
]

RELEASES_PER_LABEL = 50


def ensure_discogs_table(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS discogs_tracks (
            id SERIAL PRIMARY KEY,
            discogs_release_id INTEGER,
            title TEXT,
            artist TEXT,
            label TEXT,
            year INTEGER,
            style TEXT,
            genre TEXT,
            cover_url TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(discogs_release_id, title)
        );
        CREATE INDEX IF NOT EXISTS idx_discogs_label ON discogs_tracks(label);
        CREATE INDEX IF NOT EXISTS idx_discogs_year ON discogs_tracks(year);
    """)
    conn.commit()


def search_label(label_name: str, per_page: int = RELEASES_PER_LABEL) -> list:
    """Search Discogs for releases on a label."""
    url = f"{BASE_URL}/database/search"
    params = {
        "label": label_name,
        "genre": "Electronic",
        "style": "Techno",
        "type": "release",
        "per_page": per_page,
        "page": 1,
    }
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if resp.status_code == 429:
            print(f"  Rate limited. Waiting 60s...")
            time.sleep(60)
            resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("results", [])
    except Exception as e:
        print(f"  Error searching {label_name}: {e}")
        return []


def fetch_release_tracks(release_id: int) -> list:
    """Fetch tracklist from a Discogs release."""
    url = f"{BASE_URL}/releases/{release_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 429:
            time.sleep(60)
            resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("tracklist", []), data
    except Exception as e:
        return [], {}


def main():
    if not DISCOGS_TOKEN:
        print("Set DISCOGS_TOKEN env var (Discogs personal access token)")
        print("Get one at: https://www.discogs.com/settings/developers")
        sys.exit(1)

    conn = psycopg2.connect(DB_URL)
    ensure_discogs_table(conn)
    cur = conn.cursor()

    total_inserted = 0

    for label_name in LABELS:
        print(f"\n{'='*50}")
        print(f"Label: {label_name}")
        print(f"{'='*50}")

        releases = search_label(label_name)
        print(f"  Found {len(releases)} releases")

        for i, release in enumerate(releases):
            release_id = release.get("id")
            if not release_id:
                continue

            tracklist, release_data = fetch_release_tracks(release_id)
            year = release_data.get("year", release.get("year"))
            cover = release.get("cover_image", "")
            styles = ", ".join(release_data.get("styles", release.get("style", [])))
            genres = ", ".join(release_data.get("genres", release.get("genre", [])))

            for track in tracklist:
                title = track.get("title", "")
                if not title:
                    continue

                artists = track.get("artists")
                if artists:
                    artist = ", ".join(a.get("name", "") for a in artists)
                else:
                    artist = release_data.get("artists_sort", "Unknown")

                try:
                    cur.execute("""
                        INSERT INTO discogs_tracks
                            (discogs_release_id, title, artist, label, year, style, genre, cover_url)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (discogs_release_id, title) DO NOTHING
                    """, (release_id, title, artist, label_name, year, styles, genres, cover))
                    total_inserted += cur.rowcount
                except Exception as e:
                    conn.rollback()
                    continue

            conn.commit()

            if (i + 1) % 10 == 0:
                print(f"  Processed {i+1}/{len(releases)} releases...")

            # Respect rate limit: 60 req/min for authenticated
            time.sleep(1.5)

    conn.close()
    print(f"\n{'='*50}")
    print(f"Total tracks inserted: {total_inserted}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
