"""
Phase 4.2: FMA bulk ingestion.
Query FMA API for techno/minimal/industrial/acid tags.
Download MP3 -> Essentia -> save to tracks -> delete MP3.
"""

import os
import sys
import tempfile
import requests
import psycopg2
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from scripts.extract_features import extract_features, insert_batch, ensure_schema

DB_URL = os.getenv("DATABASE_URL", "postgresql://localhost/soma")
FMA_API = "https://freemusicarchive.org/api/get"
FMA_KEY = os.getenv("FMA_API_KEY", "")

GENRE_TAGS = ["techno", "minimal", "industrial", "acid", "electronic"]
TRACKS_PER_GENRE = 200


def fetch_fma_tracks(genre_tag: str, limit: int = TRACKS_PER_GENRE) -> list:
    """Fetch track metadata from FMA API."""
    # FMA small dataset: direct download approach
    # For larger sets, use the FMA metadata CSV
    url = f"https://freemusicarchive.org/api/get/tracks.json"
    params = {
        "api_key": FMA_KEY,
        "genre_handle": genre_tag,
        "limit": limit,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("dataset", [])
    except Exception as e:
        print(f"  FMA API error for {genre_tag}: {e}")
        return []


def download_and_process(track_url: str, track_meta: dict, tmp_dir: str) -> dict:
    """Download MP3, extract features, return feature dict."""
    if not track_url:
        return None

    tmp_path = os.path.join(tmp_dir, f"fma_{track_meta.get('track_id', 'unknown')}.mp3")

    try:
        resp = requests.get(track_url, timeout=30, stream=True)
        resp.raise_for_status()
        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)

        features = extract_features(tmp_path)

        # Override with FMA metadata
        features["title"] = track_meta.get("track_title", features["title"])
        features["artist"] = track_meta.get("artist_name", features["artist"])
        features["file_path"] = f"fma:{track_meta.get('track_id', '')}"
        features["source_platform"] = "fma"
        features["source_url"] = track_url
        features["license_type"] = track_meta.get("license_title", "Unknown")
        features["commercial_use_allowed"] = "CC0" in features.get("license_type", "") or \
                                              "CC-BY" in features.get("license_type", "")

        return features
    except Exception as e:
        print(f"  Failed: {e}")
        return None
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main():
    if not FMA_KEY:
        print("FMA API key not set. Using local FMA small dataset fallback.")
        print("Set FMA_API_KEY env var for API access.")
        print("\nAlternative: Use batch_ingest.py with pre-downloaded FMA files.")
        return

    conn = psycopg2.connect(DB_URL)
    ensure_schema(conn)

    total = 0
    with tempfile.TemporaryDirectory() as tmp_dir:
        for genre in GENRE_TAGS:
            print(f"\n{'='*50}")
            print(f"Genre: {genre}")
            print(f"{'='*50}")

            tracks = fetch_fma_tracks(genre)
            print(f"  Found {len(tracks)} tracks")

            batch = []
            for i, track_meta in enumerate(tracks):
                track_url = track_meta.get("track_file")
                result = download_and_process(track_url, track_meta, tmp_dir)

                if result:
                    batch.append(result)
                    total += 1
                    print(f"  [{i+1}/{len(tracks)}] {result['title'][:40]} BPM={result['bpm']}")

                    if len(batch) >= 10:
                        insert_batch(conn, batch)
                        batch.clear()

            if batch:
                insert_batch(conn, batch)

    conn.close()
    print(f"\nTotal tracks ingested: {total}")


if __name__ == "__main__":
    main()
