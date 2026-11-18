"""Builds the weekly decision summary prompt from rule outputs + grounded LLM flags.

Claude Pro:  python src/weekly_summary.py --week W4      -> prompts/summary_W4.txt
             paste into a new claude.ai chat; save the reply as outputs/summary_W4.md
API:         python src/weekly_summary.py --week W4 --api --model claude-sonnet-5-5

Run rules.py and llm_flags.py parse first.
"""
import argparse, json
import pandas as pd
from common import load, OUT, PROMPTS, AS_OF

TEMPLATE = """You are writing the weekly release status summary for product leadership. Use ONLY the facts in the
JSON below. Do not add facts, dates or numbers that are not in it. If something is unknown, say so.

Format (markdown, max ~300 words):
## Weekly release summary - {week} (as of {as_of})
**Needs a decision** - bullet per decision: release, the decision, by when, who decides. If none, say "None".
**What changed this week** - max 5 bullets, most material first (slips, new blockers, things resolved).
**Who owes what** - table: Owner | Function | Item | Due | Days overdue (overdue items first).
**Reporting hygiene** - one line: missing / late / stale updates by release and TPM.
**Portfolio** - one line: count of releases by latest RAG; note any release whose reported RAG disagrees with its data.

Facts:
{facts}
"""


def build(week):
    rel = load("Releases")
    upd = load("Weekly_Updates")
    hyg = pd.read_csv(OUT / "hygiene.csv")
    slips = pd.read_csv(OUT / "milestone_slips.csv")
    od = pd.read_csv(OUT / "overdue_actions.csv")
    dinc = pd.read_csv(OUT / "data_inconsistency.csv")
    flags = pd.read_csv(OUT / "llm_flags.csv")
    det = pd.read_csv(OUT / "llm_flag_details.csv")
    wk = upd[upd["week"] == week].merge(flags, on="update_id", how="left")
    facts = {
        "releases": rel[["release_id", "product", "version", "release_type", "planned_ga", "forecast_ga", "release_status"]].astype(str).to_dict("records"),
        "this_week_updates": [{"release_id": r.release_id, "reported_rag": r.reported_rag, "text": r.update_text,
                               "rag_inconsistent_with_text": bool(r.llm_inconsistent) if pd.notna(r.llm_inconsistent) else None,
                               "decision_requested": r.decision if (pd.notna(r.needs_decision) and r.needs_decision) else ""}
                              for r in wk.itertuples()],
        "grounded_flags_this_week": det[det["update_id"].isin(wk["update_id"])].fillna("").to_dict("records"),
        "hygiene_this_week": hyg[(hyg["week"] == week) & (hyg["is_missing"] | hyg["is_late"] | hyg["is_stale"])]
                             [["release_id", "tpm", "is_missing", "is_late", "hours_late", "is_stale"]].fillna("").to_dict("records"),
        "slipped_or_blocked_milestones": slips.fillna("").to_dict("records"),
        "overdue_actions": od[["release_id", "description", "owner", "owner_function", "due_on", "days_overdue"]].to_dict("records"),
        "green_but_data_disagrees": dinc.to_dict("records"),
    }
    return TEMPLATE.format(week=week, as_of=AS_OF.date(), facts=json.dumps(facts, indent=1, default=str))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", default="W4")
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--model", default="claude-sonnet-5-5")
    a = ap.parse_args()
    p = build(a.week)
    if a.api:
        import anthropic
        msg = anthropic.Anthropic().messages.create(model=a.model, max_tokens=2000, temperature=0,
                                                    messages=[{"role": "user", "content": p}])
        (OUT / f"summary_{a.week}.md").write_text(msg.content[0].text, encoding="utf-8")
        print(msg.content[0].text)
    else:
        (PROMPTS / f"summary_{a.week}.txt").write_text(p, encoding="utf-8")
        print(f"Wrote {PROMPTS / f'summary_{a.week}.txt'} ({len(p):,} chars). Paste into a new claude.ai chat.")
