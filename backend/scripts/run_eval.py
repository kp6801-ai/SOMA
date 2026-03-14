"""
Phase 5.2-5.3: Evaluation runner.
For each evaluation pair, run score_transition() and compare to human_score.
Output precision, recall, MAE vs human judgment.
Gate: fail if MAE increases > threshold.
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import psycopg2
from database import SessionLocal
from transitions import score_transition

# Map human scores to numeric values
HUMAN_SCORE_MAP = {
    "bad": 0.0,
    "usable": 0.5,
    "strong": 0.8,
    "excellent": 1.0,
}

# Map engine score ranges to categories
def engine_to_category(score: float) -> str:
    if score >= 0.90:
        return "excellent"
    elif score >= 0.75:
        return "strong"
    elif score >= 0.50:
        return "usable"
    return "bad"


def run_eval(fail_threshold: float = None):
    conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://localhost/soma"))
    cur = conn.cursor()

    cur.execute("""
        SELECT id, track_a_id, track_b_id, human_score, transition_type
        FROM evaluation_pairs
        WHERE human_score IS NOT NULL
    """)
    pairs = cur.fetchall()
    conn.close()

    if not pairs:
        print("No judged evaluation pairs found.")
        print("Run create_eval_set.py first, then manually judge pairs.")
        return

    db = SessionLocal()

    results = []
    errors = []
    category_matrix = {"bad": {"bad": 0, "usable": 0, "strong": 0, "excellent": 0},
                        "usable": {"bad": 0, "usable": 0, "strong": 0, "excellent": 0},
                        "strong": {"bad": 0, "usable": 0, "strong": 0, "excellent": 0},
                        "excellent": {"bad": 0, "usable": 0, "strong": 0, "excellent": 0}}

    for pair_id, track_a_id, track_b_id, human_score, transition_type in pairs:
        human_numeric = HUMAN_SCORE_MAP.get(human_score)
        if human_numeric is None:
            errors.append(f"Pair {pair_id}: invalid human_score '{human_score}'")
            continue

        result = score_transition(db, track_a_id, track_b_id)
        if "error" in result:
            errors.append(f"Pair {pair_id}: {result['error']}")
            continue

        engine_score = result["overall_score"]
        engine_cat = engine_to_category(engine_score)
        ae = abs(engine_score - human_numeric)

        results.append({
            "pair_id": pair_id,
            "track_a": track_a_id,
            "track_b": track_b_id,
            "human": human_score,
            "human_numeric": human_numeric,
            "engine_score": engine_score,
            "engine_category": engine_cat,
            "absolute_error": ae,
            "transition_type": transition_type,
        })

        category_matrix[human_score][engine_cat] += 1

    db.close()

    if not results:
        print("No valid results to evaluate.")
        return

    # Compute metrics
    total = len(results)
    mae = sum(r["absolute_error"] for r in results) / total
    exact_match = sum(1 for r in results if r["human"] == r["engine_category"])
    precision = exact_match / total

    # Within-one accuracy (human and engine categories are adjacent or same)
    categories = ["bad", "usable", "strong", "excellent"]
    within_one = sum(1 for r in results
                     if abs(categories.index(r["human"]) - categories.index(r["engine_category"])) <= 1)
    within_one_pct = within_one / total

    # Report
    print("=" * 60)
    print("SOMA Evaluation Report")
    print("=" * 60)
    print(f"\nPairs evaluated: {total}")
    print(f"Errors/skipped:  {len(errors)}")
    print(f"\nMean Absolute Error (MAE): {mae:.4f}")
    print(f"Exact category match:      {precision:.1%} ({exact_match}/{total})")
    print(f"Within-one accuracy:       {within_one_pct:.1%} ({within_one}/{total})")

    # Per transition type
    print(f"\n{'Transition Type':<20} {'Count':>6} {'MAE':>8}")
    print("-" * 36)
    type_groups = {}
    for r in results:
        tt = r["transition_type"] or "unknown"
        if tt not in type_groups:
            type_groups[tt] = []
        type_groups[tt].append(r["absolute_error"])
    for tt, aes in sorted(type_groups.items()):
        print(f"{tt:<20} {len(aes):>6} {sum(aes)/len(aes):>8.4f}")

    # Confusion matrix
    print(f"\nConfusion Matrix (rows=human, cols=engine):")
    print(f"{'':>12} {'bad':>8} {'usable':>8} {'strong':>8} {'excellent':>10}")
    for human_cat in categories:
        row = category_matrix[human_cat]
        print(f"{human_cat:>12} {row['bad']:>8} {row['usable']:>8} {row['strong']:>8} {row['excellent']:>10}")

    # Worst predictions
    print(f"\nWorst 5 predictions:")
    worst = sorted(results, key=lambda r: r["absolute_error"], reverse=True)[:5]
    for r in worst:
        print(f"  Pair {r['pair_id']}: human={r['human']}, engine={r['engine_category']} "
              f"(score={r['engine_score']:.3f}, error={r['absolute_error']:.3f})")

    if errors:
        print(f"\nErrors:")
        for e in errors[:10]:
            print(f"  {e}")

    # Gate check (Phase 5.3)
    if fail_threshold is not None:
        if mae > fail_threshold:
            print(f"\n EVAL GATE FAILED: MAE {mae:.4f} > threshold {fail_threshold}")
            sys.exit(1)
        else:
            print(f"\n EVAL GATE PASSED: MAE {mae:.4f} <= threshold {fail_threshold}")

    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fail-threshold", type=float, default=None,
                        help="Fail if MAE exceeds this value")
    args = parser.parse_args()
    run_eval(fail_threshold=args.fail_threshold)
