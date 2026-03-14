import requests
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

DOWNLOAD_DIR = os.path.expanduser("~/Desktop/techno_tracks")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

COLLECTIONS = [
    "top-techno-tracks-house-techno-pumping",
    "top-100-best-techno-vol.06-technoapell",
    "techno-trance",
    "various-artists-techno-dance-rave-collection",
    "techno-trax-collection",
]

def get_all_mp3s(identifier):
    try:
        url = f"https://archive.org/metadata/{identifier}"
        response = requests.get(url, timeout=10)
        data = response.json()
        title = data.get("metadata", {}).get("title", identifier)
        files = data.get("files", [])
        mp3s = []
        for f in files:
            name = f.get("name", "")
            if name.lower().endswith(".mp3"):
                mp3s.append({
                    "url": f"https://archive.org/download/{identifier}/{name}",
                    "title": f.get("title", name),
                    "name": name,
                    "identifier": identifier
                })
        print(f"Collection '{title}' → {len(mp3s)} MP3s found")
        return mp3s
    except Exception as e:
        print(f"Error fetching {identifier}: {e}")
        return []

def download_mp3(track):
    # Flatten subdirectory structure into filename
    name = track["name"].replace("/", "_").replace("\\", "_")
    safe_name = f"{track['identifier']}_{name}"
    output_path = os.path.join(DOWNLOAD_DIR, safe_name)

    if os.path.exists(output_path):
        return True
    try:
        response = requests.get(track["url"], stream=True, timeout=60)
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(2 * 1024 * 1024):
                    f.write(chunk)
            print(f"Downloaded: {track['title']}")
            return True
        else:
            print(f"HTTP {response.status_code}: {track['title']}")
    except Exception as e:
        print(f"Error: {track['title']} - {e}")
    return False

if __name__ == "__main__":
    print("\n=== SOMA Techno Downloader ===")
    print("Collections available:")
    for i, c in enumerate(COLLECTIONS, 1):
        print(f"{i}. {c}")
    print(f"{len(COLLECTIONS)+1}. All collections")

    choice = input("\nChoose collection (1-6): ").strip()

    if choice == str(len(COLLECTIONS)+1):
        selected = COLLECTIONS
    elif choice.isdigit() and 1 <= int(choice) <= len(COLLECTIONS):
        selected = [COLLECTIONS[int(choice)-1]]
    else:
        print("Invalid choice")
        exit()

    all_tracks = []
    seen = set()
    for collection in selected:
        tracks = get_all_mp3s(collection)
        for t in tracks:
            key = t["url"]
            if key not in seen:
                seen.add(key)
                all_tracks.append(t)

    print(f"\nTotal tracks to download: {len(all_tracks)}")
    confirm = input("Start downloading? (yes/no): ").strip().lower()
    if confirm != "yes":
        exit()

    success = 0
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(download_mp3, t): t for t in all_tracks}
        for future in as_completed(futures):
            if future.result():
                success += 1

    print(f"\nDone! Downloaded {success} tracks to {DOWNLOAD_DIR}")
