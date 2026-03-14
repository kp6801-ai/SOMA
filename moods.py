# moods.py — Subgenre profiles with precise audio envelopes

SUBGENRE_PROFILES = {
    "detroit": {
        "bpm_range": (125, 135),
        "energy_range": (50000, 150000),
        "brightness_range": (800, 2000),
        "danceability_range": (1.2, 2.5),
        "bpm_tolerance": 4.0,
        "key_weight": 0.25,
        "energy_weight": 0.35,
        "description": "Soulful, funky, deep. The original sound.",
        "compatible_subgenres": ["hypnotic", "dub", "minimal"],
    },
    "berlin": {
        "bpm_range": (130, 145),
        "energy_range": (60000, 200000),
        "brightness_range": (600, 1800),
        "danceability_range": (1.0, 2.2),
        "bpm_tolerance": 5.0,
        "key_weight": 0.20,
        "energy_weight": 0.40,
        "description": "Industrial, relentless, hypnotic.",
        "compatible_subgenres": ["dark", "industrial", "minimal"],
    },
    "melodic": {
        "bpm_range": (120, 135),
        "energy_range": (30000, 120000),
        "brightness_range": (1200, 3000),
        "danceability_range": (1.4, 2.8),
        "bpm_tolerance": 3.0,
        "key_weight": 0.45,
        "energy_weight": 0.20,
        "description": "Emotional, melodic, atmospheric.",
        "compatible_subgenres": ["ambient", "euphoric", "driving"],
    },
    "minimal": {
        "bpm_range": (128, 138),
        "energy_range": (20000, 80000),
        "brightness_range": (400, 1200),
        "danceability_range": (0.8, 1.8),
        "bpm_tolerance": 2.0,
        "key_weight": 0.30,
        "energy_weight": 0.25,
        "description": "Stripped back, hypnotic, repetitive.",
        "compatible_subgenres": ["detroit", "dub", "berlin"],
    },
    "dark": {
        "bpm_range": (132, 148),
        "energy_range": (70000, 220000),
        "brightness_range": (400, 1200),
        "danceability_range": (1.0, 2.0),
        "bpm_tolerance": 5.0,
        "key_weight": 0.20,
        "energy_weight": 0.45,
        "description": "Ominous, heavy, oppressive.",
        "compatible_subgenres": ["industrial", "berlin", "hard"],
    },
    "industrial": {
        "bpm_range": (135, 155),
        "energy_range": (100000, 300000),
        "brightness_range": (300, 1000),
        "danceability_range": (0.8, 1.8),
        "bpm_tolerance": 6.0,
        "key_weight": 0.15,
        "energy_weight": 0.50,
        "description": "Harsh, mechanical, aggressive.",
        "compatible_subgenres": ["dark", "hard", "berlin"],
    },
    "acid": {
        "bpm_range": (128, 145),
        "energy_range": (50000, 180000),
        "brightness_range": (1500, 4000),
        "danceability_range": (1.3, 2.5),
        "bpm_tolerance": 4.0,
        "key_weight": 0.25,
        "energy_weight": 0.30,
        "description": "303 basslines, squelchy, hypnotic.",
        "compatible_subgenres": ["detroit", "hypnotic", "minimal"],
    },
    "hard": {
        "bpm_range": (140, 160),
        "energy_range": (120000, 400000),
        "brightness_range": (500, 1500),
        "danceability_range": (1.0, 2.0),
        "bpm_tolerance": 8.0,
        "key_weight": 0.10,
        "energy_weight": 0.55,
        "description": "Fast, punishing, relentless.",
        "compatible_subgenres": ["industrial", "dark"],
    },
    "dub": {
        "bpm_range": (120, 132),
        "energy_range": (20000, 90000),
        "brightness_range": (300, 1000),
        "danceability_range": (1.0, 2.2),
        "bpm_tolerance": 3.0,
        "key_weight": 0.35,
        "energy_weight": 0.25,
        "description": "Spacious, echo-heavy, deep.",
        "compatible_subgenres": ["detroit", "minimal", "ambient"],
    },
    "ambient": {
        "bpm_range": (100, 125),
        "energy_range": (5000, 50000),
        "brightness_range": (500, 2000),
        "danceability_range": (0.5, 1.5),
        "bpm_tolerance": 8.0,
        "key_weight": 0.40,
        "energy_weight": 0.20,
        "description": "Atmospheric, textural, spacious.",
        "compatible_subgenres": ["dub", "melodic"],
    },
    "hypnotic": {
        "bpm_range": (128, 140),
        "energy_range": (40000, 140000),
        "brightness_range": (600, 1600),
        "danceability_range": (1.2, 2.3),
        "bpm_tolerance": 3.0,
        "key_weight": 0.30,
        "energy_weight": 0.35,
        "description": "Repetitive, trancelike, meditative.",
        "compatible_subgenres": ["detroit", "minimal", "acid"],
    },
    "hardgroove": {
        "bpm_range": (132, 145),
        "energy_range": (80000, 250000),
        "brightness_range": (600, 1600),
        "danceability_range": (1.3, 2.5),
        "bpm_tolerance": 4.0,
        "key_weight": 0.20,
        "energy_weight": 0.45,
        "description": "Hard but groovy, functional techno.",
        "compatible_subgenres": ["berlin", "dark", "driving"],
    },
    "euphoric": {
        "bpm_range": (128, 140),
        "energy_range": (60000, 180000),
        "brightness_range": (1500, 4000),
        "danceability_range": (1.8, 3.0),
        "bpm_tolerance": 4.0,
        "key_weight": 0.35,
        "energy_weight": 0.30,
        "description": "Peak time, uplifting, emotional.",
        "compatible_subgenres": ["melodic", "driving"],
    },
    "driving": {
        "bpm_range": (130, 145),
        "energy_range": (70000, 200000),
        "brightness_range": (800, 2200),
        "danceability_range": (1.4, 2.6),
        "bpm_tolerance": 4.0,
        "key_weight": 0.25,
        "energy_weight": 0.40,
        "description": "Forward momentum, functional, powerful.",
        "compatible_subgenres": ["berlin", "hardgroove", "euphoric"],
    },
}

