"""
SOMA Engine Integration Tests
Tests all core modules: recommender, transitions, journey, bridge, moods, camelot.
Seeds 25 mock techno tracks, runs 35 tests, reports pass/fail.

Usage:
    python scripts/test_engine.py          # run tests, cleanup after
    python scripts/test_engine.py --keep   # keep test data in DB
"""

import sys
import os
import argparse
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from database import SessionLocal, Track
from recommender import (
    recommend_tracks, similar_tracks, build_cache,
    get_cache, invalidate_cache,
)
from transitions import score_transition, _timbral_similarity
from moods import (
    list_moods, get_profile, track_fits_subgenre,
    get_subgenre_compatibility,
)
from journey import bpm_journey
from bridge import find_bridge_tracks
from camelot import get_camelot, compatible_keys

TEST_PREFIX = "test:"

# ---------------------------------------------------------------------------
# Colored terminal output
# ---------------------------------------------------------------------------

class TestRunner:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []

    def section(self, title):
        print(f"\n{self.BOLD}{self.CYAN}{'=' * 60}{self.RESET}")
        print(f"{self.BOLD}{self.CYAN}  {title}{self.RESET}")
        print(f"{self.BOLD}{self.CYAN}{'=' * 60}{self.RESET}")

    def ok(self, name, detail=""):
        self.passed += 1
        self.results.append((True, name))
        msg = f"  {self.GREEN}\u2714{self.RESET} {name}"
        if detail:
            msg += f"  {self.DIM}— {detail}{self.RESET}"
        print(msg)

    def fail(self, name, detail=""):
        self.failed += 1
        self.results.append((False, name))
        msg = f"  {self.RED}\u2718{self.RESET} {name}"
        if detail:
            msg += f"  {self.DIM}— {detail}{self.RESET}"
        print(msg)

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{self.BOLD}{'=' * 60}{self.RESET}")
        color = self.GREEN if self.failed == 0 else self.RED
        print(f"{self.BOLD}  {color}{self.passed}/{total} tests passed{self.RESET}")
        if self.failed > 0:
            print(f"  {self.RED}Failed:{self.RESET}")
            for ok, name in self.results:
                if not ok:
                    print(f"    {self.RED}\u2718{self.RESET} {name}")
        print(f"{self.BOLD}{'=' * 60}{self.RESET}")


# ---------------------------------------------------------------------------
# Mock data — 25 realistic techno tracks across 6 subgenres
# ---------------------------------------------------------------------------

SUBGENRE_SEEDS = {
    "detroit": 10,
    "berlin": 20,
    "melodic": 30,
    "minimal": 40,
    "dark": 50,
    "acid": 60,
}


def _make_vectors(subgenre_seed, track_offset):
    """Create subgenre-correlated vectors so timbral tests pass deterministically."""
    base_rng = np.random.RandomState(subgenre_seed)
    base_mfcc = base_rng.randn(26)
    base_embed = base_rng.randn(39)

    prng = np.random.RandomState(subgenre_seed * 100 + track_offset)
    n = 0.3  # noise scale — keeps same-subgenre tracks close together

    mfcc = (base_mfcc + prng.randn(26) * n).tolist()
    embedding = (base_embed + prng.randn(39) * n).tolist()
    intro_vec = (base_embed + prng.randn(39) * n * 1.2).tolist()
    peak_vec = (base_embed + prng.randn(39) * n * 0.8).tolist()
    outro_vec = (base_embed + prng.randn(39) * n * 1.0).tolist()
    return mfcc, embedding, intro_vec, peak_vec, outro_vec


def _build_track(title, artist, bpm, key, camelot, energy, danceability,
                 brightness, loudness, sc, sf, sr_, zcr, rs, onr, dc, hhr,
                 label, era, etag, ib, ob, ci, co, dur,
                 subgenre_seed, offset):
    mfcc, emb, iv, pv, ov = _make_vectors(subgenre_seed, offset)
    return {
        "file_path": f"{TEST_PREFIX}{title.lower().replace(' ', '_')}",
        "title": title, "artist": artist,
        "bpm": bpm, "key": key, "camelot_code": camelot,
        "energy": energy, "danceability": danceability,
        "brightness": brightness, "loudness": loudness,
        "spectral_centroid": sc, "spectral_flux": sf,
        "spectral_rolloff": sr_, "zero_crossing_rate": zcr,
        "rhythm_strength": rs, "onset_rate": onr,
        "dynamic_complexity": dc, "hpss_harmonic_ratio": hhr,
        "label": label, "era": era, "energy_tag": etag,
        "intro_bars": ib, "outro_bars": ob,
        "has_clean_intro": ci, "has_clean_outro": co,
        "duration": dur,
        "mfcc_vector": mfcc, "embedding": emb,
        "intro_vector": iv, "peak_vector": pv, "outro_vector": ov,
        "analysis_version": "3.0",
        "feature_extractor_version": "3.0",
        "normalization_version": "1.0",
    }


