"""
Fast batch audio feature extractor.
- librosa for BPM (~3s/track vs 30s with Essentia multifeature)
- Essentia for key detection (more accurate than librosa) with degara beat method
- Parallel processing via ProcessPoolExecutor
- Writes directly to PostgreSQL soma.tracks
- Extracts structural features: intro/outro bars, breakdowns, drops
"""

import os
import sys
import argparse
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import psycopg2
import psycopg2.extras
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

DB_URL = "postgresql://localhost/soma"

FEATURE_EXTRACTOR_VERSION = "3.0"
ANALYSIS_VERSION = "3.0"
NORMALIZATION_VERSION = "1.0"

CAMELOT = {
    # Sharp notation
    "C major":"8B","A minor":"8A","G major":"9B","E minor":"9A",
    "D major":"10B","B minor":"10A","A major":"11B","F# minor":"11A",
    "E major":"12B","C# minor":"12A","B major":"1B","G# minor":"1A",
    "F# major":"2B","D# minor":"2A","C# major":"3B","A# minor":"3A",
    "G# major":"4B","F minor":"4A","D# major":"5B","C minor":"5A",
    "A# major":"6B","G minor":"6A","F major":"7B","D minor":"7A",
    # Flat equivalents (Essentia returns these)
    "Eb major":"5B","Eb minor":"2A",
    "Ab major":"4B","Ab minor":"1A",
    "Bb major":"6B","Bb minor":"3A",
    "Db major":"3B","Db minor":"12A",
    "Gb major":"2B","Gb minor":"11A",
    "Cb major":"1B","Cb minor":"10A",
}

def to_camelot(key, scale):
    return CAMELOT.get(f"{key} {scale}", "?")


def _detect_structural_features(y, sr, bpm, duration_full):
    """Detect phrase boundaries, clean intro/outro, breakdowns, and drops."""
    import librosa

    # Estimate bars from BPM (4 beats per bar)
    beats_per_bar = 4
    bar_duration = (60.0 / bpm) * beats_per_bar if bpm > 0 else 2.0
    total_bars = int(duration_full / bar_duration)

    # Compute RMS energy per bar
    hop_length = 512
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    frames_per_bar = max(1, int(bar_duration * sr / hop_length))
    bar_energies = []
    for i in range(0, len(rms) - frames_per_bar, frames_per_bar):
        bar_energies.append(float(np.mean(rms[i:i + frames_per_bar])))

    if not bar_energies:
        return {}

    bar_energies = np.array(bar_energies)
    median_energy = np.median(bar_energies)
    low_threshold = median_energy * 0.4

    # Spectral centroid per bar (for clean intro/outro detection)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
    bar_centroids = []
    for i in range(0, len(centroid) - frames_per_bar, frames_per_bar):
        bar_centroids.append(float(np.mean(centroid[i:i + frames_per_bar])))
    bar_centroids = np.array(bar_centroids) if bar_centroids else np.array([0])

    # Intro bars: count leading bars below low energy threshold
    intro_bars = 0
    for e in bar_energies:
        if e < low_threshold:
            intro_bars += 1
        else:
            break

    # Outro bars: count trailing bars with falling energy
    outro_bars = 0
    for e in reversed(bar_energies):
        if e < low_threshold:
            outro_bars += 1
        else:
            break

    # Clean intro: first 16 bars are drum-only (low spectral centroid)
    centroid_median = np.median(bar_centroids)
    has_clean_intro = False
    if intro_bars >= 4 and len(bar_centroids) >= 16:
        intro_centroid = np.mean(bar_centroids[:min(16, intro_bars)])
        has_clean_intro = intro_centroid < centroid_median * 0.6

    # Clean outro: last 16 bars have gradual energy reduction
    has_clean_outro = False
    if outro_bars >= 4 and len(bar_energies) >= 8:
        outro_slice = bar_energies[-min(16, outro_bars):]
        if len(outro_slice) >= 4:
            has_clean_outro = all(
                outro_slice[i] >= outro_slice[i + 1] * 0.85
                for i in range(len(outro_slice) - 1)
            ) or outro_bars >= 8

    # First breakdown: first significant energy dip after intro
    first_breakdown_bar = None
    search_start = max(intro_bars, 4)
    for i in range(search_start, len(bar_energies) - 4):
        if bar_energies[i] < median_energy * 0.5:
            first_breakdown_bar = i
            break

    # Drop bar: first major energy jump after a breakdown
    drop_bar = None
    if first_breakdown_bar is not None:
        for i in range(first_breakdown_bar, min(len(bar_energies) - 1, first_breakdown_bar + 16)):
            if bar_energies[i] > median_energy * 1.2:
                drop_bar = i
                break

    # Groove stability: how consistent is the energy across the main body
    body_start = max(intro_bars, 4)
    body_end = max(body_start + 1, len(bar_energies) - max(outro_bars, 4))
    body = bar_energies[body_start:body_end]
    groove_stability = float(1.0 - (np.std(body) / (np.mean(body) + 1e-9))) if len(body) > 1 else 0.5

    return {
        "intro_bars": intro_bars,
        "outro_bars": outro_bars,
        "has_clean_intro": has_clean_intro,
        "has_clean_outro": has_clean_outro,
        "first_breakdown_bar": first_breakdown_bar,
        "drop_bar": drop_bar,
        "groove_stability": round(max(0, min(1, groove_stability)), 4),
    }


