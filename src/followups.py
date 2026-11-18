"""Drafts follow-up messages for the current reporting week, ONE message per person, for human approval.

Deliberately template-based, not AI: the content is fully determined by the rule outputs, so a template
is cheaper, deterministic and can't hallucinate. (This is an "automate vs simplify" decision.)

Triggers:
  - TPM update missing this week            -> TPM
  - TPM update late this week               -> TPM (gentle reminder of the deadline)
  - TPM update stale (copy of last week)    -> TPM
  - Reported Green but data/text disagrees  -> TPM (asks to reconcile RAG); uses LLM flags if present
  - Open action item past due               -> action owner

Writes outputs/followups_<week>.csv (to, subject, body, status=DRAFT) and outputs/followups_<week>.md.
Nothing is sent. Set approved = Y in the CSV for the ones you would send.
Run after rules.py (and llm_flags.py parse, optional):  python src/followups.py
"""
import re
import pandas as pd
from common import load, OUT, current_week, AS_OF

REPLY_BY = "Monday 12:00 IST"


def email_of(name):
    return re.sub(r"[^a-z.]", "", name.lower().replace(" ", ".")) + "@example.com"   # fictional addresses


def main():
    wk = current_week()
    rel = load("Releases").set_index("release_id")
    label = lambda rid: f"{rel.loc[rid, 'product']} {rel.loc[rid, 'version']} ({rid})"
    hyg = pd.read_csv(OUT / "hygiene.csv")
    od = pd.read_csv(OUT / "overdue_actions.csv")
    dinc = pd.read_csv(OUT / "data_inconsistency.csv")
    items = {}   # person -> list of (category, text)

    def add(person, cat, text):
        items.setdefault(person, []).append((cat, text))

    h = hyg[hyg["week"] == wk]
    for r in h[h["is_missing"]].itertuples():
        add(r.tpm, "Missing update", f"The {wk} status update for {label(r.release_id)} hasn't come in yet "
                                    f"(due {pd.Timestamp(r.submission_deadline):%a %d %b %H:%M}). Please submit it by {REPLY_BY}.")
    for r in h[h["is_late"]].itertuples():
        add(r.tpm, "Late update", f"Thanks for the {wk} update on {label(r.release_id)}. It arrived {r.hours_late:.0f} h after the "
                                 f"Thursday 18:00 deadline; on time helps us get the leadership summary out on Friday.")
    for r in h[h["is_stale"]].itertuples():
        add(r.tpm, "Stale update", f"The {wk} update for {label(r.release_id)} looks the same as last week's. "
                                  f"Could you confirm it's current, or send what changed, by {REPLY_BY}?")

    for r in dinc.itertuples():
        add(rel.loc[r.release_id, "tpm"], "RAG check",
            f"{label(r.release_id)} is reported Green, but these milestones are blocked or slipping: {r.open_slips_or_blocks} "
            f"(up to {int(r.max_slip_days)} days). Should the RAG be Amber? Please confirm by {REPLY_BY}.")
    llm = OUT / "llm_flags.csv"
    if llm.exists():
        f = pd.read_csv(llm)
        upd = load("Weekly_Updates")
        f = f.merge(upd[["update_id", "release_id", "week", "reported_rag"]], on="update_id")
        f = f[(f["week"] == wk) & (f["llm_inconsistent"] == True) & (~f["release_id"].isin(dinc["release_id"]))]
        for r in f.itertuples():
            add(rel.loc[r.release_id, "tpm"], "RAG check",
                f"Your {wk} update for {label(r.release_id)} is marked {r.reported_rag}, but the text suggests otherwise: "
                f"{r.inconsistency_reason} Could you confirm the right RAG by {REPLY_BY}?")

    for r in od.itertuples():
        add(r.owner, "Overdue action", f"[{label(r.release_id)}] \"{r.description}\" was due {pd.Timestamp(r.due_on):%a %d %b} "
                                      f"({r.days_overdue} day{'s' if r.days_overdue != 1 else ''} overdue). Can you share a new date or close it out by {REPLY_BY}?")

    rows, md = [], [f"# Follow-up drafts: {wk} (as of {AS_OF:%d %b %Y})", "",
                    "Status: **DRAFT, needs human approval. Nothing has been sent.**", ""]
    for person, its in sorted(items.items()):
        cats = sorted({c for c, _ in its})
        subject = f"[Release status {wk}] {len(its)} item{'s' if len(its) > 1 else ''} need{'' if len(its) > 1 else 's'} your input: {', '.join(cats)}"
        first = person.split()[0]
        body = f"Hi {first},\n\n" + "\n".join(f"{i}. {t}" for i, (_, t) in enumerate(its, 1)) + \
               "\n\nThanks,\nProduct Operations"
        rows.append({"to": person, "email": email_of(person), "subject": subject, "item_count": len(its),
                     "categories": "; ".join(cats), "body": body, "status": "DRAFT", "approved": ""})
        md += [f"## To: {person} <{email_of(person)}>", f"**Subject:** {subject}", "", body, "", "---", ""]
    pd.DataFrame(rows).to_csv(OUT / f"followups_{wk}.csv", index=False)
    (OUT / f"followups_{wk}.md").write_text("\n".join(md), encoding="utf-8")
    n = sum(len(v) for v in items.values())
    print(f"{len(rows)} follow-up drafts ({n} items) for {wk} -> outputs/followups_{wk}.md")


if __name__ == "__main__":
    main()