MOCK_TRACKS = [
    # ---- DETROIT (4) — BPM 125-135, energy 50k-150k, brightness 800-2000 ----
    _build_track("Warehouse Pulse", "Derrick Hayes", 128.0,
                 "A minor", "8A", 85000.0, 1.8, 1200.0, -8.5,
                 2800.0, 0.15, 6500.0, 0.08, 0.82, 4.5, 0.35, 0.45,
                 "Planet E", "classic", "groove", 16, 16, True, True, 420.0,
                 SUBGENRE_SEEDS["detroit"], 0),
    _build_track("Detroit Calling", "Kevin Saunderson Jr", 130.0,
                 "C minor", "5A", 110000.0, 2.1, 1500.0, -7.2,
                 3200.0, 0.18, 7200.0, 0.09, 0.88, 5.0, 0.30, 0.40,
                 "Transmat", "classic", "peak", 8, 16, False, True, 380.0,
                 SUBGENRE_SEEDS["detroit"], 1),
    _build_track("Motor City Groove", "Juan Atkins III", 132.0,
                 "D minor", "7A", 95000.0, 1.9, 1100.0, -8.0,
                 2600.0, 0.14, 6000.0, 0.07, 0.85, 4.8, 0.32, 0.42,
                 "M-Plant", "second_wave", "groove", 16, 8, True, False, 450.0,
                 SUBGENRE_SEEDS["detroit"], 2),
    _build_track("Inner City Dawn", "Moodymann Jr", 126.0,
                 "F minor", "4A", 65000.0, 1.5, 900.0, -10.0,
                 2200.0, 0.11, 5500.0, 0.06, 0.75, 4.0, 0.40, 0.50,
                 "Planet E", "modern", "warmup", 32, 16, True, True, 520.0,
                 SUBGENRE_SEEDS["detroit"], 3),

    # ---- BERLIN (5) — BPM 130-145, energy 60k-200k, brightness 600-1800 ----
    _build_track("Berghain Concrete", "Marcel Dettmann Jr", 133.0,
                 "C# minor", "12A", 140000.0, 1.5, 900.0, -6.5,
                 2400.0, 0.20, 5800.0, 0.07, 0.90, 5.5, 0.25, 0.35,
                 "Ostgut Ton", "modern", "peak", 8, 8, False, True, 390.0,
                 SUBGENRE_SEEDS["berlin"], 0),
    _build_track("Tresor Basement", "Surgeon Jr", 138.0,
                 "G minor", "6A", 180000.0, 1.2, 700.0, -5.0,
                 2000.0, 0.25, 5000.0, 0.06, 0.95, 6.2, 0.20, 0.28,
                 "Tresor", "modern", "peak", 4, 8, False, True, 350.0,
                 SUBGENRE_SEEDS["berlin"], 1),
    _build_track("Panorama Bar Night", "Ben Klock Jr", 135.0,
                 "A minor", "8A", 120000.0, 1.8, 1100.0, -7.0,
                 2800.0, 0.18, 6200.0, 0.08, 0.87, 5.0, 0.28, 0.38,
                 "Ostgut Ton", "modern", "groove", 16, 16, True, True, 480.0,
                 SUBGENRE_SEEDS["berlin"], 2),
    _build_track("KitKat Ritual", "Kobosil Jr", 142.0,
                 "D# minor", "2A", 190000.0, 1.1, 650.0, -4.5,
                 1800.0, 0.28, 4800.0, 0.05, 0.92, 6.8, 0.18, 0.25,
                 "Token", "modern", "peak", 4, 4, False, False, 320.0,
                 SUBGENRE_SEEDS["berlin"], 3),
    _build_track("Sisyphos Sunday", "DVS1 Jr", 131.0,
                 "B minor", "10A", 95000.0, 1.6, 1000.0, -7.5,
                 2600.0, 0.16, 6000.0, 0.07, 0.85, 4.8, 0.30, 0.40,
                 "CLR", "second_wave", "groove", 16, 16, True, True, 440.0,
                 SUBGENRE_SEEDS["berlin"], 4),

    # ---- MELODIC (4) — BPM 120-135, energy 30k-120k, brightness 1200-3000 ----
    _build_track("Ethereal Descent", "Stephan Bodzin Jr", 122.0,
                 "E minor", "9A", 55000.0, 2.2, 2200.0, -9.0,
                 3500.0, 0.10, 8000.0, 0.10, 0.70, 3.5, 0.45, 0.60,
                 "Afterlife", "modern", "warmup", 32, 32, True, True, 540.0,
                 SUBGENRE_SEEDS["melodic"], 0),
    _build_track("Northern Lights", "Tale of Us Jr", 126.0,
                 "A minor", "8A", 80000.0, 2.5, 2600.0, -8.0,
                 4000.0, 0.12, 8500.0, 0.12, 0.75, 4.0, 0.40, 0.55,
                 "Kompakt", "modern", "groove", 16, 16, True, True, 480.0,
                 SUBGENRE_SEEDS["melodic"], 1),
    _build_track("Melancholic Horizon", "Recondite Jr", 124.0,
                 "F# minor", "11A", 45000.0, 1.8, 1800.0, -10.0,
                 3000.0, 0.08, 7500.0, 0.09, 0.65, 3.2, 0.50, 0.65,
                 "Innervisions", "modern", "warmup", 32, 32, True, True, 600.0,
                 SUBGENRE_SEEDS["melodic"], 2),
    _build_track("Sunrise Protocol", "Mind Against Jr", 130.0,
                 "C major", "8B", 100000.0, 2.6, 2800.0, -7.5,
                 4200.0, 0.14, 9000.0, 0.11, 0.80, 4.5, 0.38, 0.52,
                 "Afterlife", "modern", "peak", 16, 16, True, True, 420.0,
                 SUBGENRE_SEEDS["melodic"], 3),

    # ---- MINIMAL (4) — BPM 128-138, energy 20k-80k, brightness 400-1200 ----
    _build_track("Micro Movements", "Richie Hawtin Jr", 130.0,
                 "D minor", "7A", 35000.0, 1.2, 600.0, -11.0,
                 1800.0, 0.06, 4500.0, 0.05, 0.65, 3.0, 0.50, 0.52,
                 "Minus", "second_wave", "groove", 32, 16, True, True, 480.0,
                 SUBGENRE_SEEDS["minimal"], 0),
    _build_track("Reduced Signal", "Ricardo Villalobos Jr", 133.0,
                 "G minor", "6A", 50000.0, 1.5, 800.0, -9.5,
                 2100.0, 0.08, 5000.0, 0.06, 0.70, 3.5, 0.45, 0.48,
                 "Perlon", "second_wave", "groove", 16, 16, True, True, 520.0,
                 SUBGENRE_SEEDS["minimal"], 1),
    _build_track("Sparse Geometry", "Zip Jr", 129.0,
                 "A minor", "8A", 28000.0, 1.0, 500.0, -12.0,
                 1500.0, 0.05, 4000.0, 0.04, 0.60, 2.8, 0.55, 0.55,
                 "Perlon", "modern", "warmup", 32, 32, True, True, 560.0,
                 SUBGENRE_SEEDS["minimal"], 2),
    _build_track("Click Pattern", "Luciano Jr", 135.0,
                 "C minor", "5A", 60000.0, 1.6, 950.0, -9.0,
                 2300.0, 0.09, 5200.0, 0.07, 0.72, 3.8, 0.42, 0.46,
                 "Cocoon", "modern", "groove", 16, 16, True, True, 440.0,
                 SUBGENRE_SEEDS["minimal"], 3),

    # ---- DARK (4) — BPM 132-148, energy 70k-220k, brightness 400-1200 ----
    _build_track("Shadow Protocol", "Perc Jr", 136.0,
                 "F minor", "4A", 160000.0, 1.3, 600.0, -5.5,
                 2000.0, 0.22, 4800.0, 0.06, 0.88, 5.5, 0.22, 0.30,
                 "Perc Trax", "modern", "peak", 4, 8, False, True, 360.0,
                 SUBGENRE_SEEDS["dark"], 0),
    _build_track("Void Resonance", "Ansome Jr", 140.0,
                 "C# minor", "12A", 200000.0, 1.1, 500.0, -4.0,
                 1700.0, 0.28, 4200.0, 0.05, 0.92, 6.0, 0.18, 0.25,
                 "Mord", "modern", "peak", 4, 4, False, False, 340.0,
                 SUBGENRE_SEEDS["dark"], 1),
    _build_track("Black Mass", "UVB Jr", 145.0,
                 "G# minor", "1A", 210000.0, 1.0, 450.0, -3.5,
                 1500.0, 0.30, 3800.0, 0.04, 0.95, 6.5, 0.15, 0.20,
                 "Mord", "modern", "peak", 4, 4, False, False, 310.0,
                 SUBGENRE_SEEDS["dark"], 2),
    _build_track("Obsidian Loop", "SHDW Jr", 134.0,
                 "D# minor", "2A", 120000.0, 1.5, 750.0, -6.0,
                 2200.0, 0.19, 5200.0, 0.07, 0.85, 5.0, 0.25, 0.35,
                 "Token", "modern", "groove", 8, 8, True, True, 400.0,
                 SUBGENRE_SEEDS["dark"], 3),

    # ---- ACID (4) — BPM 128-145, energy 50k-180k, brightness 1500-4000 ----
    _build_track("Acid Rain 303", "DJ Pierre Jr", 132.0,
                 "A minor", "8A", 100000.0, 2.0, 2500.0, -7.0,
                 3800.0, 0.18, 7800.0, 0.11, 0.80, 4.8, 0.38, 0.48,
                 "Acid Waxa", "classic", "groove", 16, 16, True, True, 420.0,
                 SUBGENRE_SEEDS["acid"], 0),
    _build_track("Roland Worship", "Phuture Jr", 136.0,
                 "D minor", "7A", 140000.0, 1.8, 3000.0, -5.5,
                 4200.0, 0.22, 8200.0, 0.13, 0.85, 5.2, 0.32, 0.42,
                 "Trax Records", "classic", "peak", 8, 8, False, True, 380.0,
                 SUBGENRE_SEEDS["acid"], 1),
    _build_track("Squelch Factory", "Tin Man Jr", 128.0,
                 "E minor", "9A", 70000.0, 2.2, 2000.0, -8.5,
                 3200.0, 0.14, 7000.0, 0.09, 0.75, 4.2, 0.42, 0.52,
                 "Acid Test", "modern", "warmup", 32, 16, True, True, 500.0,
                 SUBGENRE_SEEDS["acid"], 2),
    _build_track("TB Line", "Ceephax Jr", 140.0,
                 "G minor", "6A", 160000.0, 1.6, 3500.0, -5.0,
                 4500.0, 0.25, 8800.0, 0.14, 0.88, 5.8, 0.28, 0.38,
                 "Balans", "modern", "peak", 8, 8, False, False, 360.0,
                 SUBGENRE_SEEDS["acid"], 3),
]


