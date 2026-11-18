"""Imports TPM status updates from a Microsoft Forms (or Google Forms) response export.

Microsoft Forms: form -> Responses -> "Open in Excel" -> save the .xlsx -> run:
    python src/ingest_form.py --file "path/to/Weekly TPM Status Update.xlsx"
Google Forms: Responses -> Download (.csv) -> same command with the .csv.

Expected form questions (see FORM_SPEC.md): Release, Reporting week, Your name, RAG status,
% complete, Status update. Matching is by keywords in the column header, so small wording
differences are fine.

What it does:
- validates each response (known release, week like W5, RAG in Green/Amber/Red, % 0-100, text present)
- rejected rows -> outputs/ingest_rejected.csv (with the reason); nothing is silently dropped
- a resubmission for the same release + week keeps the latest one (logged)
- new weeks are added to the reporting calendar (deadline = Thursday 18:00 before week ending)
- writes data/form_updates.csv, which every other script reads together with the workbook
"""
import argparse, re, sys
from datetime import timedelta
import pandas as pd
from common import FORM_UPDATES, CALENDAR_EXTRA, OUT, WORKBOOK, week_num

VALID_RAG = {"green": "Green", "amber": "Amber", "red": "Red"}


def find_col(cols, *, any_of, exclude=()):
    for c in cols:
        lc = str(c).lower()
        if any(k in lc for k in any_of) and not any(x in lc for x in exclude):
            return c
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--dry-run", action="store_true", help="validate and report, write nothing")
    a = ap.parse_args()

    raw = pd.read_csv(a.file) if a.file.lower().endswith(".csv") else pd.read_excel(a.file)
    cols = list(raw.columns)
    m = {
        "release": find_col(cols, any_of=["release"]),
        "week": find_col(cols, any_of=["reporting week", "week"]),
        "name": find_col(cols, any_of=["your name"]) or find_col(cols, any_of=["name"], exclude=["file"]),
        "rag": find_col(cols, any_of=["rag"]),
        "pct": find_col(cols, any_of=["% complete", "percent"]),
        "ts": find_col(cols, any_of=["completion time", "timestamp"]),
        "text": find_col(cols, any_of=["status update", "update"], exclude=["time"]),
    }
    missing = [k for k, v in m.items() if v is None]
    if missing:
        sys.exit(f"Could not find columns for: {missing}. Headers found: {cols}")

    rel = pd.read_excel(WORKBOOK, sheet_name="Releases")
    known = set(rel["release_id"])
    good, bad = [], []
    for i, r in raw.iterrows():
        rid = re.search(r"R\d{2}", str(r[m["release"]]))
        rid = rid.group(0) if rid else None
        wk = re.search(r"W\d+", str(r[m["week"]]).upper())
        wk = wk.group(0) if wk else None
        rag = VALID_RAG.get(str(r[m["rag"]]).strip().lower())
        pct = pd.to_numeric(r[m["pct"]], errors="coerce")
        ts = pd.to_datetime(r[m["ts"]], errors="coerce", dayfirst=False)
        text = str(r[m["text"]]).strip() if pd.notna(r[m["text"]]) else ""
        reasons = []
        if rid not in known: reasons.append(f"unknown release '{r[m['release']]}'")
        if not wk: reasons.append(f"bad week '{r[m['week']]}'")
        if not rag: reasons.append(f"bad RAG '{r[m['rag']]}'")
        if pd.isna(pct) or not 0 <= pct <= 100: reasons.append(f"bad % complete '{r[m['pct']]}'")
        if pd.isna(ts): reasons.append("no timestamp")
        if len(text) < 15: reasons.append("update text missing or too short")
        if reasons:
            bad.append({"form_row": i + 2, "reasons": "; ".join(reasons), **{k: r[v] for k, v in m.items()}})
            continue
        good.append({"release_id": rid, "week": wk, "submitted_by": str(r[m["name"]]).strip(), "role": "TPM",
                     "submitted_at": ts, "reported_rag": rag, "pct_complete": pct / 100, "update_text": text})

    new = pd.DataFrame(good)
    prev = pd.read_csv(FORM_UPDATES, parse_dates=["submitted_at"]) if FORM_UPDATES.exists() else pd.DataFrame()
    allf = pd.concat([prev, new], ignore_index=True) if len(new) else prev
    replaced = 0
    if len(allf):
        allf = allf.sort_values("submitted_at")
        dup = allf.duplicated(["release_id", "week"], keep="last")
        replaced = int(dup.sum())
        allf = allf[~dup]
        if "update_id" not in allf or allf["update_id"].isna().any():
            ids = allf.get("update_id", pd.Series([None] * len(allf), index=allf.index))
            used = {int(x[1:]) for x in ids.dropna()}
            nxt = max(used, default=0)
            for idx in allf.index:
                if pd.isna(ids.get(idx)):
                    nxt += 1; allf.loc[idx, "update_id"] = f"F{nxt:03d}"
        allf = allf[["update_id", "release_id", "week", "submitted_by", "role", "submitted_at",
                     "reported_rag", "pct_complete", "update_text"]].sort_values(["week", "release_id"], key=lambda s: s.map(week_num) if s.name == "week" else s)

    seed_weeks = set(pd.read_excel(WORKBOOK, sheet_name="Weekly_Updates")["week"])
    clash = new[new["week"].isin(seed_weeks)] if len(new) else new
    # new weeks -> calendar
    cal = pd.read_excel(WORKBOOK, sheet_name="Reporting_Calendar")
    extra = pd.read_csv(CALENDAR_EXTRA, parse_dates=["week_ending", "submission_deadline"]) if CALENDAR_EXTRA.exists() else pd.DataFrame(columns=cal.columns)
    calall = pd.concat([cal, extra], ignore_index=True)
    last = calall.loc[calall["week"].map(week_num).idxmax()]
    add = []
    for wk in sorted(set(new["week"]) if len(new) else set(), key=week_num):
        if wk in set(calall["week"]):
            continue
        we = pd.Timestamp(last["week_ending"]) + timedelta(days=7 * (week_num(wk) - week_num(last["week"])))
        add.append({"week": wk, "week_ending": we, "submission_deadline": (we - timedelta(days=1)).replace(hour=18, minute=0)})
    # fill any gap weeks too, so "missing" works for skipped weeks
    if add:
        top = max(week_num(x["week"]) for x in add)
        have = set(calall["week"]) | {x["week"] for x in add}
        for n in range(week_num(last["week"]) + 1, top):
            if f"W{n}" not in have:
                we = pd.Timestamp(last["week_ending"]) + timedelta(days=7 * (n - week_num(last["week"])))
                add.append({"week": f"W{n}", "week_ending": we, "submission_deadline": (we - timedelta(days=1)).replace(hour=18, minute=0)})

    print(f"Form rows: {len(raw)} | accepted: {len(new)} | rejected: {len(bad)} | resubmissions replaced: {replaced}")
    if len(clash):
        print(f"NOTE: {len(clash)} response(s) are for weeks already in the seed data; they replace the seed update for that release+week.")
    if add:
        print("New reporting weeks added:", ", ".join(x["week"] for x in add))
    if bad:
        print("Rejected rows (see outputs/ingest_rejected.csv):")
        for b in bad:
            print(f"  row {b['form_row']}: {b['reasons']}")
    if a.dry_run:
        print("Dry run: nothing written."); return
    pd.DataFrame(bad).to_csv(OUT / "ingest_rejected.csv", index=False)
    if len(allf):
        allf.to_csv(FORM_UPDATES, index=False)
    if add:
        pd.concat([extra, pd.DataFrame(add)], ignore_index=True).to_csv(CALENDAR_EXTRA, index=False)
    print(f"Wrote {FORM_UPDATES.name} ({len(allf)} form updates in total).")


if __name__ == "__main__":
    main()
