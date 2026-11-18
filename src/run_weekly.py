"""ONE command for the whole weekly run.

    python src/run_weekly.py                         # Claude Pro (manual paste) mode
    python src/run_weekly.py --form "responses.xlsx" # import new form responses first
    python src/run_weekly.py --llm api               # fully hands-off (needs ANTHROPIC_API_KEY + credits)

Steps: [form import] -> rules -> LLM checks -> eval (if labels exist) -> weekly summary -> follow-up drafts.
In manual mode the run stops at the LLM step only if a prompt batch has no saved reply yet; it tells you
exactly which files to paste, and you run the same command again afterwards. Rule-based outputs and
follow-up drafts are produced either way.
Every run is logged in outputs/run_log.csv.
"""
import argparse, subprocess, sys
from datetime import datetime
from pathlib import Path
import pandas as pd

SRC = Path(__file__).resolve().parent
PY = sys.executable


def step(name, *args, check=True):
    print(f"\n=== {name} ===")
    r = subprocess.run([PY, str(SRC / args[0]), *args[1:]], cwd=SRC.parent)
    if check and r.returncode != 0:
        sys.exit(f"Step '{name}' failed. Fix the error above and re-run.")
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--form", help="Microsoft/Google Forms export (.xlsx or .csv) to import first")
    ap.add_argument("--llm", choices=["manual", "api"], default="manual")
    ap.add_argument("--model", default="claude-sonnet-5-5")
    a = ap.parse_args()

    if a.form:
        step("1. Import form responses", "ingest_form.py", "--file", a.form)
    step("2. Rule checks (missing / late / stale / readiness / slips / overdue)", "rules.py")

    from common import PROMPTS, RESP, OUT, current_week
    llm_ready = False
    if a.llm == "api":
        step("3. LLM checks via API", "llm_flags.py", "api", "--model", a.model)
        llm_ready = step("3b. Parse + citation guardrail", "llm_flags.py", "parse")
    else:
        step("3. Prepare LLM prompt batches", "llm_flags.py", "prepare")
        pending = [p.name for p in sorted(PROMPTS.glob("batch_*.txt"))
                   if not (RESP / p.name.replace(".txt", ".json")).exists()]
        if pending:
            print("\n>>> ACTION NEEDED: paste these into NEW claude.ai chats and save each reply as responses/<same name>.json:")
            for p in pending:
                print(f"    prompts/{p}  ->  responses/{p.replace('.txt', '.json')}")
            print(">>> Then run this command again. Continuing with rule-based outputs only.")
        else:
            llm_ready = step("3b. Parse + citation guardrail", "llm_flags.py", "parse")

    if llm_ready:
        step("4. Eval vs ground truth", "eval.py", check=False)
        wk = current_week()
        if a.llm == "api":
            step("5. Weekly summary (API)", "weekly_summary.py", "--week", wk, "--api", "--model", a.model)
        else:
            step("5. Weekly summary prompt", "weekly_summary.py", "--week", wk)
            print(f">>> ACTION NEEDED: paste prompts/summary_{wk}.txt into a new claude.ai chat; save the reply as outputs/summary_{wk}.md")
    step("6. Follow-up drafts (for approval)", "followups.py")

    wk = current_week()
    h = pd.read_csv(OUT / "hygiene.csv"); hw = h[h["week"] == wk]
    fu = pd.read_csv(OUT / f"followups_{wk}.csv")
    log = {"run_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "week": wk, "llm_mode": a.llm, "llm_done": llm_ready,
           "missing": int(hw.is_missing.sum()), "late": int(hw.is_late.sum()), "stale": int(hw.is_stale.sum()),
           "overdue_actions": len(pd.read_csv(OUT / "overdue_actions.csv")),
           "followup_drafts": len(fu)}
    lp = OUT / "run_log.csv"
    (pd.concat([pd.read_csv(lp), pd.DataFrame([log])]) if lp.exists() else pd.DataFrame([log])).to_csv(lp, index=False)
    print("\n=== Run summary ===")
    for k, v in log.items():
        print(f"  {k}: {v}")
    print("\nHuman steps left: approve follow-ups (outputs/followups_%s.csv)%s" %
          (wk, "" if llm_ready else ", paste pending LLM batches and re-run"))


if __name__ == "__main__":
    main()