# ---------------------------------------------------------------------------
# Seed / cleanup
# ---------------------------------------------------------------------------

def seed_tracks(db):
    """Insert mock tracks, return list of inserted IDs in insertion order."""
    # Remove any leftover test tracks first
    db.query(Track).filter(Track.file_path.like(f"{TEST_PREFIX}%")).delete(
        synchronize_session=False)
    db.commit()

    for data in MOCK_TRACKS:
        db.add(Track(**data))
    db.commit()

    test_tracks = (
        db.query(Track)
        .filter(Track.file_path.like(f"{TEST_PREFIX}%"))
        .order_by(Track.id)
        .all()
    )
    return [t.id for t in test_tracks]


def cleanup_tracks(db, track_ids):
    db.query(Track).filter(Track.id.in_(track_ids)).delete(
        synchronize_session=False)
    db.commit()


# ---------------------------------------------------------------------------
# Test sections
# ---------------------------------------------------------------------------

def test_db_connectivity(runner, db):
    runner.section("DATABASE CONNECTIVITY")

    try:
        result = db.execute(text("SELECT 1")).fetchone()
        assert result[0] == 1
        runner.ok("PostgreSQL connection", "SELECT 1 returned 1")
    except Exception as e:
        runner.fail("PostgreSQL connection", str(e))

    try:
        count = db.query(Track).count()
        runner.ok("Tracks table accessible", f"{count} tracks in database")
    except Exception as e:
        runner.fail("Tracks table accessible", str(e))


