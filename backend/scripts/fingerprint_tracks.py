"""
fingerprint_tracks.py — Identify tracks within DJ sets using AcoustID + Chromaprint.

Usage:
  python fingerprint_tracks.py --manifest ./dj_sets/manifest.json
  python fingerprint_tracks.py --audio-file ./dj_sets/abc123.mp3

Requires:
  pip install requests pydub
  fpcalc binary: https://acoustid.org/chromaprint (or: brew install chromaprint)
  ACOUSTID_API_KEY env var (free at acoustid.org — just needs an app name)
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ACOUSTID_URL = "https://api.acoustid.org/v2/lookup"
CHUNK_SECONDS = 180      # fingerprint every 3 minutes
OVERLAP_SECONDS = 30     # overlap between chunks
MIN_CONFIDENCE = 0.5     # discard low-confidence matches


def check_fpcalc() -> str:
    """Find fpcalc binary or exit with instructions."""
    path = shutil.which("fpcalc")
    if path:
        return path
    log.error(
        "fpcalc not found. Install Chromaprint:\n"
        "  macOS:  brew install chromaprint\n"
        "  Ubuntu: apt-get install libchromaprint-tools\n"
        "  Or download from: https://acoustid.org/chromaprint"
    )
    sys.exit(1)


def split_audio(audio_path: str, chunk_sec: int, overlap_sec: int, tmp_dir: str) -> list[dict]:
    """Split mp3 into overlapping chunks using ffmpeg. Returns list of {path, start_sec}."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path],
            capture_output=True, text=True, check=True
        )
        duration = float(json.loads(result.stdout)["format"]["duration"])
    except Exception as e:
        log.error(f"Could not probe {audio_path}: {e}")
        return []

    chunks = []
    step = chunk_sec - overlap_sec
    start = 0

    while start < duration:
        end = min(start + chunk_sec, duration)
        chunk_path = os.path.join(tmp_dir, f"chunk_{int(start):06d}.mp3")

        ret = subprocess.run([
            "ffmpeg", "-y", "-ss", str(start), "-t", str(chunk_sec),
            "-i", audio_path, "-vn", "-ar", "44100", "-ac", "1",
            "-b:a", "128k", chunk_path
        ], capture_output=True)

        if ret.returncode == 0 and Path(chunk_path).exists():
            chunks.append({"path": chunk_path, "start_sec": start})

        start += step
        if end >= duration:
            break

    return chunks


def fingerprint_chunk(fpcalc: str, chunk_path: str) -> dict | None:
    """Run fpcalc and return {fingerprint, duration}."""
    try:
        result = subprocess.run(
            [fpcalc, "-json", chunk_path],
            capture_output=True, text=True, timeout=30
        )
        data = json.loads(result.stdout)
        return {"fingerprint": data["fingerprint"], "duration": data["duration"]}
    except Exception as e:
        log.debug(f"fpcalc error on {chunk_path}: {e}")
        return None


