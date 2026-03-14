import os
import json
import sys
sys.path.append(os.path.expanduser("~/Desktop/soma/backend"))

from database import SessionLocal, Track, create_tables
from camelot import get_camelot
from scripts.extract_features import extract_features

FMA_PATH = os.path.expanduser("~/Desktop/fma_small")
TECHNO_JSON = os.path.expanduser("~/Desktop/techno_tracks.json")

def get_audio_path(track_id: str) -> str:
    padded = track_id.zfill(6)
    folder = padded[:3]
    return os.path.join(FMA_PATH, folder, f"{padded}.mp3")

def batch_ingest():
    create_tables()
    db = SessionLocal()
    
    with open(TECHNO_JSON) as f:
        tracks = json.load(f)
    
    print(f"Processing {len(tracks)} techno tracks...")
    
    success = 0
    failed = 0
    
    for i, track in enumerate(tracks):
        audio_path = get_audio_path(track["id"])
        
        if not os.path.exists(audio_path):
            failed += 1
            continue
        
        try:
            features = extract_features(audio_path)
            camelot = get_camelot(features["key"])
            
            db_track = Track(
                title=track["title"],
                artist=track["artist"],
                file_path=audio_path,
                bpm=features["bpm"],
                key=features["key"],
                camelot=camelot,
                energy=features["energy"],
                danceability=features["danceability"],
                loudness=features["loudness"],
                brightness=features["brightness"]
            )
            
            db.add(db_track)
            db.commit()
            success += 1
            
            if i % 50 == 0:
                print(f"Progress: {i}/{len(tracks)} | Success: {success} | Failed: {failed}")
        
        except Exception as e:
            failed += 1
            db.rollback()
            continue
    
    db.close()
    print(f"\nDone! Success: {success} | Failed: {failed}")

if __name__ == "__main__":
    batch_ingest()