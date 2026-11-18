"""LLM checks on TPM update text: RAG-vs-text inconsistency, risks, cross-functional dependencies,
decision requests. Every flag must carry a verbatim quote from the update; flags whose quote is not
found in the update text are dropped (citation guardrail).

Two ways to run the model:

  A) Claude Pro (no API key, free with your subscription)
     1. python src/llm_flags.py prepare          -> writes prompts/batch_01.txt ... batch_03.txt
     2. For each batch: open a NEW chat on claude.ai (incognito/temporary chat if available, so
        memory doesn't influence it), paste the whole file, send.
     3. Copy Claude's JSON reply into responses/batch_01.json (same number as the prompt).
     4. python src/llm_flags.py parse            -> outputs/llm_flags.csv + llm_flag_details.csv

  B) Anthropic API (billed separately from Claude Pro; needs ANTHROPIC_API_KEY)
     pip install anthropic
     python src/llm_flags.py api --model claude-sonnet-5-5
     python src/llm_flags.py parse
"""
import argparse, json, re, sys
from datetime import datetime
import pandas as pd
from common import load, PROMPTS, RESP, OUT, RISK_CATEGORIES, FUNCTIONS

BATCH_SIZE = 12
PROMPT_VERSION = "v1"

INSTRUCTIONS = f"""You are a Product Operations analyst reviewing weekly TPM status updates for software releases.
For EACH update below, judge only from the update text and the fields given. Do not invent facts.

Definitions:
- inconsistent: true if reported_rag does not match what the text describes. Typical case: reported_rag is
  "Green" but the text describes a slipped or likely-slipping date, a missed approval, quality below its exit
  criterion, open P1 defects, failing tests, or a stalled dependency. Also true if the RAG is Amber/Red but the
  text says everything is on track with no open problems. Otherwise false.
- has_risk: true if the text describes a CURRENT, UNRESOLVED threat to schedule, quality, security or commercial
  readiness. Resolved past problems and negated statements (e.g. "no escalations", "blocker is resolved") are NOT
  risks. A dependency that is on schedule is NOT a risk by itself.
- risks: each with category in {RISK_CATEGORIES}, severity in [High, Medium, Low].
- dependencies: anything the release needs from a team or party outside its own engineering team (a deliverable,
  sign-off, approval or decision), even if on schedule. function must be one of {FUNCTIONS}.
  "Partner" = an external commercial partner. Do not list teams that are merely informed.
- needs_decision: true only if the text explicitly asks leadership for a decision.
- evidence: a VERBATIM quote copied exactly from update_text (max 25 words). Every inconsistency, risk and
  dependency needs one. If you cannot quote it, do not flag it.

Return ONLY a JSON array (no prose, no markdown fences), one object per update, in this exact shape:
[{{"update_id": "U001",
   "inconsistent": false, "inconsistency_reason": "", "inconsistency_evidence": "",
   "has_risk": false,
   "risks": [{{"category": "Schedule", "severity": "High", "evidence": "..."}}],
   "dependencies": [{{"function": "Pricing", "needed": "SKU approval", "evidence": "..."}}],
   "needs_decision": false, "decision": "",
   "confidence": 0.0}}]
"""


def batches():
    upd = load("Weekly_Updates")
    rel = load("Releases")[["release_id", "product", "version", "release_type", "planned_ga"]]
    df = upd.merge(rel, on="release_id")
    recs = [{"update_id": r.update_id, "release": f"{r.product} {r.version} ({r.release_type})",
             "week": r.week, "planned_ga": r.planned_ga.strftime("%Y-%m-%d"),
             "reported_rag": r.reported_rag, "update_text": r.update_text} for r in df.itertuples()]
    return [recs[i:i + BATCH_SIZE] for i in range(0, len(recs), BATCH_SIZE)]


def prompt_text(batch):
    return INSTRUCTIONS + "\nUpdates:\n" + json.dumps(batch, indent=1, ensure_ascii=False)


def cmd_prepare(_):
    """Writes a batch file only if its content changed, so existing replies stay valid. If a batch's
    content changed, its old reply no longer matches and is moved to responses/archive/."""
    new_files, changed = [], []
    for i, b in enumerate(batches(), 1):
        p = PROMPTS / f"batch_{i:02d}.txt"
        txt = prompt_text(b)
        if p.exists() and p.read_text(encoding="utf-8") == txt:
            continue
        r = RESP / f"batch_{i:02d}.json"
        if r.exists():
            (RESP / "archive").mkdir(exist_ok=True)
            r.rename(RESP / "archive" / f"batch_{i:02d}_{datetime.now():%Y%m%d_%H%M%S}.json")
            changed.append(p.name)
        p.write_text(txt, encoding="utf-8")
        new_files.append(p.name)
    print(f"{i} batches total | new/changed: {new_files or 'none'}" +
          (f" | archived stale replies for: {changed}" if changed else ""))


