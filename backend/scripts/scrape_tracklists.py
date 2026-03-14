"""
Phase 5: Scrape DJ tracklists from 1001Tracklists.
Extracts consecutive track pairs as transitions for the learning pipeline.

Usage:
    python scripts/scrape_tracklists.py --url "https://www.1001tracklists.com/tracklist/..."
    python scripts/scrape_tracklists.py --dj "Charlotte de Witte" --limit 20
    python scripts/scrape_tracklists.py --genre techno --limit 50

Note: Respects rate limits. Use responsibly.
"""

import sys
import time
import argparse
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import psycopg2
import psycopg2.extras

DB_URL = "postgresql://localhost/soma"
BASE_URL = "https://www.1001tracklists.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
}

RATE_LIMIT_SECS = 3  # seconds between requests


def _parse_tracklist_page(html: str) -> dict:
    """Parse a 1001Tracklists page and extract track listing."""
    soup = BeautifulSoup(html, "html.parser")

    # Extract event metadata
    meta = {}
    title_el = soup.find("meta", property="og:title")
    if title_el:
        meta["title"] = title_el.get("content", "")

    # Parse DJ name from breadcrumbs or title
    meta["dj_name"] = ""
    meta["event_name"] = ""
    meta["event_date"] = None

    # Try to get DJ name
    dj_link = soup.find("a", class_="action")
    if dj_link:
        meta["dj_name"] = dj_link.text.strip()

    # Parse tracks
    tracks = []
    track_items = soup.find_all("div", class_="tlpItem")
    if not track_items:
        # Alternative selectors
        track_items = soup.find_all("div", attrs={"data-trk": True})

    for item in track_items:
        track = {}

        # Track title/artist from value spans
        title_span = item.find("span", class_="trackValue")
        if title_span:
            full_text = title_span.get_text(separator=" - ", strip=True)
            if " - " in full_text:
                parts = full_text.split(" - ", 1)
                track["artist"] = parts[0].strip()
                track["title"] = parts[1].strip()
            else:
                track["artist"] = "Unknown"
                track["title"] = full_text.strip()
        else:
            # Try meta tags within the item
            meta_title = item.find("meta", itemprop="name")
            meta_artist = item.find("meta", itemprop="byArtist")
            track["title"] = meta_title.get("content", "Unknown") if meta_title else "Unknown"
            track["artist"] = meta_artist.get("content", "Unknown") if meta_artist else "Unknown"

        if track.get("title") and track["title"] != "Unknown":
            tracks.append(track)

    return {"meta": meta, "tracks": tracks}


def scrape_tracklist(url: str) -> dict:
    """Fetch and parse a single tracklist URL."""
    print(f"  Fetching: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return _parse_tracklist_page(resp.text)


def search_tracklists(query: str, limit: int = 20) -> list:
    """Search 1001Tracklists for tracklists matching a query."""
    search_url = f"{BASE_URL}/search/result.php?search_selection=2&search_value={query}"
    print(f"Searching: {query}")
    resp = requests.get(search_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    links = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/tracklist/" in href and href not in links:
            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            links.append(full_url)
            if len(links) >= limit:
                break

    return links


def store_transitions(conn, tracklist_id: str, tracklist_data: dict):
    """Store consecutive track pairs as DJ transitions."""
    tracks = tracklist_data["tracks"]
    meta = tracklist_data["meta"]

    if len(tracks) < 2:
        print(f"  ⏭ Less than 2 tracks — skipping")
        return 0

    cur = conn.cursor()

    # Check if this tracklist already exists
    cur.execute("SELECT COUNT(*) FROM dj_transitions WHERE tracklist_id = %s", (tracklist_id,))
    if cur.fetchone()[0] > 0:
        print(f"  ⏭ Already scraped")
        return 0

    inserted = 0
    for i in range(len(tracks) - 1):
        a = tracks[i]
        b = tracks[i + 1]
        cur.execute("""
            INSERT INTO dj_transitions
                (tracklist_id, dj_name, event_name, event_date,
                 position_in_set, track_a_title, track_a_artist,
                 track_b_title, track_b_artist, resolved)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
        """, (
            tracklist_id,
            meta.get("dj_name", ""),
            meta.get("event_name", ""),
            meta.get("event_date"),
            i,
            a.get("title", ""),
            a.get("artist", ""),
            b.get("title", ""),
            b.get("artist", ""),
        ))
        inserted += 1

    conn.commit()
    print(f"  ✓ {inserted} transitions stored")
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Scrape DJ tracklists from 1001Tracklists")
    parser.add_argument("--url", help="Single tracklist URL to scrape")
    parser.add_argument("--dj", help="DJ name to search for")
    parser.add_argument("--genre", help="Genre to search for (e.g., 'techno')")
    parser.add_argument("--limit", type=int, default=10, help="Max tracklists to scrape")
    args = parser.parse_args()

    conn = psycopg2.connect(DB_URL)

    # Ensure table exists
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dj_transitions (
            id SERIAL PRIMARY KEY,
            tracklist_id TEXT NOT NULL,
            dj_name TEXT, event_name TEXT, event_date TIMESTAMPTZ,
            position_in_set INTEGER,
            track_a_title TEXT, track_a_artist TEXT,
            track_b_title TEXT, track_b_artist TEXT,
            track_a_id INTEGER, track_b_id INTEGER,
            resolved BOOLEAN DEFAULT FALSE
        );
        CREATE INDEX IF NOT EXISTS idx_dj_trans_tracklist ON dj_transitions(tracklist_id);
    """)
    conn.commit()

    total_transitions = 0

    if args.url:
        # Scrape single URL
        tracklist_id = args.url.split("/")[-1].split(".")[0]
        data = scrape_tracklist(args.url)
        total_transitions += store_transitions(conn, tracklist_id, data)
    else:
        # Search and scrape multiple
        query = args.dj or args.genre or "techno"
        urls = search_tracklists(query, args.limit)
        print(f"\nFound {len(urls)} tracklists\n")

        for url in urls:
            try:
                tracklist_id = url.split("/")[-1].split(".")[0]
                data = scrape_tracklist(url)
                total_transitions += store_transitions(conn, tracklist_id, data)
                time.sleep(RATE_LIMIT_SECS)  # respect rate limits
            except Exception as e:
                print(f"  ✗ Error: {e}")
                continue

    conn.close()
    print(f"\n{'='*60}")
    print(f"✅ Total transitions scraped: {total_transitions}")


if __name__ == "__main__":
    main()
