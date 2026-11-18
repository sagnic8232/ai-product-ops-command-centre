"""Scores the LLM flags and the keyword baseline against data/ground_truth.csv.

Run after rules.py and llm_flags.py parse:   python src/eval.py
Writes outputs/eval_results.csv, outputs/eval_errors.csv and outputs/eval_results.md (paste into README).
"""
import pandas as pd
from common import DATA, OUT


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f = 2 * p * r / (p + r) if p == p and r == r and p + r else float("nan")
    return p, r, f


def binary(y, yhat):
    tp = int((y & yhat).sum()); fp = int((~y & yhat).sum()); fn = int((y & ~yhat).sum())
    return (tp, fp, fn) + prf(tp, fp, fn)


def sets(col):
    return col.fillna("").apply(lambda s: {x for x in s.split(";") if x})


def main():
    gt = pd.read_csv(DATA / "ground_truth.csv")
    if (gt["label_status"] != "verified").any():
        print("WARNING: some ground-truth labels are still 'DRAFT - verify'. Review them and set label_status = verified "
              "BEFORE quoting any number.\n")
    base = pd.read_csv(OUT / "baseline_flags.csv")
    llm = pd.read_csv(OUT / "llm_flags.csv")
    df = gt.merge(base, on="update_id", how="left").merge(llm, on="update_id", how="left")
    n_missing = df["llm_inconsistent"].isna().sum()
    if n_missing:
        print(f"WARNING: {n_missing} updates have no LLM output; they count as 'not flagged'.")
    for c in ["llm_inconsistent", "llm_has_risk"]:
        df[c] = df[c].fillna(False).astype(bool)
    y_inc, y_risk = df["gt_inconsistent"].astype(bool), df["gt_has_risk"].astype(bool)

    res = []
    for name, y, b, l in [("RAG-vs-text inconsistency", y_inc, df["base_inconsistent"].astype(bool), df["llm_inconsistent"]),
                          ("Has unresolved risk", y_risk, df["base_has_risk"].astype(bool), df["llm_has_risk"])]:
        for method, yhat in [("Keyword baseline", b), ("LLM", l)]:
            tp, fp, fn, p, r, f = binary(y, yhat)
            res.append({"task": name, "method": method, "positives_in_gt": int(y.sum()), "TP": tp, "FP": fp, "FN": fn,
                        "precision": p, "recall": r, "f1": f})
    # dependencies: micro-averaged over (update, function) pairs; baseline has no dependency extraction
    g, h = sets(df["gt_dependency_functions"]), sets(df["llm_dependency_functions"])
    tp = sum(len(a & b) for a, b in zip(g, h)); fp = sum(len(b - a) for a, b in zip(g, h)); fn = sum(len(a - b) for a, b in zip(g, h))
    p, r, f = prf(tp, fp, fn)
    res.append({"task": "Dependency functions (micro)", "method": "LLM", "positives_in_gt": sum(len(a) for a in g),
                "TP": tp, "FP": fp, "FN": fn, "precision": p, "recall": r, "f1": f})
    out = pd.DataFrame(res)
    out.to_csv(OUT / "eval_results.csv", index=False)

    err = []
    for r_ in df.itertuples():
        for task, y_, yh in [("inconsistency", r_.gt_inconsistent, r_.llm_inconsistent), ("risk", r_.gt_has_risk, r_.llm_has_risk)]:
            if bool(y_) != bool(yh):
                err.append({"update_id": r_.update_id, "task": task, "error": "FN" if y_ else "FP", "label_note": r_.label_note})
    pd.DataFrame(err).to_csv(OUT / "eval_errors.csv", index=False)

    fmt = out.copy()
    for c in ["precision", "recall", "f1"]:
        fmt[c] = fmt[c].map(lambda v: "n/a" if v != v else f"{v:.0%}")
    md = ["| Task | Method | GT positives | TP | FP | FN | Precision | Recall | F1 |", "|---|---|---|---|---|---|---|---|---|"]
    md += [f"| {r.task} | {r.method} | {r.positives_in_gt} | {r.TP} | {r.FP} | {r.FN} | {r.precision} | {r.recall} | {r.f1} |" for r in fmt.itertuples()]
    md.append(f"\nn = {len(df)} labelled updates. Small sample: one error moves precision/recall by roughly 10-20 points.")
    (OUT / "eval_results.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print(f"\nErrors listed in {OUT / 'eval_errors.csv'}")


if __name__ == "__main__":
    main()