def test_cache_build(runner, db):
    runner.section("CACHE BUILD (13-feature vectors)")

    try:
        invalidate_cache()
        build_cache(db)
        runner.ok("build_cache() completes")
    except Exception as e:
        runner.fail("build_cache() completes", str(e))
        return

    cache = get_cache(db)
    if cache and "matrix" in cache and "tracks" in cache:
        n = len(cache["tracks"])
        shape = cache["matrix"].shape
        runner.ok("Cache structure valid", f"{n} tracks, matrix {shape}")
    else:
        runner.fail("Cache structure valid", "Cache is None or missing keys")
        return

    if cache["matrix"].shape[1] == 13:
        runner.ok("13-feature vector width", f"columns = {cache['matrix'].shape[1]}")
    else:
        runner.fail("13-feature vector width",
                    f"Expected 13, got {cache['matrix'].shape[1]}")


def test_mfcc_blending(runner, db):
    runner.section("MFCC TIMBRAL BLENDING")

    cache = get_cache(db)
    if cache and "mfcc_matrix" in cache and cache["mfcc_matrix"] is not None:
        shape = cache["mfcc_matrix"].shape
        runner.ok("MFCC matrix in cache", f"shape = {shape}")
    else:
        runner.fail("MFCC matrix in cache", "mfcc_matrix missing")
        return

    if cache["mfcc_matrix"].shape[1] == 26:
        runner.ok("MFCC 26-dim vectors", "26 columns confirmed")
    else:
        runner.fail("MFCC 26-dim vectors",
                    f"Expected 26, got {cache['mfcc_matrix'].shape[1]}")

    if "mfcc_mean" in cache and "mfcc_std" in cache:
        runner.ok("MFCC normalization stats", f"mean len={len(cache['mfcc_mean'])}")
    else:
        runner.fail("MFCC normalization stats", "mfcc_mean/mfcc_std missing")