def lookup_acoustid(api_key: str, fingerprint: str, duration: float) -> list[dict]:
    """Query AcoustID API. Returns list of {title, artist, recording_id, score}."""
    try:
        resp = requests.post(ACOUSTID_URL, data={
            "client": api_key,
            "fingerprint": fingerprint,
            "duration": int(duration),
            "meta": "recordings",
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.debug(f"AcoustID API error: {e}")
        return []

    matches = []
    for result in data.get("results", []):
        score = result.get("score", 0)
        if score < MIN_CONFIDENCE:
            continue
        for rec in result.get("recordings", []):
            title = rec.get("title", "Unknown")
            artists = rec.get("artists", [])
            artist = artists[0]["name"] if artists else "Unknown"
            matches.append({
                "title": title,
                "artist": artist,
                "recording_id": rec.get("id", ""),
                "score": score,
            })

    # Return best match only
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[:1]


def deduplicate_tracks(raw_matches: list[dict]) -> list[dict]:
    """
    Merge consecutive chunks that matched the same track.
    raw_matches: [{title, artist, recording_id, score, start_sec}, ...]
    Returns: [{title, artist, recording_id, confidence, start_sec, end_sec}, ...]
    """
    if not raw_matches:
        return []

    merged = []
    current = dict(raw_matches[0])
    current["end_sec"] = current["start_sec"] + CHUNK_SECONDS
    current["confidence"] = current.pop("score")
    current["hit_count"] = 1

    for m in raw_matches[1:]:
        same = (
            m["title"] == current["title"] and
            m["artist"] == current["artist"]
        )
        if same:
            current["end_sec"] = m["start_sec"] + CHUNK_SECONDS
            current["confidence"] = max(current["confidence"], m["score"])
            current["hit_count"] += 1
        else:
            merged.append(current)
            current = dict(m)
            current["end_sec"] = current["start_sec"] + CHUNK_SECONDS
            current["confidence"] = current.pop("score")
            current["hit_count"] = 1

    merged.append(current)
    return merged


def fingerprint_set(audio_path: str, api_key: str, fpcalc: str, output_dir: Path) -> list[dict]:
    """Full pipeline: split → fingerprint → lookup → deduplicate → save."""
    video_id = Path(audio_path).stem
    out_file = output_dir / f"{video_id}_tracks.json"

    if out_file.exists():
        log.info(f"Already fingerprinted: {video_id}, loading cached result")
        with open(out_file) as f:
            return json.load(f)

    log.info(f"Fingerprinting: {audio_path}")
    raw_matches = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        chunks = split_audio(audio_path, CHUNK_SECONDS, OVERLAP_SECONDS, tmp_dir)
        log.info(f"  {len(chunks)} chunks to fingerprint")

        for i, chunk in enumerate(chunks):
            fp_data = fingerprint_chunk(fpcalc, chunk["path"])
            if not fp_data:
                continue

            matches = lookup_acoustid(api_key, fp_data["fingerprint"], fp_data["duration"])
            if matches:
                m = matches[0]
                m["start_sec"] = chunk["start_sec"]
                raw_matches.append(m)
                log.info(f"  [{chunk['start_sec']//60:3d}m] {m['artist']} - {m['title']} ({m['score']:.2f})")
            else:
                log.debug(f"  [{chunk['start_sec']//60:3d}m] No match")

            # Be polite to AcoustID API (free tier)
            time.sleep(0.34)  # ~3 req/sec max

    tracks = deduplicate_tracks(raw_matches)
    log.info(f"  Identified {len(tracks)} distinct tracks")

    with open(out_file, "w") as f:
        json.dump(tracks, f, indent=2)

    return tracks


def build_transitions(all_sets: list[dict]) -> list[dict]:
    """Build consecutive track pairs (A→B transitions) from all sets."""
    transitions = []
    for s in all_sets:
        tracks = s["tracks"]
        for i in range(len(tracks) - 1):
            a, b = tracks[i], tracks[i + 1]
            transitions.append({
                "dj_name": s.get("channel", "Unknown"),
                "set_title": s.get("title", "Unknown"),
                "video_id": s["video_id"],
                "track_a_title": a["title"],
                "track_a_artist": a["artist"],
                "track_a_recording_id": a.get("recording_id", ""),
                "track_a_start_sec": a["start_sec"],
                "track_b_title": b["title"],
                "track_b_artist": b["artist"],
                "track_b_recording_id": b.get("recording_id", ""),
                "track_b_start_sec": b["start_sec"],
            })
    return transitions


def main():
    parser = argparse.ArgumentParser(description="Fingerprint DJ sets to identify tracks")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--manifest", help="manifest.json from scrape_youtube_sets.py")
    group.add_argument("--audio-file", help="Single MP3 file to fingerprint")
    parser.add_argument("--output-dir", default=None, help="Where to save track JSON files (defaults to manifest dir)")
    args = parser.parse_args()

    api_key = os.getenv("ACOUSTID_API_KEY")
    if not api_key:
        log.error("Set ACOUSTID_API_KEY env var (free at acoustid.org)")
        sys.exit(1)

    fpcalc = check_fpcalc()
    log.info(f"Using fpcalc at: {fpcalc}")

    if args.audio_file:
        audio_files = [{"video_id": Path(args.audio_file).stem,
                        "local_path": args.audio_file,
                        "title": Path(args.audio_file).stem,
                        "channel": "Unknown"}]
        output_dir = Path(args.output_dir or Path(args.audio_file).parent)
    else:
        with open(args.manifest) as f:
            manifest = json.load(f)
        audio_files = [v for v in manifest if v.get("local_path")]
        output_dir = Path(args.output_dir or Path(args.manifest).parent)

    output_dir.mkdir(parents=True, exist_ok=True)
    all_sets = []

    for v in audio_files:
        if not v.get("local_path") or not Path(v["local_path"]).exists():
            log.warning(f"Audio file not found: {v.get('local_path')}")
            continue
        tracks = fingerprint_set(v["local_path"], api_key, fpcalc, output_dir)
        all_sets.append({**v, "tracks": tracks})

    transitions = build_transitions(all_sets)
    out_file = output_dir / "all_transitions.json"
    with open(out_file, "w") as f:
        json.dump(transitions, f, indent=2)

    log.info(f"\n{'='*50}")
    log.info(f"Sets processed:     {len(all_sets)}")
    log.info(f"Total transitions:  {len(transitions)}")
    log.info(f"Saved to:           {out_file}")
    log.info(f"\nNext step:\n  python build_training_pairs.py --transitions-file {out_file}")


if __name__ == "__main__":
    main()
