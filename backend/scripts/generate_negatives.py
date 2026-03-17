"""
generate_negatives.py — Generate hard negative transition pairs for model training.

For each track_a in transition_scores, find 2 "clearly bad" partner tracks:
  - BPM delta > 15, OR
  - Camelot distance > 3

Writes: negative_pairs.json [{track_a_id, track_b_id, label: 0}]

Usage:
  python generate_negatives.py
  python generate_negatives.py --ratio 2 --output ./negative_pairs.json
"""

import argparse
import json
import logging
import random
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal, Track, TransitionScore
from recommender import camelot_distance


def main():
    parser = argparse.ArgumentParser(description="Generate negative training pairs")
    parser.add_argument("--ratio", type=int, default=2,
                        help="Negatives per positive (default 2)")
    parser.add_argument("--output", default="./negative_pairs.json")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    db = SessionLocal()

    try:
        # All resolved positive pairs
        positive_pairs = db.query(TransitionScore).filter(
            TransitionScore.times_played >= 1
        ).all()

        if not positive_pairs:
            log.warning("No positive pairs in transition_scores. Run build_training_pairs.py first.")
            db.close()
            return

        # Load all tracks with BPM data
        all_tracks = db.query(Track).filter(Track.bpm.isnot(None)).all()
        log.info(f"Positive pairs: {len(positive_pairs)} | Tracks with BPM: {len(all_tracks)}")

        # Build fast lookup
        track_map = {t.id: t for t in all_tracks}
        positive_set = {(p.track_a_id, p.track_b_id) for p in positive_pairs}
        positive_set |= {(p.track_b_id, p.track_a_id) for p in positive_pairs}  # symmetric

        negatives = []
        skipped = 0

        for pos in positive_pairs:
            track_a = track_map.get(pos.track_a_id)
            if not track_a:
                continue

            # Shuffle tracks and take first N that qualify as "bad" partners
            candidates = list(all_tracks)
            random.shuffle(candidates)

            count = 0
            for track_b in candidates:
                if track_b.id == track_a.id:
                    continue
                if (track_a.id, track_b.id) in positive_set:
                    continue

                bpm_delta = abs((track_a.bpm or 130) - (track_b.bpm or 130))
                key_dist = camelot_distance(
                    track_a.camelot_code or "", track_b.camelot_code or ""
                )

                # Hard negative: incompatible BPM or key
                is_bad = bpm_delta > 15 or key_dist > 3

                if is_bad:
                    negatives.append({
                        "track_a_id": track_a.id,
                        "track_b_id": track_b.id,
                        "label": 0,
                        "reason": f"bpm_delta={bpm_delta:.1f}, key_dist={key_dist}",
                    })
                    count += 1
                    if count >= args.ratio:
                        break

            if count < args.ratio:
                skipped += 1

    finally:
        db.close()

    with open(args.output, "w") as f:
        json.dump(negatives, f, indent=2)

    log.info(f"\n{'='*50}")
    log.info(f"Negative pairs generated: {len(negatives)}")
    log.info(f"Tracks with no hard negatives found: {skipped}")
    log.info(f"Saved to: {args.output}")
    log.info(f"\nNext step:\n  python train_transition_model.py --negatives-file {args.output}")


if __name__ == "__main__":
    main()