def test_recommender(runner, db, track_ids):
    runner.section("RECOMMENDER")

    # Basic recommend
    try:
        results = recommend_tracks(db, bpm=130.0, limit=5)
        if len(results) > 0:
            runner.ok("recommend_tracks() basic", f"returned {len(results)} tracks")
        else:
            runner.fail("recommend_tracks() basic", "returned 0 tracks")
    except Exception as e:
        runner.fail("recommend_tracks() basic", str(e))
        results = []

    # Camelot filter
    try:
        results_c = recommend_tracks(db, bpm=130.0, camelot="8A", limit=5)
        if len(results_c) > 0:
            runner.ok("recommend with camelot='8A'", f"returned {len(results_c)}")
        else:
            runner.fail("recommend with camelot='8A'", "no results")
    except Exception as e:
        runner.fail("recommend with camelot='8A'", str(e))

    # Mood filter
    try:
        results_m = recommend_tracks(db, bpm=130.0, mood="detroit", limit=10)
        if len(results_m) > 0:
            all_in = all(
                125 - 4 <= r["bpm"] <= 135 + 4
                for r in results_m if r.get("bpm")
            )
            if all_in:
                runner.ok("recommend mood='detroit'",
                          f"{len(results_m)} tracks, all within detroit BPM")
            else:
                runner.fail("recommend mood='detroit'",
                            "some tracks outside detroit BPM envelope")
        else:
            runner.fail("recommend mood='detroit'", "no results")
    except Exception as e:
        runner.fail("recommend mood='detroit'", str(e))
        results_m = []

    # Score + reasons payload
    if results_m and "score" in results_m[0] and "reasons" in results_m[0]:
        runner.ok("score + reasons in payload",
                  f"score={results_m[0]['score']}, reasons={len(results_m[0]['reasons'])}")
    else:
        runner.fail("score + reasons in payload", "missing keys")