# Cross-subgenre transition compatibility matrix
# Score 1.0 = flows perfectly, 0.0 = never mix these
SUBGENRE_TRANSITION_MATRIX = {
    ("detroit", "hypnotic"): 0.95,
    ("detroit", "minimal"): 0.90,
    ("detroit", "dub"): 0.92,
    ("berlin", "dark"): 0.95,
    ("berlin", "industrial"): 0.88,
    ("berlin", "minimal"): 0.85,
    ("melodic", "euphoric"): 0.95,
    ("melodic", "driving"): 0.90,
    ("melodic", "ambient"): 0.85,
    ("minimal", "dub"): 0.90,
    ("minimal", "hypnotic"): 0.88,
    ("dark", "industrial"): 0.92,
    ("dark", "hard"): 0.85,
    ("acid", "hypnotic"): 0.90,
    ("acid", "detroit"): 0.88,
    ("dub", "ambient"): 0.90,
    ("hypnotic", "acid"): 0.90,
    ("hardgroove", "driving"): 0.92,
    ("euphoric", "driving"): 0.90,
    # Hard stops — never mix these
    ("ambient", "hard"): 0.0,
    ("ambient", "industrial"): 0.0,
    ("hard", "ambient"): 0.0,
    ("industrial", "melodic"): 0.05,
    ("hard", "melodic"): 0.05,
}


def get_subgenre_compatibility(subgenre_a: str, subgenre_b: str) -> float:
    """Returns compatibility score between two subgenres (0-1)."""
    if subgenre_a == subgenre_b:
        return 1.0
    key = (subgenre_a, subgenre_b)
    reverse_key = (subgenre_b, subgenre_a)
    return SUBGENRE_TRANSITION_MATRIX.get(key,
           SUBGENRE_TRANSITION_MATRIX.get(reverse_key, 0.4))


def get_profile(subgenre: str) -> dict:
    return SUBGENRE_PROFILES.get(subgenre, SUBGENRE_PROFILES["berlin"])


def list_moods() -> list[str]:
    return sorted(SUBGENRE_PROFILES.keys())


def track_fits_subgenre(track, subgenre: str) -> bool:
    """Hard filter: does this track fit within the subgenre's audio envelope?"""
    profile = get_profile(subgenre)
    if track.bpm is None:
        return False
    bpm_min, bpm_max = profile["bpm_range"]
    tol = profile["bpm_tolerance"]
    if not (bpm_min - tol <= track.bpm <= bpm_max + tol):
        return False
    if track.energy is not None:
        emin, emax = profile["energy_range"]
        if not (emin * 0.7 <= track.energy <= emax * 1.3):
            return False
    return True
