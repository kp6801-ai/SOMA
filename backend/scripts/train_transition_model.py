"""
train_transition_model.py — Train the LightGBM DJ transition quality model.

Data sources (label=1 positive):
  - transition_scores table (times_played >= 2, confidence >= 0.5)
  - evaluation_pairs table (human_score in 'strong', 'excellent')

Data sources (label=0 negative):
  - negative_pairs.json from generate_negatives.py
  - evaluation_pairs with human_score='bad'

Usage:
  python train_transition_model.py
  python train_transition_model.py --min-plays 1 --negatives-file ./negative_pairs.json
  python train_transition_model.py --db-url postgresql://localhost/soma
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal, Track, TransitionScore, EvaluationPair
from transition_model import TransitionModel, DEFAULT_MODEL_PATH


def load_track(db, track_id: int, cache: dict) -> Track | None:
    if track_id in cache:
        return cache[track_id]
    t = db.query(Track).filter(Track.id == track_id).first()
    if t:
        db.expunge(t)
        cache[track_id] = t
    return t


def build_dataset(db, min_plays: int, negatives_file: str | None) -> list[dict]:
    pairs = []
    track_cache = {}

    # ── Positive pairs from transition_scores ──
    positive_ts = db.query(TransitionScore).filter(
        TransitionScore.times_played >= min_plays,
        TransitionScore.confidence >= 0.5,
        TransitionScore.track_a_id.isnot(None),
        TransitionScore.track_b_id.isnot(None),
    ).all()

    log.info(f"transition_scores positives: {len(positive_ts)}")
    for ts in positive_ts:
        ta = load_track(db, ts.track_a_id, track_cache)
        tb = load_track(db, ts.track_b_id, track_cache)
        if ta and tb:
            pairs.append({"track_a": ta, "track_b": tb, "label": 1, "source": "transition_scores"})

    # ── Positive/negative pairs from evaluation_pairs ──
    eval_pairs = db.query(EvaluationPair).all()
    log.info(f"evaluation_pairs: {len(eval_pairs)}")
    for ep in eval_pairs:
        ta = load_track(db, ep.track_a_id, track_cache)
        tb = load_track(db, ep.track_b_id, track_cache)
        if not ta or not tb:
            continue
        if ep.human_score in ("strong", "excellent"):
            pairs.append({"track_a": ta, "track_b": tb, "label": 1, "source": "human_eval"})
        elif ep.human_score == "bad":
            pairs.append({"track_a": ta, "track_b": tb, "label": 0, "source": "human_eval"})

    # ── Negative pairs from generate_negatives.py ──
    neg_path = negatives_file or str(Path(__file__).parent.parent / "negative_pairs.json")
    if Path(neg_path).exists():
        with open(neg_path) as f:
            neg_data = json.load(f)
        log.info(f"File negatives: {len(neg_data)}")
        for n in neg_data:
            ta = load_track(db, n["track_a_id"], track_cache)
            tb = load_track(db, n["track_b_id"], track_cache)
            if ta and tb:
                pairs.append({"track_a": ta, "track_b": tb, "label": 0, "source": "generated_negatives"})
    else:
        log.warning(f"No negatives file at {neg_path} — run generate_negatives.py first")
        # Auto-generate simple negatives from existing positives
        log.info("Auto-generating random negatives from positive pairs...")
        import random
        all_tracks = db.query(Track).filter(Track.bpm.isnot(None)).all()
        for t in all_tracks:
            db.expunge(t)
        for t in all_tracks:
            track_cache[t.id] = t

        positive_a_ids = {p["track_a"].id for p in pairs if p["label"] == 1}
        positive_set = {(p["track_a"].id, p["track_b"].id) for p in pairs if p["label"] == 1}

        random.seed(42)
        neg_count = 0
        target = len([p for p in pairs if p["label"] == 1]) * 2

        for ta in list(positive_a_ids)[:500]:
            track_a = track_cache.get(ta)
            if not track_a:
                continue
            shuffled = random.sample(all_tracks, min(20, len(all_tracks)))
            for tb in shuffled:
                if tb.id == ta or (ta, tb.id) in positive_set:
                    continue
                bpm_delta = abs((track_a.bpm or 130) - (tb.bpm or 130))
                if bpm_delta > 15:
                    pairs.append({"track_a": track_a, "track_b": tb, "label": 0, "source": "auto_neg"})
                    neg_count += 1
                    if neg_count >= target:
                        break
            if neg_count >= target:
                break
        log.info(f"Auto-generated {neg_count} negatives")

    return pairs


def main():
    parser = argparse.ArgumentParser(description="Train LightGBM transition quality model")
    parser.add_argument("--min-plays", type=int, default=2,
                        help="Min times_played in transition_scores (default 2)")
    parser.add_argument("--negatives-file", default=None,
                        help="Path to negative_pairs.json from generate_negatives.py")
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH,
                        help=f"Where to save model (default {DEFAULT_MODEL_PATH})")
    parser.add_argument("--db-url", default=None,
                        help="Override DATABASE_URL env var")
    args = parser.parse_args()

    if args.db_url:
        os.environ["DATABASE_URL"] = args.db_url

    db = SessionLocal()
    try:
        pairs = build_dataset(db, args.min_plays, args.negatives_file)
    finally:
        db.close()

    n_pos = sum(1 for p in pairs if p["label"] == 1)
    n_neg = sum(1 for p in pairs if p["label"] == 0)
    log.info(f"\nDataset: {len(pairs)} pairs | {n_pos} positive | {n_neg} negative")

    if n_pos == 0:
        log.error(
            "No positive pairs found. Make sure you have:\n"
            "  1. Tracks in the DB\n"
            "  2. transition_scores rows (run build_training_pairs.py first)\n"
            "  or evaluation_pairs with human_score='strong'/'excellent'"
        )
        sys.exit(1)

    if n_neg == 0:
        log.error("No negative pairs found. Run generate_negatives.py first.")
        sys.exit(1)

    model = TransitionModel()
    metrics = model.train(pairs)

    if "error" in metrics:
        log.error(f"Training failed: {metrics['error']}")
        sys.exit(1)

    log.info(f"\n{'='*50}")
    log.info(f"Training complete!")
    log.info(f"  Train samples:  {metrics['n_train']}")
    log.info(f"  Val samples:    {metrics['n_val']}")
    log.info(f"  Val AUC:        {metrics['val_auc']:.4f}")
    log.info(f"  Val Accuracy:   {metrics['val_accuracy']:.4f}")
    log.info(f"\nTop features:")
    for name, importance in metrics.get("top_features", []):
        log.info(f"  {name:<28} {importance:.0f}")

    model.save(args.model_path)
    log.info(f"\nModel saved to: {args.model_path}")
    log.info("The model will be auto-loaded on next backend restart.")


if __name__ == "__main__":
    main()