def test_similar_tracks(runner, db, track_ids):
    runner.section("SIMILAR TRACKS")

    source_id = track_ids[0]  # Warehouse Pulse

    try:
        result = similar_tracks(db, source_id, limit=5)
    except Exception as e:
        runner.fail("similar_tracks() structure", str(e))
        return

    if "source" in result and "similar" in result:
        runner.ok("similar_tracks() structure",
                  f"Source: {result['source']['title']}, {len(result['similar'])} similar")
    else:
        runner.fail("similar_tracks() structure", f"keys: {list(result.keys())}")
        return

    sim_ids = [s.get("id") for s in result["similar"]]
    if source_id not in sim_ids:
        runner.ok("Source excluded from similar", f"ID {source_id} not in results")
    else:
        runner.fail("Source excluded from similar", f"ID {source_id} found in results")

    if result["similar"]:
        src_bpm = result["source"]["bpm"]
        max_diff = max(
            abs(s["bpm"] - src_bpm)
            for s in result["similar"] if s.get("bpm")
        )
        if max_diff <= 15:
            runner.ok("Similar within 15 BPM", f"max diff={max_diff:.1f}")
        else:
            runner.fail("Similar within 15 BPM", f"max diff={max_diff:.1f}")
    else:
        runner.fail("Similar within 15 BPM", "no similar tracks")


def test_transition_scoring(runner, db, track_ids):
    runner.section("TRANSITION SCORING (8 dimensions)")

    # Compatible pair: two detroit tracks
    try:
        r1 = score_transition(db, track_ids[0], track_ids[1],
                              subgenre_a="detroit", subgenre_b="detroit")
    except Exception as e:
        runner.fail("score_transition() compatible", str(e))
        return

    if "overall_score" in r1:
        s1 = r1["overall_score"]
        runner.ok("score_transition() compatible",
                  f"Detroit\u2192Detroit = {s1:.4f}, {r1['verdict']}")
    else:
        runner.fail("score_transition() compatible", r1.get("error", "??"))
        return

    # Check all 8+2 breakdown keys
    expected = ["bpm_score", "harmonic_score", "energy_score",
                "subgenre_score", "label_score", "timbral_score",
                "learned_score", "era_bonus", "structure_bonus"]
    if "breakdown" in r1:
        missing = [k for k in expected if k not in r1["breakdown"]]
        if not missing:
            runner.ok("Breakdown has all dimensions", "8 scores + 2 bonuses")
        else:
            runner.fail("Breakdown has all dimensions", f"missing: {missing}")
    else:
        runner.fail("Breakdown has all dimensions", "no breakdown key")

    # Incompatible pair should score lower (melodic warmup → dark peak)
    mel_idx = 9   # Ethereal Descent (melodic, 122 BPM)
    dark_idx = 20  # Black Mass (dark, 145 BPM)
    try:
        r2 = score_transition(db, track_ids[mel_idx], track_ids[dark_idx],
                              subgenre_a="melodic", subgenre_b="dark")
        if "overall_score" in r2:
            s2 = r2["overall_score"]
            if s2 < s1:
                runner.ok("Incompatible scores lower",
                          f"Melodic\u2192Dark={s2:.4f} < Detroit\u2192Detroit={s1:.4f}")
            else:
                runner.fail("Incompatible scores lower",
                            f"Melodic\u2192Dark={s2:.4f} >= Detroit\u2192Detroit={s1:.4f}")
        else:
            runner.fail("Incompatible scores lower", r2.get("error", "??"))
    except Exception as e:
        runner.fail("Incompatible scores lower", str(e))

    # Score clamped 0-1
    if 0.0 <= r1["overall_score"] <= 1.0:
        runner.ok("Score clamped [0, 1]", f"{r1['overall_score']}")
    else:
        runner.fail("Score clamped [0, 1]", f"{r1['overall_score']}")