def cmd_api(a):
    try:
        import anthropic
    except ImportError:
        sys.exit("pip install anthropic   (and set ANTHROPIC_API_KEY)")
    client = anthropic.Anthropic()
    usage = []
    for i, b in enumerate(batches(), 1):
        msg = client.messages.create(model=a.model, max_tokens=8000, temperature=0,
                                     messages=[{"role": "user", "content": prompt_text(b)}])
        (RESP / f"batch_{i:02d}.json").write_text(msg.content[0].text, encoding="utf-8")
        usage.append({"batch": i, "model": a.model, "input_tokens": msg.usage.input_tokens,
                      "output_tokens": msg.usage.output_tokens})
        print(f"batch {i}: {msg.usage.input_tokens} in / {msg.usage.output_tokens} out tokens")
    pd.DataFrame(usage).to_csv(OUT / "api_usage.csv", index=False)


def norm(s):
    s = (s or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().strip('."').lower()


def grounded(quote, text):
    q = norm(quote)
    return bool(q) and q in norm(text)


def extract_json(raw):
    raw = raw.strip()
    m = re.search(r"\[.*\]", raw, re.S)          # tolerate ```json fences or stray prose
    if not m:
        raise ValueError("no JSON array found")
    return json.loads(m.group(0))


def cmd_parse(_):
    texts = load("Weekly_Updates").set_index("update_id")["update_text"].to_dict()
    valid = {p.stem for p in PROMPTS.glob("batch_*.txt")}
    files = sorted(f for f in RESP.glob("batch_*.json") if f.stem in valid)
    if not files:
        sys.exit(f"No responses in {RESP}. Run 'prepare' and save Claude's replies first.")
    rows, details, dropped, seen = [], [], [], set()
    for f in files:
        for o in extract_json(f.read_text(encoding="utf-8")):
            uid = o.get("update_id")
            if uid not in texts:
                dropped.append((uid, "unknown update_id", "")); continue
            seen.add(uid)
            t = texts[uid]
            inc = bool(o.get("inconsistent"))
            if inc and not grounded(o.get("inconsistency_evidence"), t):
                dropped.append((uid, "inconsistency without verbatim evidence", o.get("inconsistency_evidence")))
                inc = False
            risks = []
            for r in o.get("risks") or []:
                ok = grounded(r.get("evidence"), t) and r.get("category") in RISK_CATEGORIES
                (risks if ok else dropped).append(r if ok else (uid, "risk ungrounded/bad category", r.get("evidence")))
            deps = []
            for d in o.get("dependencies") or []:
                ok = grounded(d.get("evidence"), t) and d.get("function") in FUNCTIONS
                (deps if ok else dropped).append(d if ok else (uid, "dependency ungrounded/bad function", d.get("evidence")))
            has_risk = bool(o.get("has_risk")) and len(risks) > 0
            rows.append({"update_id": uid, "llm_inconsistent": inc, "inconsistency_reason": o.get("inconsistency_reason", "") if inc else "",
                         "llm_has_risk": has_risk,
                         "llm_risk_categories": ";".join(sorted({r["category"] for r in risks})) if has_risk else "",
                         "llm_dependency_functions": ";".join(sorted({d["function"] for d in deps})),
                         "needs_decision": bool(o.get("needs_decision")), "decision": o.get("decision", ""),
                         "confidence": o.get("confidence")})
            for r in risks if has_risk else []:
                details.append({"update_id": uid, "type": "risk", "label": r["category"], "severity": r.get("severity"), "evidence": r["evidence"]})
            for d in deps:
                details.append({"update_id": uid, "type": "dependency", "label": d["function"], "severity": "", "evidence": d["evidence"], "needed": d.get("needed", "")})
            if inc:
                details.append({"update_id": uid, "type": "inconsistency", "label": "RAG vs text", "severity": "", "evidence": o.get("inconsistency_evidence")})
    missing = sorted(set(texts) - seen)
    pd.DataFrame(rows).sort_values("update_id").to_csv(OUT / "llm_flags.csv", index=False)
    pd.DataFrame(details).to_csv(OUT / "llm_flag_details.csv", index=False)
    pd.DataFrame(dropped, columns=["update_id", "reason", "evidence"]).to_csv(OUT / "llm_dropped_flags.csv", index=False)
    print(f"Parsed {len(rows)} updates | dropped {len(dropped)} ungrounded/invalid flags | missing from responses: {missing or 'none'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("prepare")
    p = sp.add_parser("api"); p.add_argument("--model", default="claude-sonnet-5-5")
    sp.add_parser("parse")
    a = ap.parse_args()
    {"prepare": cmd_prepare, "api": cmd_api, "parse": cmd_parse}[a.cmd](a)
