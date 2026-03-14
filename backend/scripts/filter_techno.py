import csv
import json
import os

tracks_path = os.path.expanduser("~/Desktop/fma_metadata/tracks.csv")

def filter_techno_tracks():
    techno_tracks = []
    
    with open(tracks_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        next(reader)
        next(reader)
        
        for row in reader:
            try:
                genre = row[40].lower()
                title = row[52]
                artist = row[11]
                track_id = row[0]
                
                if any(word in genre for word in ["techno", "electronic", "house", "dance"]):
                    techno_tracks.append({
                        "id": track_id,
                        "title": title,
                        "artist": artist,
                        "genre": genre
                    })
            except IndexError:
                continue
    
    print(f"Found {len(techno_tracks)} techno/electronic tracks")
    
    with open(os.path.expanduser("~/Desktop/techno_tracks.json"), "w") as f:
        json.dump(techno_tracks, f, indent=2)
    
    print("Saved to ~/Desktop/techno_tracks.json")

if __name__ == "__main__":
    filter_techno_tracks()