def test_timbral_transition(runner, db, track_ids):
    runner.section("TIMBRAL SIMILARITY (segment vectors)")

    a = db.query(Track).filter(Track.id == track_ids[0]).first()  # detroit
    b = db.query(Track).filter(Track.id == track_ids[1]).first()  # detroit

    if not (a and b):
        runner.fail("Load test tracks", "tracks not found")
        return

    if a.outro_vector and b.intro_vector:
        score = _timbral_similarity(a, b)
        if isinstance(score, float) and -1.0 <= score <= 1.0:
            runner.ok("_timbral_similarity() with segments",
                      f"outro(A)\u2192intro(B) = {score:.4f}")
        else:
            runner.fail("_timbral_similarity() with segments", f"invalid: {score}")
    else:
        runner.fail("_timbral_similarity() with segments", "segment vectors missing")

    # Same-subgenre > cross-subgenre
    c = db.query(Track).filter(Track.id == track_ids[17]).first()  # dark: Shadow Protocol
    if c:
        same = _timbral_similarity(a, b)
        cross = _timbral_similarity(a, c)
        if same > cross:
            runner.ok("Same-subgenre timbral > cross",
                      f"detroit\u2194detroit={same:.4f} > detroit\u2194dark={cross:.4f}")
        else:
            runner.fail("Same-subgenre timbral > cross",
                        f"same={same:.4f} <= cross={cross:.4f}")
    else:
        runner.fail("Same-subgenre timbral > cross", "dark track not found")


def test_journey(runner, db):
    runner.section("BPM JOURNEY")

    try:
        result = bpm_journey(db, 125, 145, steps=6)
    except Exception as e:
        runner.fail("bpm_journey() 125\u2192145", str(e))
        return

    if "journey" in result and len(result["journey"]) > 0:
        runner.ok("bpm_journey() 125\u2192145", f"{result['found']} steps found")
    else:
        runner.fail("bpm_journey() 125\u2192145", f"got: {result}")
        return

    if len(result["journey"]) > 1:
        targets = [s["target_bpm"] for s in result["journey"]]
        increasing = all(targets[i] <= targets[i + 1]
                         for i in range(len(targets) - 1))
        if increasing:
            runner.ok("Target BPMs increase",
                      f"{targets[0]:.0f} \u2192 {targets[-1]:.0f}")
        else:
            runner.fail("Target BPMs increase", f"{targets}")

    ids = [s["id"] for s in result["journey"]]
    if len(ids) == len(set(ids)):
        runner.ok("No duplicate tracks", f"{len(ids)} unique")
    else:
        runner.fail("No duplicate tracks", f"{len(ids)} total, {len(set(ids))} unique")


def test_bridge(runner, db, track_ids):
    runner.section("BRIDGE TRACKS")

    source_id = track_ids[0]  # Warehouse Pulse (detroit 128 BPM)

    try:
        result = find_bridge_tracks(db, from_id=source_id,
                                    target_subgenre="berlin")
    except Exception as e:
        runner.fail("find_bridge_tracks() detroit\u2192berlin", str(e))
        return

    if "bridge_tracks" in result and len(result["bridge_tracks"]) > 0:
        runner.ok("find_bridge_tracks() detroit\u2192berlin",
                  f"{result['steps_found']} steps")
    else:
        runner.fail("find_bridge_tracks() detroit\u2192berlin", f"got: {result}")
        return

    bridge_bpms = [s["bpm"] for s in result["bridge_tracks"]]
    target_bpm = result["target_bpm"]
    source_bpm = 128.0
    last = bridge_bpms[-1]
    if abs(last - target_bpm) <= abs(source_bpm - target_bpm):
        runner.ok("Bridge BPMs trend toward target",
                  f"{source_bpm} \u2192 {last:.0f} \u2192 target {target_bpm:.0f}")
    else:
        runner.fail("Bridge BPMs trend toward target",
                    f"end={last}, target={target_bpm}")

    bridge_ids = [s["id"] for s in result["bridge_tracks"]]
    if source_id not in bridge_ids:
        runner.ok("Source not in bridge results")
    else:
        runner.fail("Source not in bridge results")


