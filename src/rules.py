"""Deterministic checks (no AI). Use these outputs to cross-check your Excel/Power Query build.

Writes to outputs/:
  hygiene.csv            one row per expected update: missing / late / stale
  readiness.csv          readiness % per release against its required gates
  milestone_slips.csv    milestones whose forecast/actual is later than planned, or blocked
  overdue_actions.csv    open action items past due as of the report date
  data_inconsistency.csv latest reported RAG = Green while a gate is blocked or an open milestone has slipped
  baseline_flags.csv     keyword baseline used in the eval (the thing the LLM must beat)

Run:  python src/rules.py
"""
import difflib
import re
import pandas as pd
from common import load, OUT, AS_OF

STALE_THRESHOLD = 0.90   # text similarity vs previous submitted update of the same release
# Word-start matching (so "late" does not match "latency"/"related"). Stems like "block" match "blocked"/"blocker".
BASELINE_KEYWORDS = [r"\bblock", r"\bdelay", r"\bslip", r"\brisk", r"\bissue", r"\bpending", r"\bfail",
                     r"\bwaiting", r"\bbehind", r"\blate\b", r"\blater\b", r"\bregression", r"\bescalat",
                     r"\bconcern", r"\bstuck", r"\bat risk", r"\bmiss"]


def hygiene(rel, cal, upd):
    # An update is expected while the release is active, and for shipped releases up to the week after GA.
    exp = rel[["release_id", "tpm", "release_status", "forecast_ga"]].merge(cal, how="cross")
    exp = exp[(exp["release_status"] == "Active") | (exp["week_ending"] <= exp["forecast_ga"] + pd.Timedelta(days=7))]
    exp = exp.drop(columns=["release_status", "forecast_ga"])
    df = exp.merge(upd, on=["release_id", "week"], how="left")
    df["is_missing"] = df["update_id"].isna()
    df["is_late"] = (~df["is_missing"]) & (df["submitted_at"] > df["submission_deadline"])
    df["hours_late"] = ((df["submitted_at"] - df["submission_deadline"]).dt.total_seconds() / 3600).where(df["is_late"]).round(1)
    df = df.sort_values(["release_id", "week"])
    sims = []
    for rid, g in df.groupby("release_id", sort=False):
        prev = None
        for _, r in g.iterrows():
            if pd.isna(r["update_text"]):
                sims.append(None); continue
            sims.append(round(difflib.SequenceMatcher(None, prev, r["update_text"]).ratio(), 3) if prev else None)
            prev = r["update_text"]
    df["similarity_to_prev"] = sims
    df["is_stale"] = df["similarity_to_prev"].fillna(0) >= STALE_THRESHOLD
    return df[["release_id", "week", "tpm", "update_id", "submission_deadline", "submitted_at",
               "is_missing", "is_late", "hours_late", "similarity_to_prev", "is_stale"]]


def readiness(rel, ms):
    g = ms.groupby("release_id").agg(gates_required=("milestone_id", "count"),
                                     gates_done=("status", lambda s: (s == "Done").sum()),
                                     gates_blocked=("status", lambda s: (s == "Blocked").sum()))
    g["readiness_pct"] = (g["gates_done"] / g["gates_required"]).round(3)
    open_due = ms[(ms["status"] != "Done") & (ms["planned_date"] <= AS_OF)]
    g["gates_overdue"] = open_due.groupby("release_id").size().reindex(g.index).fillna(0).astype(int)
    return rel[["release_id", "product", "version", "release_type", "release_status", "official_rag",
                "planned_ga", "forecast_ga"]].merge(g.reset_index(), on="release_id")


def slips(ms):
    ms = ms.copy()
    end = ms["actual_date"].fillna(ms["forecast_date"])
    ms["slip_days"] = (end - ms["planned_date"]).dt.days
    out = ms[(ms["slip_days"] > 0) | (ms["status"] == "Blocked")]
    return out[["release_id", "milestone", "owner_function", "planned_date", "forecast_date",
                "actual_date", "status", "slip_days", "note"]]


def overdue(act):
    o = act[(act["status"] == "Open") & (act["due_on"] < AS_OF)].copy()
    o["days_overdue"] = (AS_OF - o["due_on"]).dt.days
    return o.sort_values("days_overdue", ascending=False)


def data_inconsistency(rel, sl, upd):
    """Latest TPM-reported RAG is Green while the milestone data shows a blocked gate or a slip
    that is still open (not yet Done). Text-vs-RAG inconsistency is the LLM's job, not this rule's."""
    latest = upd.sort_values("week").groupby("release_id").tail(1)[["release_id", "week", "reported_rag"]]
    open_sl = sl[sl["status"] != "Done"]
    bad = open_sl.groupby("release_id").agg(open_slips_or_blocks=("milestone", lambda s: "; ".join(s)),
                                            max_slip_days=("slip_days", "max"))
    df = rel[["release_id", "product", "release_status"]].merge(latest, on="release_id").merge(bad.reset_index(), on="release_id")
    return df[(df["reported_rag"] == "Green") & (df["release_status"] != "Shipped")]


def baseline(upd):
    t = upd["update_text"].str.lower()
    hit = t.apply(lambda s: [k.replace("\\b", "") for k in BASELINE_KEYWORDS if re.search(k, s)])
    b = upd[["update_id", "release_id", "week", "reported_rag"]].copy()
    b["keywords_hit"] = hit.apply(";".join)
    b["base_has_risk"] = (hit.str.len() > 0) | upd["reported_rag"].isin(["Amber", "Red"])
    b["base_inconsistent"] = (hit.str.len() > 0) & (upd["reported_rag"] == "Green")
    return b


def main():
    rel, ms, upd = load("Releases"), load("Milestones"), load("Weekly_Updates")
    cal, act = load("Reporting_Calendar"), load("Action_Items")
    h = hygiene(rel, cal, upd); h.to_csv(OUT / "hygiene.csv", index=False)
    r = readiness(rel, ms); r.to_csv(OUT / "readiness.csv", index=False)
    s = slips(ms); s.to_csv(OUT / "milestone_slips.csv", index=False)
    o = overdue(act); o.to_csv(OUT / "overdue_actions.csv", index=False)
    d = data_inconsistency(rel, s, upd); d.to_csv(OUT / "data_inconsistency.csv", index=False)
    b = baseline(upd); b.to_csv(OUT / "baseline_flags.csv", index=False)

    print(f"Expected updates: {len(h)} | missing: {h.is_missing.sum()} | late: {h.is_late.sum()} | stale: {h.is_stale.sum()}")
    print("Missing:", ", ".join(h[h.is_missing].release_id + "-" + h[h.is_missing].week))
    print("Late:   ", ", ".join(h[h.is_late].release_id + "-" + h[h.is_late].week))
    print("Stale:  ", ", ".join(h[h.is_stale].release_id + "-" + h[h.is_stale].week))
    print(f"Slipped/blocked milestones: {len(s)} | overdue actions: {len(o)} | Green-but-slipping releases: {len(d)}")
    print(r[["release_id", "release_type", "readiness_pct", "gates_blocked", "gates_overdue"]].to_string(index=False))


if __name__ == "__main__":
    main()