def _extract_spectral_rhythm(y, sr):
    """Extract 8 spectral/rhythm features using librosa + Essentia."""
    import librosa

    # 1. Spectral centroid (already computed for brightness, but store raw Hz mean)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    spectral_centroid = float(np.mean(centroid))

    # 2. Spectral flux (onset strength mean — measures rate of spectral change)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    spectral_flux = float(np.mean(onset_env))

    # 3. Spectral rolloff (frequency below which 85% of energy is concentrated)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)[0]
    spectral_rolloff = float(np.mean(rolloff))

    # 4. Zero crossing rate (percussiveness indicator)
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    zero_crossing_rate = float(np.mean(zcr))

    # 5. Rhythm strength (autocorrelation peak of onset envelope)
    ac = librosa.autocorrelate(onset_env, max_size=sr // 512)
    if len(ac) > 1:
        # Normalize by first value and find peak after lag 0
        ac_norm = ac / (ac[0] + 1e-9)
        rhythm_strength = float(np.max(ac_norm[1:])) if len(ac_norm) > 1 else 0.0
    else:
        rhythm_strength = 0.0

    # 6. Onset rate (onsets per second — rhythmic density)
    onsets = librosa.onset.onset_detect(y=y, sr=sr)
    duration = len(y) / sr
    onset_rate = float(len(onsets) / duration) if duration > 0 else 0.0

    # 7. Dynamic complexity (RMS energy standard deviation — how much dynamics vary)
    rms = librosa.feature.rms(y=y)[0]
    dynamic_complexity = float(np.std(rms) / (np.mean(rms) + 1e-9))

    # 8. HPSS harmonic ratio (harmonic vs percussive energy balance)
    y_harmonic, y_percussive = librosa.effects.hpss(y)
    h_energy = float(np.mean(y_harmonic ** 2))
    p_energy = float(np.mean(y_percussive ** 2))
    hpss_harmonic_ratio = h_energy / (h_energy + p_energy + 1e-9)

    return {
        "spectral_centroid": round(spectral_centroid, 4),
        "spectral_flux": round(spectral_flux, 6),
        "spectral_rolloff": round(spectral_rolloff, 4),
        "zero_crossing_rate": round(zero_crossing_rate, 6),
        "rhythm_strength": round(rhythm_strength, 6),
        "onset_rate": round(onset_rate, 4),
        "dynamic_complexity": round(dynamic_complexity, 6),
        "hpss_harmonic_ratio": round(hpss_harmonic_ratio, 6),
    }


def _extract_mfcc(y, sr, n_mfcc=13):
    """
    Extract MFCC timbral fingerprint: 13 mean + 13 std = 26-dim vector.
    Captures tonal color, formants, texture — the 'sound' of a track.
    """
    import librosa
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
    mfcc_mean = np.mean(mfccs, axis=1).tolist()
    mfcc_std = np.std(mfccs, axis=1).tolist()
    return [round(v, 6) for v in mfcc_mean + mfcc_std]


def _extract_segment_features(y, sr, bpm, duration_full):
    """
    Phase 4: Extract features from intro, peak, and outro segments.
    Returns 3 dicts of scalar features for each segment.
    """
    import librosa

    bar_duration = (60.0 / bpm) * 4 if bpm > 0 else 2.0

    # Segment boundaries: intro = first 16 bars, outro = last 16 bars, peak = middle 50%
    intro_secs = min(16 * bar_duration, duration_full * 0.2)
    outro_secs = min(16 * bar_duration, duration_full * 0.2)

    intro_samples = int(intro_secs * sr)
    outro_samples = int(outro_secs * sr)

    y_intro = y[:intro_samples] if intro_samples < len(y) else y[:len(y) // 5]
    y_outro = y[-outro_samples:] if outro_samples < len(y) else y[-(len(y) // 5):]

    # Peak = middle 50% of the track
    mid_start = len(y) // 4
    mid_end = 3 * len(y) // 4
    y_peak = y[mid_start:mid_end]

    segments = {}
    for name, segment in [("intro", y_intro), ("peak", y_peak), ("outro", y_outro)]:
        if len(segment) < sr:  # less than 1 second, skip
            segments[name] = None
            continue

        spectral = _extract_spectral_rhythm(segment, sr)
        mfcc = _extract_mfcc(segment, sr)

        # Build 13 scalar features matching the full-track feature order
        rms = librosa.feature.rms(y=segment)[0]
        energy_val = float(np.mean(rms) * 1000)
        centroid = librosa.feature.spectral_centroid(y=segment, sr=sr)[0]
        brightness_val = float(np.mean(centroid) / sr)
        loudness_val = float(librosa.amplitude_to_db(rms).mean())
        onset_env_seg = librosa.onset.onset_strength(y=segment, sr=sr)
        danceability_val = float(np.std(onset_env_seg) / (np.mean(onset_env_seg) + 1e-6))

        # 13 scalars: bpm, energy, danceability, brightness, loudness,
        #             spectral_centroid, spectral_flux, spectral_rolloff,
        #             zero_crossing_rate, rhythm_strength, onset_rate,
        #             dynamic_complexity, hpss_harmonic_ratio
        scalar_13 = [
            bpm,  # same BPM for all segments
            energy_val, danceability_val, brightness_val, abs(loudness_val),
            spectral["spectral_centroid"], spectral["spectral_flux"],
            spectral["spectral_rolloff"], spectral["zero_crossing_rate"],
            spectral["rhythm_strength"], spectral["onset_rate"],
            spectral["dynamic_complexity"], spectral["hpss_harmonic_ratio"],
        ]
        # 26 MFCC values
        segment_vector = [round(v, 6) for v in scalar_13] + mfcc
        segments[name] = segment_vector

    return segments


def extract_features(file_path: str) -> dict:
    import librosa
    import essentia.standard as es

    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > 100:
        raise ValueError(f"Too large ({size_mb:.0f}MB) — skipping")

    y, sr = librosa.load(file_path, sr=22050, mono=True, duration=120)
    duration_full = librosa.get_duration(path=file_path)

    if duration_full > 900:
        raise ValueError(f"Too long ({duration_full/60:.0f}min) — skipping")

    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(tempo) if np.isscalar(tempo) else float(tempo[0])

    rms = librosa.feature.rms(y=y)[0]
    energy = float(np.mean(rms) * 1000)

    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    brightness = float(np.mean(centroid) / sr)

    loudness = float(librosa.amplitude_to_db(rms).mean())

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    danceability = float(np.std(onset_env) / (np.mean(onset_env) + 1e-6))

    # Key detection with Essentia (degara beat tracking for accuracy)
    audio_es = es.MonoLoader(filename=file_path, sampleRate=44100)()
    key, scale, _ = es.KeyExtractor()(audio_es)

    # Phase 1 (Embedding): 8 spectral/rhythm features
    spectral_rhythm = _extract_spectral_rhythm(y, sr)

    # Phase 2 (Embedding): MFCC timbral fingerprint (26-dim)
    mfcc_vector = _extract_mfcc(y, sr)

    # Structural features (Phase 3.1-3.3)
    y_full, sr_full = librosa.load(file_path, sr=22050, mono=True)
    structural = _detect_structural_features(y_full, sr_full, bpm, duration_full)

    # Phase 4 (Embedding): Segment-level vectors
    segments = _extract_segment_features(y_full, sr_full, bpm, duration_full)

    stem = Path(file_path).stem
    if " - " in stem:
        parts = stem.split(" - ", 1)
        artist, title = parts[0].strip(), parts[1].strip()
    else:
        artist, title = "Unknown", stem

    # Build 39-dim embedding: 13 scalar features + 26 MFCC
    scalar_13 = [
        round(bpm, 2), round(energy, 4), round(danceability, 4),
        round(brightness, 6), round(abs(loudness), 4),
        spectral_rhythm["spectral_centroid"], spectral_rhythm["spectral_flux"],
        spectral_rhythm["spectral_rolloff"], spectral_rhythm["zero_crossing_rate"],
        spectral_rhythm["rhythm_strength"], spectral_rhythm["onset_rate"],
        spectral_rhythm["dynamic_complexity"], spectral_rhythm["hpss_harmonic_ratio"],
    ]
    embedding = [round(v, 6) for v in scalar_13] + mfcc_vector

    result = {
        "file_path": file_path, "title": title, "artist": artist,
        "bpm": round(bpm, 2), "key": f"{key} {scale}",
        "camelot_code": to_camelot(key, scale),
        "energy": round(energy, 4), "loudness": round(loudness, 4),
        "danceability": round(danceability, 4),
        "brightness": round(brightness, 6),
        "duration": round(duration_full, 2),
        # Version tracking (Phase 0.1)
        "analysis_version": ANALYSIS_VERSION,
        "feature_extractor_version": FEATURE_EXTRACTOR_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        # Phase 1 (Embedding): 8 spectral/rhythm features
        **spectral_rhythm,
        # Phase 2 (Embedding): MFCC vector
        "mfcc_vector": mfcc_vector,
        # Phase 3 (Embedding): Combined 39-dim embedding
        "embedding": embedding,
        # Phase 4 (Embedding): Segment vectors
        "intro_vector": segments.get("intro"),
        "peak_vector": segments.get("peak"),
        "outro_vector": segments.get("outro"),
    }
    result.update(structural)
    return result

def process_one(file_path: str):
    try:
        return ("ok", file_path, extract_features(file_path))
    except ValueError as e:
        return ("skip", file_path, str(e))
    except Exception as e:
        return ("error", file_path, str(e))

def insert_batch(conn, batch: list):
    cols = ["file_path","title","artist","bpm","key","camelot_code",
            "energy","loudness","danceability","brightness","duration",
            "analysis_version","feature_extractor_version","normalization_version",
            "intro_bars","outro_bars","has_clean_intro","has_clean_outro",
            "first_breakdown_bar","drop_bar","groove_stability",
            # Phase 1 (Embedding): 8 spectral/rhythm features
            "spectral_centroid","spectral_flux","spectral_rolloff",
            "zero_crossing_rate","rhythm_strength","onset_rate",
            "dynamic_complexity","hpss_harmonic_ratio",
            # Phase 2 (Embedding): MFCC vector
            "mfcc_vector",
            # Phase 3 (Embedding): Combined embedding
            "embedding",
            # Phase 4 (Embedding): Segment vectors
            "intro_vector","peak_vector","outro_vector"]
    rows = [tuple(f.get(c) for c in cols) for f in batch]
    update_cols = [c for c in cols if c != "file_path"]
    update_clause = ", ".join(f"{c}=EXCLUDED.{c}" for c in update_cols)
    sql = f"""
        INSERT INTO tracks ({', '.join(cols)}) VALUES %s
        ON CONFLICT (file_path) DO UPDATE SET {update_clause}
    """
    psycopg2.extras.execute_values(conn.cursor(), sql, rows)
    conn.commit()

def ensure_schema(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id SERIAL PRIMARY KEY, file_path TEXT UNIQUE, title TEXT, artist TEXT,
            bpm FLOAT, key TEXT, camelot_code TEXT, energy FLOAT, loudness FLOAT,
            danceability FLOAT, brightness FLOAT, duration FLOAT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_tracks_bpm ON tracks(bpm);
        CREATE INDEX IF NOT EXISTS idx_tracks_camelot ON tracks(camelot_code);
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS camelot_code TEXT;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS duration FLOAT;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS brightness FLOAT;
        -- Phase 0: Version columns
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS analysis_version TEXT;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS feature_extractor_version TEXT;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS normalization_version TEXT;
        -- Phase 1.1: Raw metadata
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS label TEXT;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS release_year INTEGER;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS era TEXT;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS source_platform TEXT;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS source_url TEXT;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS license_type TEXT;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS commercial_use_allowed BOOLEAN;
        -- Phase 1.2: Structural features
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS intro_bars INTEGER;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS outro_bars INTEGER;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS has_clean_intro BOOLEAN;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS has_clean_outro BOOLEAN;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS first_breakdown_bar INTEGER;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS drop_bar INTEGER;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS groove_stability FLOAT;
        -- Phase 1.3: Energy classification
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS energy_tag TEXT;
        -- Embedding Plan Phase 1: 8 spectral/rhythm features
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS spectral_centroid FLOAT;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS spectral_flux FLOAT;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS spectral_rolloff FLOAT;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS zero_crossing_rate FLOAT;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS rhythm_strength FLOAT;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS onset_rate FLOAT;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS dynamic_complexity FLOAT;
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS hpss_harmonic_ratio FLOAT;
        -- Embedding Plan Phase 2: MFCC timbral fingerprint
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS mfcc_vector FLOAT[];
        -- Embedding Plan Phase 3: Combined 39-dim embedding
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS embedding FLOAT[];
        -- Embedding Plan Phase 4: Segment vectors (39-dim each)
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS intro_vector FLOAT[];
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS peak_vector FLOAT[];
        ALTER TABLE tracks ADD COLUMN IF NOT EXISTS outro_vector FLOAT[];
    """)

    # Embedding Plan Phase 5: DJ sequence learning tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dj_transitions (
            id SERIAL PRIMARY KEY,
            tracklist_id TEXT NOT NULL,
            dj_name TEXT,
            event_name TEXT,
            event_date TIMESTAMPTZ,
            position_in_set INTEGER,
            track_a_title TEXT,
            track_a_artist TEXT,
            track_b_title TEXT,
            track_b_artist TEXT,
            track_a_id INTEGER REFERENCES tracks(id),
            track_b_id INTEGER REFERENCES tracks(id),
            resolved BOOLEAN DEFAULT FALSE
        );
        CREATE INDEX IF NOT EXISTS idx_dj_trans_tracklist ON dj_transitions(tracklist_id);
        CREATE INDEX IF NOT EXISTS idx_dj_trans_tracks ON dj_transitions(track_a_id, track_b_id);

        CREATE TABLE IF NOT EXISTS transition_scores (
            id SERIAL PRIMARY KEY,
            track_a_id INTEGER NOT NULL REFERENCES tracks(id),
            track_b_id INTEGER NOT NULL REFERENCES tracks(id),
            times_played INTEGER DEFAULT 1,
            avg_position_pct FLOAT,
            confidence FLOAT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_trans_score_pair
            ON transition_scores(track_a_id, track_b_id);
    """)
    conn.commit()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    folder = Path(args.directory)
    mp3s = sorted(folder.rglob("*.mp3"))
    if args.limit:
        mp3s = mp3s[:args.limit]
    total = len(mp3s)
    print(f"Found {total} MP3s | Workers: {args.workers}\n")

    conn = None
    if not args.dry_run:
        conn = psycopg2.connect(DB_URL)
        ensure_schema(conn)
        print("✓ DB connected\n")

    success, failed, skipped, completed = 0, 0, 0, 0
    batch = []

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_one, str(mp3)): mp3 for mp3 in mp3s}
        for future in as_completed(futures):
            completed += 1
            status, path, result = future.result()
            name = Path(path).name
            if status == "ok":
                print(f"[{completed}/{total}] ✓ {name[:50]} BPM={result['bpm']} {result['camelot_code']}")
                success += 1
                if not args.dry_run:
                    batch.append(result)
                    if len(batch) >= 10:
                        insert_batch(conn, batch)
                        batch.clear()
            elif status == "skip":
                print(f"[{completed}/{total}] ⏭  {name[:50]} — {result}")
                skipped += 1
            else:
                print(f"[{completed}/{total}] ✗  {name[:50]} — {result[:80]}")
                failed += 1

    if not args.dry_run and batch:
        insert_batch(conn, batch)
    if conn:
        conn.close()

    print(f"\n{'='*60}")
    print(f"✅ Success: {success} | Skipped: {skipped} | Failed: {failed} | Total: {total}")

if __name__ == "__main__":
    main()