def test_moods(runner, db):
    runner.section("MOODS / SUBGENRE PROFILES")

    moods = list_moods()
    if len(moods) >= 14:
        runner.ok("list_moods() count", f"{len(moods)} subgenres")
    else:
        runner.fail("list_moods() count", f"expected \u226514, got {len(moods)}")

    profile = get_profile("detroit")
    needed = ["bpm_range", "energy_range", "brightness_range",
              "danceability_range", "bpm_tolerance", "key_weight"]
    missing = [k for k in needed if k not in profile]
    if not missing:
        runner.ok("get_profile('detroit')", f"BPM {profile['bpm_range']}")
    else:
        runner.fail("get_profile('detroit')", f"missing: {missing}")

    det = (
        db.query(Track)
        .filter(Track.file_path.like(f"{TEST_PREFIX}%"),
                Track.bpm.between(125, 135))
        .first()
    )
    if det and track_fits_subgenre(det, "detroit"):
        runner.ok("track_fits_subgenre() detroit", f"'{det.title}' fits")
    elif det:
        runner.fail("track_fits_subgenre() detroit",
                    f"BPM={det.bpm}, energy={det.energy}")
    else:
        runner.fail("track_fits_subgenre() detroit", "no matching test track")

    compat = get_subgenre_compatibility("detroit", "hypnotic")
    incompat = get_subgenre_compatibility("ambient", "hard")
    if compat > incompat:
        runner.ok("Subgenre compatibility ordering",
                  f"det\u2194hyp={compat} > amb\u2194hard={incompat}")
    else:
        runner.fail("Subgenre compatibility ordering",
                    f"det\u2194hyp={compat}, amb\u2194hard={incompat}")


def test_camelot(runner):
    runner.section("CAMELOT WHEEL")

    r = get_camelot("A minor")
    if r == "8A":
        runner.ok("get_camelot('A minor') = '8A'")
    else:
        runner.fail("get_camelot('A minor')", f"got '{r}'")

    compat = compatible_keys("8A")
    if len(compat) == 4:
        runner.ok("compatible_keys('8A') returns 4", f"{compat}")
    else:
        runner.fail("compatible_keys('8A') returns 4", f"got {len(compat)}: {compat}")

    if "8A" in compat:
        runner.ok("compatible_keys includes self")
    else:
        runner.fail("compatible_keys includes self", "'8A' not in results")

    expected = {"7A", "9A", "8B"}
    found = expected.intersection(set(compat))
    if found == expected:
        runner.ok("Adjacent + relative keys", f"{found}")
    else:
        runner.fail("Adjacent + relative keys", f"expected {expected}, found {found}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SOMA Engine Integration Tests")
    parser.add_argument("--keep", action="store_true",
                        help="Keep test data after run")
    args = parser.parse_args()

    R = TestRunner

    print(f"\n{R.BOLD}{R.CYAN}"
          f"  ___  ___  __  __   _   \n"
          f" / __|/ _ \\|  \\/  | /_\\  \n"
          f" \\__ \\ (_) | |\\/| |/ _ \\ \n"
          f" |___/\\___/|_|  |_/_/ \\_\\\n"
          f"  Engine Integration Tests{R.RESET}\n"
          f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    runner = TestRunner()
    db = SessionLocal()
    track_ids = []

    try:
        # 1. DB connectivity
        test_db_connectivity(runner, db)

        # 2. Seed test data
        runner.section("SEEDING TEST DATA")
        try:
            track_ids = seed_tracks(db)
            invalidate_cache()
            print(f"  Seeded {len(track_ids)} tracks "
                  f"(IDs {track_ids[0]}..{track_ids[-1]})")
        except Exception as e:
            print(f"  {R.RED}Seed failed: {e}{R.RESET}")
            db.rollback()
            db.close()
            sys.exit(1)

        # 3. Run all tests
        test_cache_build(runner, db)
        test_mfcc_blending(runner, db)
        test_recommender(runner, db, track_ids)
        test_similar_tracks(runner, db, track_ids)
        test_transition_scoring(runner, db, track_ids)
        test_timbral_transition(runner, db, track_ids)
        test_journey(runner, db)
        test_bridge(runner, db, track_ids)
        test_moods(runner, db)
        test_camelot(runner)

        # 4. Summary
        runner.summary()

    finally:
        if track_ids and not args.keep:
            try:
                cleanup_tracks(db, track_ids)
                print(f"\n  Cleaned up {len(track_ids)} test tracks.")
            except Exception:
                db.rollback()
                print(f"\n  {R.YELLOW}Cleanup failed — test data may remain.{R.RESET}")
        elif track_ids:
            print(f"\n  {R.YELLOW}--keep: test data retained "
                  f"(IDs {track_ids[0]}..{track_ids[-1]}){R.RESET}")
        db.close()

    sys.exit(0 if runner.failed == 0 else 1)


if __name__ == "__main__":
    main()
