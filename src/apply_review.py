"""Applies your decisions from data/label_review.xlsx to data/ground_truth.csv.

Run:  python src/apply_review.py
- Every row must have agree = Y or N (it stops and lists the blanks otherwise).
- For N rows, any filled new_ column replaces the draft value; your_reason goes into label_note.
- All rows are then marked label_status = verified, and a change log is written to data/label_changes.csv.
"""
import sys
import pandas as pd
from common import DATA, FUNCTIONS, RISK_CATEGORIES

rv = pd.read_excel(DATA / "label_review.xlsx", sheet_name="Review", dtype=str).fillna("")
gt = pd.read_csv(DATA / "ground_truth.csv", dtype=str).fillna("")
blank = rv[~rv["agree"].str.strip().str.upper().isin(["Y", "N"])]["update_id"].tolist()
if blank:
    sys.exit(f"{len(blank)} rows have no Y/N in 'agree': {', '.join(blank)}")

def check_list(val, allowed, uid, col):
    items = [x.strip() for x in val.split(";") if x.strip()]
    bad = [x for x in items if x not in allowed]
    if bad:
        sys.exit(f"{uid} {col}: unknown value(s) {bad}. Allowed: {allowed}")
    return ";".join(items)

changes = []
gt = gt.set_index("update_id")
for r in rv.itertuples():
    if r.agree.strip().upper() != "N":
        continue
    for new, old, kind in [("new_inconsistent", "gt_inconsistent", "01"), ("new_has_risk", "gt_has_risk", "01"),
                           ("new_risk_categories", "gt_risk_categories", RISK_CATEGORIES),
                           ("new_dependency_functions", "gt_dependency_functions", FUNCTIONS)]:
        v = str(getattr(r, new)).strip()
        if not v:
            continue
        if v.lower() in ("none", "-"):
            v = ""
        elif kind == "01":
            v = v.split(".")[0]
            if v not in ("0", "1"):
                sys.exit(f"{r.update_id} {new}: use 0 or 1, got '{v}'")
        else:
            v = check_list(v, kind, r.update_id, new)
        if v != gt.at[r.update_id, old]:
            changes.append({"update_id": r.update_id, "field": old, "draft": gt.at[r.update_id, old], "yours": v, "reason": r.your_reason})
            gt.at[r.update_id, old] = v
    if r.your_reason.strip():
        gt.at[r.update_id, "label_note"] = f"REVIEWED: {r.your_reason.strip()}"
# consistency: no risk -> no risk categories
mask = gt["gt_has_risk"] == "0"
gt.loc[mask, "gt_risk_categories"] = ""
gt["label_status"] = "verified"
gt.reset_index().to_csv(DATA / "ground_truth.csv", index=False)
pd.DataFrame(changes).to_csv(DATA / "label_changes.csv", index=False)
print(f"Verified {len(gt)} rows | changed {len(changes)} label values (log: data/label_changes.csv)")
