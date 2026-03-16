from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/soma")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    file_path = Column(String, unique=True)
    bpm = Column(Float)
    key = Column(String)
    camelot_code = Column(String)
    energy = Column(Float)
    danceability = Column(Float)
    loudness = Column(Float)
    brightness = Column(Float)
    duration = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Phase 0: Version tracking
    analysis_version = Column(Text)
    feature_extractor_version = Column(Text)
    normalization_version = Column(Text)

    # Phase 1.1: Raw metadata
    label = Column(String)
    release_year = Column(Integer)
    era = Column(String)
    source_platform = Column(String)
    source_url = Column(String)
    license_type = Column(String)
    commercial_use_allowed = Column(Boolean)

    # Phase 1.2: Structural features
    intro_bars = Column(Integer)
    outro_bars = Column(Integer)
    has_clean_intro = Column(Boolean)
    has_clean_outro = Column(Boolean)
    first_breakdown_bar = Column(Integer)
    drop_bar = Column(Integer)
    groove_stability = Column(Float)

    # Phase 1.3: Energy classification
    energy_tag = Column(String)  # warmup/groove/peak/closer

    # Embedding Accuracy Plan — Phase 1: 8 spectral/rhythm features
    spectral_centroid = Column(Float)
    spectral_flux = Column(Float)
    spectral_rolloff = Column(Float)
    zero_crossing_rate = Column(Float)
    rhythm_strength = Column(Float)
    onset_rate = Column(Float)
    dynamic_complexity = Column(Float)
    hpss_harmonic_ratio = Column(Float)

    # Embedding Accuracy Plan — Phase 2: MFCC timbral fingerprint (26-dim)
    mfcc_vector = Column(ARRAY(Float))  # 13 mean + 13 std = 26 values

    # Embedding Accuracy Plan — Phase 3: Combined embedding (39-dim)
    # 13 scalar features + 26 MFCC values
    # Using pgvector via raw SQL; stored as FLOAT[] for ORM compatibility
    embedding = Column(ARRAY(Float))  # 39-dim combined vector

    # Embedding Accuracy Plan — Phase 4: Segment-level vectors (39-dim each)
    intro_vector = Column(ARRAY(Float))   # 39-dim intro embedding
    peak_vector = Column(ARRAY(Float))    # 39-dim peak/body embedding
    outro_vector = Column(ARRAY(Float))   # 39-dim outro embedding

    __table_args__ = (
        Index("idx_tracks_bpm", "bpm"),
        Index("idx_tracks_camelot", "camelot_code"),
        Index("idx_tracks_energy_tag", "energy_tag"),
        Index("idx_tracks_bpm_energy", "bpm", "energy"),
    )


class LabelRelationship(Base):
    """Phase 1.4: Label compatibility scores."""
    __tablename__ = "label_relationships"

    id = Column(Integer, primary_key=True, index=True)
    label_a = Column(String, nullable=False)
    label_b = Column(String, nullable=False)
    compatibility_score = Column(Float, nullable=False)

    __table_args__ = (
        Index("idx_label_rel_pair", "label_a", "label_b", unique=True),
    )


class EvaluationPair(Base):
    """Phase 1.5: Human-judged track pairs for evaluation."""
    __tablename__ = "evaluation_pairs"

    id = Column(Integer, primary_key=True, index=True)
    track_a_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    track_b_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    human_score = Column(String, nullable=False)  # bad/usable/strong/excellent
    transition_type = Column(Text)
    notes = Column(Text)

    __table_args__ = (
        Index("idx_eval_pair_tracks", "track_a_id", "track_b_id"),
    )


class DJTransition(Base):
    """Phase 5: DJ transitions scraped from 1001Tracklists."""
    __tablename__ = "dj_transitions"

    id = Column(Integer, primary_key=True, index=True)
    tracklist_id = Column(String, nullable=False)  # 1001tracklists ID
    dj_name = Column(String)
    event_name = Column(String)
    event_date = Column(DateTime)
    position_in_set = Column(Integer)  # ordering within the set
    track_a_title = Column(String)
    track_a_artist = Column(String)
    track_b_title = Column(String)
    track_b_artist = Column(String)
    track_a_id = Column(Integer, ForeignKey("tracks.id"), nullable=True)
    track_b_id = Column(Integer, ForeignKey("tracks.id"), nullable=True)
    resolved = Column(Boolean, default=False)  # matched to local tracks?

    __table_args__ = (
        Index("idx_dj_trans_tracklist", "tracklist_id"),
        Index("idx_dj_trans_tracks", "track_a_id", "track_b_id"),
    )


class TransitionScore(Base):
    """Phase 5: Aggregated learned transition scores."""
    __tablename__ = "transition_scores"

    id = Column(Integer, primary_key=True, index=True)
    track_a_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    track_b_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    times_played = Column(Integer, default=1)  # how many DJs played this pair
    avg_position_pct = Column(Float)  # average set position (0=opener, 1=closer)
    confidence = Column(Float)  # higher = more data points

    __table_args__ = (
        Index("idx_trans_score_pair", "track_a_id", "track_b_id", unique=True),
    )


class SomaSession(Base):
    """M2: A planned listening session with a full pre-generated track arc."""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    arc_type = Column(String, nullable=False)   # e.g. "peak_hour", "deep_focus"
    duration_min = Column(Integer, nullable=False)
    bpm_start = Column(Float)
    bpm_peak = Column(Float)
    bpm_end = Column(Float)
    total_tracks = Column(Integer)
    status = Column(String, default="active")   # active / completed / abandoned
    created_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)


class SessionTrack(Base):
    """M2: One track slot in a planned session arc."""
    __tablename__ = "session_tracks"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    position = Column(Integer, nullable=False)      # 1-based slot in the arc
    target_bpm = Column(Float)
    status = Column(String, default="pending")      # pending / playing / completed / skipped
    resonance_rating = Column(Integer, nullable=True)  # 1–5, user rating
    played_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_session_tracks_session", "session_id", "position"),
    )


# Seed data for label relationships
LABEL_RELATIONSHIP_SEEDS = [
    ("Tresor", "Hardwax", 0.95),
    ("Drumcode", "Rekids", 0.85),
    ("Ostgut Ton", "Tresor", 0.90),
    ("Kompakt", "Perlon", 0.92),
    ("Mute", "Tresor", 0.80),
    ("R&S Records", "Kompakt", 0.85),
    ("Planet E", "Transmat", 0.95),
    ("Soma", "Slam", 0.90),
    ("CLR", "Drumcode", 0.88),
    ("Minus", "Perlon", 0.90),
    ("Cocoon", "Kompakt", 0.88),
    ("Bpitch Control", "Ostgut Ton", 0.85),
    ("M-Plant", "Planet E", 0.92),
    ("Prologue", "Minus", 0.85),
    ("Token", "CLR", 0.88),
    ("Stroboscopic Artefacts", "Ostgut Ton", 0.82),
    ("Delsin", "Clone", 0.90),
    ("Clone", "Tresor", 0.85),
    ("Mord", "Perc Trax", 0.92),
    ("Perc Trax", "Token", 0.88),
]


def create_tables():
    Base.metadata.create_all(bind=engine)


def seed_label_relationships():
    """Seed label_relationships table with initial data."""
    db = SessionLocal()
    try:
        existing = db.query(LabelRelationship).count()
        if existing == 0:
            for label_a, label_b, score in LABEL_RELATIONSHIP_SEEDS:
                db.add(LabelRelationship(
                    label_a=label_a, label_b=label_b, compatibility_score=score
                ))
            db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()