"""
Arc presets for SOMA session types.
Each preset defines the BPM shape and track count for a session duration.
"""

# Arc type → BPM config
# bpm_start: where the session opens
# bpm_peak: the highest point in the arc
# bpm_end: where the session lands at the end
# shape: how the BPM moves ("ramp_hold_cool", "oscillate", "ramp", "descent")

ARC_PRESETS = {
    "peak_hour": {
        "label": "Peak Hour",
        "bpm_start": 128,
        "bpm_peak": 145,
        "bpm_end": 145,
        "shape": "ramp",
        "description": "Driving techno build. Starts hard, goes harder.",
    },
    "workout": {
        "label": "Workout",
        "bpm_start": 120,
        "bpm_peak": 145,
        "bpm_end": 125,
        "shape": "ramp_hold_cool",
        "description": "Ramp up, hold at peak, cool down.",
    },
    "deep_focus": {
        "label": "Deep Focus",
        "bpm_start": 85,
        "bpm_peak": 105,
        "bpm_end": 105,
        "shape": "ramp",
        "description": "Slow ease-in to a focused groove.",
    },
    "sleep": {
        "label": "Sleep",
        "bpm_start": 80,
        "bpm_peak": 80,
        "bpm_end": 55,
        "shape": "descent",
        "description": "Gradual descent into stillness.",
    },
    "meditate": {
        "label": "Meditate",
        "bpm_start": 65,
        "bpm_peak": 65,
        "bpm_end": 60,
        "shape": "descent",
        "description": "Slow, steady, near-still.",
    },
    "recovery": {
        "label": "Recovery",
        "bpm_start": 100,
        "bpm_peak": 100,
        "bpm_end": 70,
        "shape": "descent",
        "description": "Fast descent from groove to rest.",
    },
    "hiit": {
        "label": "HIIT",
        "bpm_start": 110,
        "bpm_peak": 170,
        "bpm_end": 110,
        "shape": "oscillate",
        "description": "Alternates between high-intensity bursts and recovery.",
    },
}


def get_preset(arc_type: str) -> dict:
    """Return preset config for the given arc type. Raises ValueError if unknown."""
    key = arc_type.lower().replace(" ", "_")
    if key not in ARC_PRESETS:
        valid = list(ARC_PRESETS.keys())
        raise ValueError(f"Unknown arc type '{arc_type}'. Valid options: {valid}")
    return ARC_PRESETS[key]


def tracks_for_duration(duration_min: int) -> int:
    """Estimate number of tracks for a session length. Assumes ~6 min avg track."""
    return max(4, min(30, round(duration_min / 6)))


def build_bpm_steps(preset: dict, n_tracks: int) -> list[float]:
    """
    Generate a list of target BPMs — one per track slot — based on arc shape.
    """
    import numpy as np

    start = preset["bpm_start"]
    peak = preset["bpm_peak"]
    end = preset["bpm_end"]
    shape = preset["shape"]

    if n_tracks == 1:
        return [float(start)]

    if shape == "ramp":
        steps = np.linspace(start, peak, n_tracks)

    elif shape == "descent":
        steps = np.linspace(start, end, n_tracks)

    elif shape == "ramp_hold_cool":
        # 50% ramp up, 30% hold at peak, 20% cool down
        ramp_n = max(1, round(n_tracks * 0.5))
        hold_n = max(1, round(n_tracks * 0.3))
        cool_n = max(1, n_tracks - ramp_n - hold_n)
        ramp = np.linspace(start, peak, ramp_n)
        hold = np.full(hold_n, peak)
        cool = np.linspace(peak, end, cool_n + 1)[1:]  # skip duplicate peak
        steps = np.concatenate([ramp, hold, cool])

    elif shape == "oscillate":
        # Alternates between high-intensity (peak) and recovery (start) BPMs
        steps = []
        for i in range(n_tracks):
            steps.append(peak if i % 2 == 1 else start)
        steps = np.array(steps, dtype=float)

    else:
        steps = np.linspace(start, end, n_tracks)

    return [round(float(b), 1) for b in steps[:n_tracks]]
