import requests
import psycopg2
import psycopg2.extras
import time

DB_URL = "postgresql://localhost/soma"

# FMA genre IDs for techno/electronic
GENRE_IDS = [15, 38]  # 15=Techno, 38=Electronic
FMA_API = "https://freemusicarchive.org/api/get/tracks.json"
API_KEY = "60BLHNQCAOUFPIBZ"

def fetch_fma_tracks(genre_id, page=1, limit=50):
    params = {"api_key": API_KEY, "genre_id": genre_id, "limit": limit, "page": page}
    try:
        r = requests.get(FMA_API, params=params, timeout=10)
        data = r.json()
        return data.get("dataset", [])
    except Exception as e:
        print(f"Error: {e}")
        return []

def insert_tracks(conn, tracks):
    rows = []
    for t in tracks:
        title = t.get("track_title", "Unknown")
        artist = t.get("artist_name", "Unknown")
        file_path = f"fma:{t.get('track_id')}"
        rows.append((file_path, title, artist))
    if not rows:
        return 0
    sql = "INSERT INTO tracks (file_path, title, artist) VALUES %s ON CONFLICT (file_path) DO NOTHING"
    cur = conn.cursor()
    psycopg2.extras.execute_values(cur, sql, rows)
    conn.commit()
    return len(rows)

if __name__ == "__main__":
    conn = psycopg2.connect(DB_URL)
    total = 0
    for genre_id in GENRE_IDS:
        for page in range(1, 21):
            tracks = fetch_fma_tracks(genre_id, page=page)
            if not tracks:
                break
            n = insert_tracks(conn, tracks)
            total += n
            print(f"Genre {genre_id} page {page}: +{n} tracks (total: {total})")
            time.sleep(0.3)
    conn.close()
    print(f"\nDone. {total} tracks seeded.")
