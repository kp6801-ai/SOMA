"""
fingerprint_tracks.py — Identify tracks within DJ sets using Shazam.

Uses shazamio (unofficial Shazam API) — free, no key needed, recognizes remixes.

Usage:
  python3 fingerprint_tracks.py --manifest ./dj_sets/manifest.json
  python3 fingerprint_tracks.py --audio-file ./dj_sets/abc123.mp3

Requires:
  pip install shazamio pydub
  ffmpeg (brew install ffmpeg)
"""

import argparse
import asyncio
import json
import logging
import subprocess
import sys
import tempfile
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

CHUNK_SECONDS = 60       # sample 60s per chunk (Shazam works well with 1 min)
STEP_SECONDS = 180       # sample every 3 minutes through the set
MIN_CONFIDENCE = 0.4


def check_deps():
    try:
        import shazamio  # noqa
    except ImportError:
        log.error("Install shazamio: pip3 install shazamio")
        sys.exit(1)
    result = subprocess.run(["which", "ffmpeg"], capture_output=True)
    if result.returncode != 0:
        log.error("ffmpeg not found: brew install ffmpeg")
        sys.exit(1)


def get_duration(audio_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path],
        capture_output=True, text=True
    )
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except Exception:
        return 0.0


def extract_chunk(audio_path: str, start_sec: float, duration: float, out_path: str) -> bool:
    ret = subprocess.run([
        "ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration),
        "-i", audio_path, "-vn", "-ar", "44100", "-ac", "1",
        "-b:a", "128k", out_path
    ], capture_output=True)
    return ret.returncode == 0 and Path(out_path).exists()


async def shazam_chunk(chunk_path: str) -> dict | None:
    from shazamio import Shazam
    shazam = Shazam()
    try:
        result = await shazam.recognize(chunk_path)
        track = result.get("track")
        if not track:
            return None
        return {
            "title": track.get("title", "Unknown"),
            "artist": track.get("subtitle", "Unknown"),
            "shazam_id": track.get("key", ""),
            "confidence": 0.9,  # Shazam doesn't return confidence scores; assume high
        }
    except Exception as e:
        log.debug(f"Shazam error: {e}")
        return None


async def fingerprint_set_async(audio_path: str, output_dir: Path) -> list[dict]:
    video_id = Path(audio_path).stem
    out_file = output_dir / f"{video_id}_tracks.json"

    if out_file.exists():
        log.info(f"Already fingerprinted: {video_id}")
        with open(out_file) as f:
            return json.load(f)

    duration = get_duration(audio_path)
    if duration == 0:
        log.warning(f"Could not read duration: {audio_path}")
        return []

    log.info(f"Fingerprinting: {Path(audio_path).name} ({duration/3600:.1f}h)")

    raw_matches = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        start = 0.0
        while start < duration:
            chunk_path = f"{tmp_dir}/chunk_{int(start):06d}.mp3"
            if extract_chunk(audio_path, start, CHUNK_SECONDS, chunk_path):
                match = await shazam_chunk(chunk_path)
                if match:
                    match["start_sec"] = start
                    raw_matches.append(match)
                    log.info(f"  [{int(start)//60:3d}m] {match['artist']} - {match['title']}")
                else:
                    log.debug(f"  [{int(start)//60:3d}m] No match")

            start += STEP_SECONDS
            await asyncio.sleep(0.5)  # be polite

    tracks = deduplicate_tracks(raw_matches)
    log.info(f"  → {len(tracks)} distinct tracks identified")

    with open(out_file, "w") as f:
        json.dump(tracks, f, indent=2)

    return tracks


def deduplicate_tracks(raw: list[dict]) -> list[dict]:
    if not raw:
        return []
    merged = []
    cur = {**raw[0], "end_sec": raw[0]["start_sec"] + CHUNK_SECONDS, "hit_count": 1}

    for m in raw[1:]:
        same = (m["title"] == cur["title"] and m["artist"] == cur["artist"])
        if same:
            cur["end_sec"] = m["start_sec"] + CHUNK_SECONDS
            cur["hit_count"] += 1
        else:
            merged.append(cur)
            cur = {**m, "end_sec": m["start_sec"] + CHUNK_SECONDS, "hit_count": 1}
    merged.append(cur)
    return merged


def build_transitions(all_sets: list[dict]) -> list[dict]:
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
                "track_a_start_sec": a["start_sec"],
                "track_b_title": b["title"],
                "track_b_artist": b["artist"],
                "track_b_start_sec": b["start_sec"],
            })
    return transitions


async def main_async(args):
    check_deps()

    if args.audio_file:
        audio_files = [{
            "video_id": Path(args.audio_file).stem,
            "local_path": args.audio_file,
            "title": Path(args.audio_file).stem,
            "channel": "Unknown",
        }]
        output_dir = Path(args.output_dir or Path(args.audio_file).parent)
    else:
        with open(args.manifest) as f:
            manifest = json.load(f)
        audio_files = [v for v in manifest if v.get("local_path")]
        output_dir = Path(args.output_dir or Path(args.manifest).parent)

    output_dir.mkdir(parents=True, exist_ok=True)
    all_sets = []

    for i, v in enumerate(audio_files):
        path = v.get("local_path", "")
        if not Path(path).exists():
            log.warning(f"File not found: {path}")
            continue
        log.info(f"\n[{i+1}/{len(audio_files)}] {v.get('title','')[:60]}")
        tracks = await fingerprint_set_async(path, output_dir)
        all_sets.append({**v, "tracks": tracks})

    transitions = build_transitions(all_sets)
    out_file = output_dir / "all_transitions.json"
    with open(out_file, "w") as f:
        json.dump(transitions, f, indent=2)

    total_tracks = sum(len(s["tracks"]) for s in all_sets)
    log.info(f"\n{'='*50}")
    log.info(f"Sets processed:      {len(all_sets)}")
    log.info(f"Tracks identified:   {total_tracks}")
    log.info(f"Transitions found:   {len(transitions)}")
    log.info(f"Saved to:            {out_file}")
    if len(transitions) > 0:
        log.info(f"\nNext step:\n  python3 scripts/build_training_pairs.py --transitions-file {out_file}")
    else:
        log.warning("No transitions found — check that ffmpeg is working and sets are > 30 min")


def main():
    parser = argparse.ArgumentParser(description="Fingerprint DJ sets via Shazam")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--manifest", help="manifest.json from scrape_youtube_sets.py")
    group.add_argument("--audio-file", help="Single MP3 to fingerprint")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
