"""Builds data/label_review.xlsx: each update's text next to its draft labels, for human review."""
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from pathlib import Path
D = Path(__file__).resolve().parent.parent / "data"
gt = pd.read_csv(D / "ground_truth.csv")
upd = pd.read_excel(D / "releaseops_dataset.xlsx", sheet_name="Weekly_Updates")[["update_id", "reported_rag", "update_text"]]
df = gt.merge(upd, on="update_id")[["update_id", "release_id", "week", "reported_rag", "update_text",
     "gt_inconsistent", "gt_has_risk", "gt_risk_categories", "gt_dependency_functions", "label_note"]]
df["agree"] = ""
for c in ["new_inconsistent", "new_has_risk", "new_risk_categories", "new_dependency_functions", "your_reason"]:
    df[c] = ""
rules = [
 ["How to review (about 45 min)"],
 ["1. Read update_text and reported_rag. Judge the draft labels (grey columns) using the definitions below."],
 ["2. agree = Y if all labels are right. If not, set agree = N and fill ONLY the new_ columns you'd change, plus your_reason."],
 ["3. Save, then run:  python src/apply_review.py   (writes ground_truth.csv, marks every row verified)."],
 [""],
 ["Definitions (same as the AI prompt, so you're both judged on the same task)"],
 ["inconsistent = 1: reported RAG doesn't match the text. Usually Green while the text shows a slip, missed approval, quality below target, open P1s, failing tests or a stalled dependency. Also Amber/Red when the text says all is on track."],
 ["has_risk = 1: a CURRENT, UNRESOLVED threat to schedule, quality, security or commercial readiness. Resolved problems and negations ('no escalations') are NOT risks. An on-schedule dependency alone is NOT a risk."],
 ["risk categories: Schedule; Quality; Security; Commercial; Dependency (separate with ;)"],
 ["dependency functions: Legal; Pricing; Finance; Marketing; Security; Platform Eng; QA; Support; Docs; Partner. A team or party OUTSIDE the release's own engineering team that the release needs something from (deliverable, sign-off, approval, decision). Teams that are merely informed don't count."],
 [""],
 ["Not labelled here: missing, late, stale. Those are rule checks, not judgement."],
 ["Judgement calls I made are in label_note (e.g. U026: Support only informed, so not a dependency; U030: customer-impacting hotfix counted as Quality risk). Overrule me if you disagree; just write why."],
]
p = D / "label_review.xlsx"
with pd.ExcelWriter(p, engine="openpyxl") as xw:
    pd.DataFrame(rules).to_excel(xw, sheet_name="How_to_review", index=False, header=False)
    df.to_excel(xw, sheet_name="Review", index=False)
wb = load_workbook(p)
ws = wb["Review"]
grey, yel, hdr = PatternFill("solid", fgColor="EDEDED"), PatternFill("solid", fgColor="FFF2CC"), PatternFill("solid", fgColor="1F3864")
widths = {"A":8,"B":7,"C":6,"D":9,"E":70,"F":10,"G":9,"H":20,"I":20,"J":40,"K":8,"L":12,"M":11,"N":20,"O":20,"P":35}
for col, w in widths.items(): ws.column_dimensions[col].width = w
for c in ws[1]:
    c.font = Font(name="Arial", size=10, bold=True, color="FFFFFF"); c.fill = hdr
    c.alignment = Alignment(wrap_text=True, vertical="top")
for row in ws.iter_rows(min_row=2):
    for c in row:
        c.font = Font(name="Arial", size=10); c.alignment = Alignment(wrap_text=True, vertical="top")
        if c.column_letter in "FGHIJ": c.fill = grey
        if c.column_letter in "KLMNOP": c.fill = yel
ws.freeze_panes = "F2"
n = ws.max_row
dv = DataValidation(type="list", formula1='"Y,N"', allow_blank=True); ws.add_data_validation(dv); dv.add(f"K2:K{n}")
dv2 = DataValidation(type="list", formula1='"0,1"', allow_blank=True); ws.add_data_validation(dv2); dv2.add(f"L2:M{n}")
h = wb["How_to_review"]; h.column_dimensions["A"].width = 160
for r in h.iter_rows():
    for c in r: c.font = Font(name="Arial", size=10, bold=c.row in (1, 6)); c.alignment = Alignment(wrap_text=True)
wb.active = 0
wb.save(p)
print("rows:", len(df))
