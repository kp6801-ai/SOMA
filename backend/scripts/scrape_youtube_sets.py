"""
scrape_youtube_sets.py — Find and download DJ sets from YouTube.

Usage:
  python scrape_youtube_sets.py --query "techno DJ mix 2023" --max-results 50
  python scrape_youtube_sets.py --query "techno set berghain" --dry-run

Requires:
  pip install google-api-python-client yt-dlp
  YOUTUBE_API_KEY env var (free at console.cloud.google.com)
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def search_youtube(api_key: str, query: str, max_results: int) -> list[dict]:
    """Search YouTube for long DJ sets matching query."""
    try:
        from googleapiclient.discovery import build
    except ImportError:
        log.error("Install google-api-python-client: pip install google-api-python-client")
        sys.exit(1)

    youtube = build("youtube", "v3", developerKey=api_key)
    results = []
    page_token = None

    while len(results) < max_results:
        batch = min(50, max_results - len(results))
        resp = youtube.search().list(
            q=query,
            part="snippet",
            type="video",
            videoDuration="long",   # > 20 min
            maxResults=batch,
            pageToken=page_token,
        ).execute()

        video_ids = [item["id"]["videoId"] for item in resp.get("items", [])]

        # Fetch video details for duration + view count
        details = youtube.videos().list(
            id=",".join(video_ids),
            part="contentDetails,statistics,snippet",
        ).execute()

        for item in details.get("items", []):
            vid_id = item["id"]
            snippet = item["snippet"]
            duration_iso = item["contentDetails"]["duration"]  # e.g. PT1H32M10S
            duration_sec = _parse_duration(duration_iso)

            # Only keep sets longer than 30 minutes
            if duration_sec < 1800:
                continue

            results.append({
                "video_id": vid_id,
                "title": snippet["title"],
                "channel": snippet["channelTitle"],
                "url": f"https://www.youtube.com/watch?v={vid_id}",
                "duration_sec": duration_sec,
                "published_at": snippet["publishedAt"],
                "view_count": int(item["statistics"].get("viewCount", 0)),
            })

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return results[:max_results]


def _parse_duration(iso: str) -> int:
    """Parse ISO 8601 duration PT1H32M10S → seconds."""
    import re
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return 0
    h, mn, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mn * 60 + s


def load_manifest(manifest_path: Path) -> dict:
    if manifest_path.exists():
        with open(manifest_path) as f:
            data = json.load(f)
        return {item["video_id"]: item for item in data}
    return {}


def save_manifest(manifest_path: Path, manifest: dict):
    with open(manifest_path, "w") as f:
        json.dump(list(manifest.values()), f, indent=2)


def download_set(video: dict, output_dir: Path) -> str | None:
    """Download audio using yt-dlp. Returns local file path or None on failure."""
    try:
        import yt_dlp
    except ImportError:
        log.error("Install yt-dlp: pip install yt-dlp")
        sys.exit(1)

    out_template = str(output_dir / f"{video['video_id']}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video["url"]])
        local_path = str(output_dir / f"{video['video_id']}.mp3")
        return local_path if Path(local_path).exists() else None
    except Exception as e:
        log.warning(f"Download failed for {video['video_id']}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Download DJ sets from YouTube for SOMA training")
    parser.add_argument("--query", required=True, help='e.g. "techno DJ mix 2023"')
    parser.add_argument("--max-results", type=int, default=50)
    parser.add_argument("--output-dir", default="./dj_sets", help="Directory to save audio files")
    parser.add_argument("--dry-run", action="store_true", help="Print results without downloading")
    args = parser.parse_args()

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        log.error("Set YOUTUBE_API_KEY environment variable")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    manifest = load_manifest(manifest_path)

    log.info(f"Searching YouTube: '{args.query}' (max {args.max_results})")
    videos = search_youtube(api_key, args.query, args.max_results)
    log.info(f"Found {len(videos)} sets longer than 30 minutes")

    for v in videos:
        h = v["duration_sec"] // 3600
        m = (v["duration_sec"] % 3600) // 60
        log.info(f"  [{v['video_id']}] {v['title'][:60]} | {h}h{m:02d}m | {v['view_count']:,} views")

    if args.dry_run:
        log.info("Dry run — no downloads.")
        return

    downloaded = 0
    skipped = 0
    failed = 0

    for v in videos:
        if v["video_id"] in manifest:
            log.info(f"Skip (already downloaded): {v['video_id']}")
            skipped += 1
            continue

        log.info(f"Downloading: {v['title'][:60]}")
        local_path = download_set(v, output_dir)

        if local_path:
            v["local_path"] = local_path
            v["downloaded_at"] = datetime.now(timezone.utc).isoformat()
            manifest[v["video_id"]] = v
            save_manifest(manifest_path, manifest)
            downloaded += 1
            log.info(f"  Saved to {local_path}")
        else:
            failed += 1

    log.info(f"\nDone. Downloaded: {downloaded} | Skipped: {skipped} | Failed: {failed}")
    log.info(f"Manifest: {manifest_path}")
    log.info(f"\nNext step:\n  python fingerprint_tracks.py --manifest {manifest_path}")


if __name__ == "__main__":
    main()
