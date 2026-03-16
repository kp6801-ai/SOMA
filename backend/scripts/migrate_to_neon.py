#!/usr/bin/env python3
"""
Migrate SOMA database from Render Postgres to Neon (or any other Postgres URL).

Usage:
    python scripts/migrate_to_neon.py \
        --source "postgresql://..." \
        --target "postgresql://..."

What it does:
1. Reads all tracks from the source DB
2. Creates all tables in the target DB
3. Inserts all tracks in batches of 50
4. Migrates sessions and session_tracks if any exist
5. Prints a summary
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def migrate(source_url: str, target_url: str):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from database import Base, Track, SomaSession, SessionTrack, LabelRelationship

    print(f"Connecting to source DB...")
    src_engine = create_engine(source_url)
    SrcSession = sessionmaker(bind=src_engine)
    src_db = SrcSession()

    print(f"Connecting to target DB (Neon)...")
    dst_engine = create_engine(target_url)
    DstSession = sessionmaker(bind=dst_engine)
    dst_db = DstSession()

    print("Creating tables on target...")
    Base.metadata.create_all(bind=dst_engine)

    # ── Tracks ──────────────────────────────────────────────────
    tracks = src_db.query(Track).all()
    print(f"Found {len(tracks)} tracks to migrate...")

    BATCH = 50
    migrated = 0
    for i in range(0, len(tracks), BATCH):
        batch = tracks[i:i + BATCH]
        for t in batch:
            exists = dst_db.query(Track).filter(Track.file_path == t.file_path).first()
            if exists:
                continue
            dst_db.add(Track(
                title=t.title, artist=t.artist, file_path=t.file_path,
                bpm=t.bpm, key=t.key, camelot_code=t.camelot_code,
                energy=t.energy, danceability=t.danceability, loudness=t.loudness,
                brightness=t.brightness, duration=t.duration,
                label=t.label, release_year=t.release_year, era=t.era,
                source_platform=t.source_platform, source_url=t.source_url,
                license_type=t.license_type, commercial_use_allowed=t.commercial_use_allowed,
                intro_bars=t.intro_bars, outro_bars=t.outro_bars,
                has_clean_intro=t.has_clean_intro, has_clean_outro=t.has_clean_outro,
                first_breakdown_bar=t.first_breakdown_bar, drop_bar=t.drop_bar,
                groove_stability=t.groove_stability, energy_tag=t.energy_tag,
                spectral_centroid=t.spectral_centroid, spectral_flux=t.spectral_flux,
                spectral_rolloff=t.spectral_rolloff, zero_crossing_rate=t.zero_crossing_rate,
                rhythm_strength=t.rhythm_strength, onset_rate=t.onset_rate,
                dynamic_complexity=t.dynamic_complexity, hpss_harmonic_ratio=t.hpss_harmonic_ratio,
                mfcc_vector=t.mfcc_vector, embedding=t.embedding,
                intro_vector=t.intro_vector, peak_vector=t.peak_vector, outro_vector=t.outro_vector,
                analysis_version=t.analysis_version,
                feature_extractor_version=t.feature_extractor_version,
                normalization_version=t.normalization_version,
            ))
            migrated += 1
        dst_db.commit()
        print(f"  Tracks: {min(i + BATCH, len(tracks))}/{len(tracks)}")

    # ── Label relationships ──────────────────────────────────────
    lr_count = src_db.query(LabelRelationship).count()
    if lr_count:
        for lr in src_db.query(LabelRelationship).all():
            exists = dst_db.query(LabelRelationship).filter_by(
                label_a=lr.label_a, label_b=lr.label_b
            ).first()
            if not exists:
                dst_db.add(LabelRelationship(
                    label_a=lr.label_a, label_b=lr.label_b,
                    compatibility_score=lr.compatibility_score
                ))
        dst_db.commit()
        print(f"Migrated {lr_count} label relationships.")

    # ── Sessions ────────────────────────────────────────────────
    sessions = src_db.query(SomaSession).all()
    if sessions:
        print(f"Migrating {len(sessions)} sessions...")
        for s in sessions:
            dst_db.add(SomaSession(
                arc_type=s.arc_type, duration_min=s.duration_min,
                bpm_start=s.bpm_start, bpm_peak=s.bpm_peak, bpm_end=s.bpm_end,
                total_tracks=s.total_tracks, status=s.status,
                created_at=s.created_at, ended_at=s.ended_at,
            ))
        dst_db.commit()

    print(f"\n✓ Migration complete — {migrated} tracks, {len(sessions)} sessions moved to Neon.")

    src_db.close()
    dst_db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate SOMA DB to Neon")
    parser.add_argument("--source", required=True, help="Source DATABASE_URL (Render)")
    parser.add_argument("--target", required=True, help="Target DATABASE_URL (Neon)")
    args = parser.parse_args()
    migrate(args.source, args.target)
