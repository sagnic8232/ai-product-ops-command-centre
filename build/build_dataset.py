"""Builds the synthetic ReleaseOps dataset: workbook, Jira-style CSV, ground truth.
All products, people and figures are fictional."""
from datetime import date, datetime, timedelta
import csv, os
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

OUT = os.path.join(os.path.dirname(__file__), "..", "data")
AS_OF = date(2026, 11, 13)

# ---------------- Releases ----------------
releases = [
 # id, product, version, type, commercial_change, GPM, TPM, planned_GA, forecast_GA, status, rag, test_pass, p1, security
 ("R01","Query Engine","5.0","Major","Y","Ananya Rao","Vikram Shah",date(2026,12,4),date(2026,12,18),"Active","Amber",0.915,3,"Pending"),
 ("R02","Cloud Connector","3.1","Minor","Y","Rahul Menon","Priya Nair",date(2026,11,20),date(2026,11,27),"Active","Amber",0.972,0,"Approved"),
 ("R03","Admin Console","2.4","Minor","N","Rahul Menon","Arjun Iyer",date(2026,11,27),date(2026,11,27),"Active","Green",0.988,0,"In review"),
 ("R04","Data Catalog","1.0","Major","Y","Meera Kulkarni","Sneha Reddy",date(2026,12,18),date(2027,1,15),"Active","Red",0.880,3,"Pending"),
 ("R05","ML Feature Store","2.2","Minor","N","Meera Kulkarni","Karan Gupta",date(2026,12,11),date(2026,12,11),"Active","Amber",0.954,1,"Pending"),
 ("R06","Query Engine","4.9.2","Patch","N","Ananya Rao","Vikram Shah",date(2026,11,6),date(2026,11,6),"Shipped","Green",0.996,0,"Approved"),
 ("R07","Connector Pack","3.0.5","Patch","N","Rahul Menon","Priya Nair",date(2026,11,13),date(2026,11,20),"Active","Amber",0.931,2,"Approved"),
 ("R08","Workload Manager","6.1.1","Patch","N","Ananya Rao","Deepak Joshi",date(2026,11,27),date(2026,11,27),"Active","Green",0.991,0,"Approved"),
 ("R09","Auth Service","2.8-HF1","Hotfix","N","Meera Kulkarni","Karan Gupta",date(2026,10,28),date(2026,10,28),"Shipped","Green",1.000,0,"Approved"),
 ("R10","Billing Integration","1.3","Minor","Y","Rahul Menon","Arjun Iyer",date(2026,12,4),date(2026,12,11),"Active","Amber",0.960,1,"Approved"),
]
rel_cols = ["release_id","product","version","release_type","commercial_change","gpm","tpm",
            "planned_ga","forecast_ga","release_status","official_rag","test_pass_rate","open_p1_defects","security_signoff"]
df_rel = pd.DataFrame(releases, columns=rel_cols)

# ---------------- Readiness checklist ----------------
items = [  # item, owner_function, days_before_GA, Major, Minor, Patch, Hotfix
 ("Design complete","Engineering",60,"Y","Y","N","N"),
 ("Code freeze","Engineering",28,"Y","Y","Y","N"),
 ("QA complete (>=95% pass, 0 open P1)","QA",14,"Y","Y","Y","Y"),
 ("Security review sign-off","Security",12,"Y","Y","Y","Y"),
 ("Pricing approved","Pricing",10,"Y","Conditional","N","N"),
 ("Legal review complete","Legal",10,"Y","Conditional","N","N"),
 ("Docs & release notes","Docs",5,"Y","Y","Y","N"),
 ("Support enablement","Support",5,"Y","Y","N","N"),
 ("Marketing launch kit","Marketing",3,"Y","Conditional","N","N"),
 ("GA go/no-go","Product Ops",2,"Y","Y","Y","Y"),
]
chk_rows = []
for it, fn, off, *req in items:
    for rt, r in zip(["Major","Minor","Patch","Hotfix"], req):
        chk_rows.append((rt, it, fn, off, r))
df_chk = pd.DataFrame(chk_rows, columns=["release_type","checklist_item","owner_function","planned_days_before_ga","required"])
df_chk["rule_note"] = df_chk["required"].map({"Conditional":"Required only if Releases.commercial_change = Y","Y":"","N":""})

# ---------------- Milestones ----------------
# overrides: (release, item) -> dict(actual, forecast, status)
D = lambda m, d, y=2026: date(y, m, d)
ov = {
 ("R01","Code freeze"): dict(actual=D(11,10), status="Done"),
 ("R01","QA complete (>=95% pass, 0 open P1)"): dict(forecast=D(11,27), status="In progress"),
 ("R01","Security review sign-off"): dict(forecast=D(12,4), status="Blocked", note="Pen-test vendor slot only from 1 Dec"),
 ("R02","Pricing approved"): dict(forecast=D(11,19), status="Blocked", note="Missed 4 Nov committee; outcome of 12 Nov slot pending"),
 ("R02","Docs & release notes"): dict(status="In progress"),
 ("R03","Security review sign-off"): dict(status="In progress", forecast=D(11,15)),
 ("R04","Code freeze"): dict(forecast=D(12,4), status="In progress"),
 ("R04","Legal review complete"): dict(forecast=D(1,8,2027), status="Blocked", note="Partner T&Cs redlines unanswered"),
 ("R04","Marketing launch kit"): dict(status="Not started", note="Needs final positioning by 25 Nov"),
 ("R05","Code freeze"): dict(forecast=D(11,20), status="In progress", note="Waiting on Platform Eng v2 identity API (Sprint 48)"),
 ("R07","QA complete (>=95% pass, 0 open P1)"): dict(forecast=D(11,17), status="In progress", note="Salesforce connector tests failing"),
 ("R07","Security review sign-off"): dict(actual=D(11,2), status="Done"),
 ("R07","Docs & release notes"): dict(status="In progress", forecast=D(11,18)),
 ("R07","GA go/no-go"): dict(status="Not started", forecast=D(11,19)),
 ("R10","Code freeze"): dict(actual=D(11,12), status="Done"),
 ("R10","Pricing approved"): dict(status="Blocked", forecast=D(12,1), note="Needs Finance sign-off on metering logic first"),
}
ms_rows, mid = [], 1
for r in releases:
    rid, rtype, cc, pga = r[0], r[3], r[4], r[7]
    for it, fn, off, *req in items:
        reqd = dict(zip(["Major","Minor","Patch","Hotfix"], req))[rtype]
        if reqd == "N" or (reqd == "Conditional" and cc != "Y"):
            continue
        planned = pga - timedelta(days=off)
        o = ov.get((rid, it), {})
        if "status" in o:
            status = o["status"]
        else:
            status = "Done" if planned <= AS_OF else "Not started"
        actual = o.get("actual", planned if status == "Done" else None)
        forecast = o.get("forecast", actual if actual else planned)
        ms_rows.append((f"M{mid:03d}", rid, it, fn, planned, forecast, actual, status, o.get("note","")))
        mid += 1
df_ms = pd.DataFrame(ms_rows, columns=["milestone_id","release_id","milestone","owner_function","planned_date","forecast_date","actual_date","status","note"])

# ---------------- Reporting calendar ----------------
cal = [("W1", D(10,23), datetime(2026,10,22,18,0)),
       ("W2", D(10,30), datetime(2026,10,29,18,0)),
       ("W3", D(11,6),  datetime(2026,11,5,18,0)),
       ("W4", D(11,13), datetime(2026,11,12,18,0))]
df_cal = pd.DataFrame(cal, columns=["week","week_ending","submission_deadline"])
dl = {w: d for w, _, d in cal}

# ---------------- Weekly updates + ground truth ----------------
# (release, week, submit offset hours vs deadline (neg = early), rag, pct, text, GT: inconsistent, risk, risk_categories, dependency_functions, note)
U = [
 ("R01","W1",-5,"Green",70,"Feature development 90% done. Code freeze on track for 6 Nov. Performance benchmarks scheduled for next week.",0,0,"","",""),
 ("R01","W2",-3,"Green",78,"Code freeze moved to 10 Nov to land the optimizer changes. Benchmarks show a 12% regression on join-heavy queries vs 4.9; perf team investigating.",1,1,"Schedule;Quality","","Green despite code-freeze slip and 12% perf regression"),
 ("R01","W3",-2,"Amber",84,"Code freeze now confirmed for 10 Nov. Join regression down to 5% after the fix, still above the 2% exit criterion. Security pen-test vendor slot is only available from 1 Dec, which pushes security sign-off.",0,1,"Schedule;Quality;Security","Security",""),
 ("R01","W4",17.5,"Amber",88,"Code freeze completed 10 Nov. Regression now at 3%. Security sign-off expected 4 Dec, so GA forecast moves to 18 Dec. Need a leadership decision on whether to ship with the 3% regression documented as a known issue.",0,1,"Schedule;Quality;Security","Security","Submitted late (Fri). Contains explicit decision request"),
 ("R02","W1",-6,"Green",80,"Code freeze done 23 Oct. QA in progress, pass rate 94% and climbing. New consumption-based SKU submitted to Pricing for approval.",0,0,"","Pricing","Dependency exists but no risk yet"),
 ("R02","W2",-4,"Green",88,"QA at 97%, zero P1s. Security sign-off received. Pricing committee review scheduled for 4 Nov.",0,0,"","Pricing",""),
 ("R02","W3",-1,"Green",92,"Pricing committee did not get to our SKU on 4 Nov; next slot is 12 Nov. Docs in progress. Everything else on track for 20 Nov GA.",1,1,"Commercial;Schedule","Pricing","Pricing approval (planned 10 Nov) will miss; GA at risk, still Green. No obvious risk keywords"),
 ("R02","W4",-2,"Green",94,"Still waiting on the Pricing committee outcome from 12 Nov. Without an approved SKU we can't publish the price list, so GA will likely move to 27 Nov.",1,1,"Commercial;Schedule","Pricing","Green while GA likely slipping"),
 ("R03","W1",-8,"Green",72,"UI redesign complete, code freeze planned 30 Oct. Usability test with 5 admins scheduled.",0,0,"","",""),
 ("R03","W2",-5,"Green",80,"Code freeze on track for 30 Oct. QA started; 212 of 230 test cases passed so far, no P1s. Docs drafting underway.",0,0,"","",""),
 ("R03","W3",-4,"Green",80,"Code freeze on track for 30 Oct. QA started; 212 of 230 test cases passed so far, no P1s. Docs drafting underway.",0,0,"","","STALE: exact copy of W2 (rules should catch; not an LLM label)"),
 ("R03","W4",-3,"Green",90,"Code freeze done 30 Oct. QA complete at 98.8% pass rate, no P1s. Security review in progress, expected 15 Nov. Docs drafted.",0,0,"","Security","Routine dependency on Security review, on schedule"),
 ("R04","W1",-6,"Green",40,"Core metadata ingestion complete. Integration with the external lineage partner's connector has started. Legal has received the partner T&Cs for review.",0,0,"","Legal;Partner",""),
 ("R04","W2",-2,"Green",50,"Partner integration 60% done. Legal sent redlines back to the partner on 27 Oct; the partner's counsel has not responded. 5 open P1 defects in search indexing.",1,1,"Quality;Commercial","Legal;Partner","Green with 5 P1s and stalled legal; no obvious risk keywords"),
 ("R04","W3",3.1,"Amber",56,"Search indexing P1s down from 5 to 3. Code freeze will move from 20 Nov to 4 Dec. Partner redlines still open. Marketing has asked for final positioning by 25 Nov for the launch kit.",0,1,"Schedule;Quality;Commercial","Legal;Partner;Marketing","Submitted late (Thu 21:05)"),
 ("R04","W4",-1,"Red",60,"The partner has still not returned the T&Cs, and Legal won't clear GA without them. With code freeze at 4 Dec, the 18 Dec GA is not achievable; proposing 15 Jan. Decision needed: hold GA for the partner connector, or ship 1.0 without it and add it in 1.1.",0,1,"Schedule;Commercial","Legal;Partner","Explicit decision request"),
 ("R05","W1",16.25,"Green",55,"Online store latency work done. Depends on Platform Eng's v2 identity API, planned for Sprint 46. Code freeze 13 Nov.",0,0,"","Platform Eng","Submitted late (Fri)"),
 ("R05","W2",15.67,"Green",62,"Integration with the v2 identity API started against a mock. Platform Eng confirmed Sprint 46 delivery. QA plan approved.",0,0,"","Platform Eng","Submitted late (Fri)"),
 ("R05","W4",-3,"Amber",68,"Platform Eng now says the v2 identity API lands in Sprint 48, not 46. We can't finish integration testing until then, so code freeze moves to 20 Nov. GA of 11 Dec holds only if QA compresses to one week.",0,1,"Schedule;Dependency","Platform Eng","W3 missing"),
 ("R06","W1",-7,"Green",90,"Patch includes 14 customer-reported fixes. Code freeze done 9 Oct. QA regression suite 99.6% passed.",0,0,"","",""),
 ("R06","W2",-6,"Green",95,"Security scan clean. Release notes in review. On track for 6 Nov GA.",0,0,"","",""),
 ("R06","W3",-5,"Green",98,"Go/no-go approved on 4 Nov. GA on 6 Nov as planned.",0,0,"","",""),
 ("R06","W4",-6,"Green",100,"Shipped 6 Nov. No escalations in the first week; two support tickets, both configuration-related.",0,0,"","","Negation trap: 'No escalations'"),
 ("R07","W1",-4,"Green",70,"Patch bundles fixes for 6 connectors. Code freeze done 16 Oct. QA regression started.",0,0,"","",""),
 ("R07","W3",-2,"Green",85,"QA rerun has 2 connectors (SAP, Salesforce) still failing 11 tests. Fix in progress. May need to move GA by a week.",1,1,"Quality;Schedule","","W2 missing. Green despite failing tests and likely slip"),
 ("R07","W4",-1,"Amber",90,"SAP connector fixed. Salesforce tests still failing on the API v61 changes; GA moved to 20 Nov. Support has been told to hold the customer communication.",0,1,"Quality;Schedule","","Support informed, not a blocking dependency (judgement call)"),
 ("R08","W1",-5,"Amber",60,"Patch scope frozen: 9 fixes. Code freeze on track for 30 Oct. One blocker on the scheduler fix (deadlock under high concurrency) being investigated.",0,1,"Quality","",""),
 ("R08","W2",-4,"Amber",64,"Patch scope frozen: 9 fixes. Code freeze on track for 30 Oct. One blocker on the scheduler fix (deadlock under high concurrency) still being investigated.",0,1,"Quality","","STALE: near-copy of W1"),
 ("R08","W4",-3,"Green",85,"The scheduler deadlock blocker from last month is resolved and verified in QA. Code freeze done 30 Oct, QA at 99.1%, no P1s. On track for 27 Nov.",0,0,"","","Resolved-blocker trap. W3 missing"),
 ("R09","W1",-9,"Amber",80,"Hotfix for an SSO token refresh failure affecting 3 enterprise customers. Fix verified in staging; security review in progress. Target 28 Oct.",0,1,"Quality","Security","Customer-impacting issue being fixed"),
 ("R09","W2",-7,"Green",100,"Security sign-off received. Hotfix deployed 28 Oct. All 3 customers confirmed the fix.",0,0,"","",""),
 ("R09","W3",-8,"Green",100,"No regressions since deployment. Closing this release.",0,0,"","","Negation trap: 'No regressions'"),
 ("R09","W4",-8,"Green",100,"Closed. No further updates.",0,0,"","",""),
 ("R10","W1",-3,"Green",50,"Usage metering events wired into the billing pipeline. Code freeze 6 Nov. Needs Finance sign-off on the metering logic and Pricing approval for the new overage rate.",0,0,"","Finance;Pricing",""),
 ("R10","W2",-2,"Green",58,"Metering accuracy at 99.2% vs the 99.9% target. Code freeze will be 12 Nov instead of 6 Nov to close the gap.",1,1,"Quality;Schedule","","Green with below-target accuracy and code-freeze slip; no risk keywords"),
 ("R10","W3",-1,"Amber",66,"Accuracy at 99.7%. Finance hasn't signed off the metering logic yet, and Pricing can't take the overage rate to committee until they do. GA of 4 Dec is at risk.",0,1,"Schedule;Commercial","Finance;Pricing","W4 missing"),
]
rel_tpm = {r[0]: r[6] for r in releases}
upd_rows, gt_rows = [], []
for i, u in enumerate(U, 1):
    rid, wk, off, rag, pct, txt, inc, risk, rc, dep, note = u
    uid = f"U{i:03d}"
    ts = dl[wk] + timedelta(hours=off)
    upd_rows.append((uid, rid, wk, rel_tpm[rid], "TPM", ts, rag, pct/100, txt))
    gt_rows.append((uid, rid, wk, inc, risk, rc, dep, note))
df_upd = pd.DataFrame(upd_rows, columns=["update_id","release_id","week","submitted_by","role","submitted_at","reported_rag","pct_complete","update_text"])
df_gt = pd.DataFrame(gt_rows, columns=["update_id","release_id","week","gt_inconsistent","gt_has_risk","gt_risk_categories","gt_dependency_functions","label_note"])
df_gt["label_status"] = "DRAFT - verify"

# ---------------- Action items ----------------
A = [
 ("R01","Confirm pen-test vendor slot or alternative vendor","Imran Sheikh","Security",D(10,30),D(11,7),"Open",None),
 ("R01","Root-cause join-query regression","Vikram Shah","Engineering",D(10,29),D(11,5),"Closed",D(11,4)),
 ("R01","Draft known-issue note for 3% regression","Vikram Shah","Docs",D(11,12),D(11,19),"Open",None),
 ("R01","Leadership decision: ship with known regression?","Ananya Rao","Product",D(11,12),D(11,18),"Open",None),
 ("R02","Get consumption SKU onto Pricing committee agenda","Rohit Bansal","Pricing",D(10,22),D(11,4),"Closed",D(11,3)),
 ("R02","Escalate SKU approval after missed 4 Nov slot","Rahul Menon","Product",D(11,5),D(11,10),"Open",None),
 ("R02","Prepare price list draft for publication","Rohit Bansal","Pricing",D(11,5),D(11,12),"Open",None),
 ("R03","Run usability test with 5 admins","Arjun Iyer","Design",D(10,22),D(10,28),"Closed",D(10,27)),
 ("R03","Book security review slot","Arjun Iyer","Security",D(10,29),D(11,6),"Closed",D(11,5)),
 ("R04","Chase partner counsel on T&C redlines","Farah Khan","Legal",D(10,28),D(11,4),"Open",None),
 ("R04","Fix 5 P1 defects in search indexing","Sneha Reddy","Engineering",D(10,29),D(11,12),"Open",None),
 ("R04","Send final positioning to Marketing","Meera Kulkarni","Product",D(11,5),D(11,25),"Open",None),
 ("R04","Options paper: GA with vs without partner connector","Meera Kulkarni","Product",D(11,12),D(11,19),"Open",None),
 ("R05","Confirm v2 identity API delivery sprint","Suresh Pillai","Platform Eng",D(10,23),D(10,30),"Closed",D(10,29)),
 ("R05","Compressed 1-week QA plan","Neha Batra","QA",D(11,12),D(11,17),"Open",None),
 ("R05","Submit W3 status update","Karan Gupta","Engineering",D(11,6),D(11,7),"Open",None),
 ("R06","Publish 4.9.2 release notes","Vikram Shah","Docs",D(10,29),D(11,5),"Closed",D(11,5)),
 ("R07","Fix SAP connector test failures","Priya Nair","Engineering",D(11,5),D(11,10),"Closed",D(11,11)),
 ("R07","Fix Salesforce API v61 test failures","Priya Nair","Engineering",D(11,5),D(11,12),"Open",None),
 ("R07","Hold customer comms until new GA confirmed","Lakshmi Venkat","Support",D(11,12),D(11,19),"Open",None),
 ("R07","Submit W2 status update","Priya Nair","Engineering",D(10,30),D(10,31),"Closed",D(11,3)),
 ("R08","Investigate scheduler deadlock","Deepak Joshi","Engineering",D(10,22),D(10,29),"Closed",D(11,6)),
 ("R08","Submit W3 status update","Deepak Joshi","Engineering",D(11,6),D(11,7),"Open",None),
 ("R09","Confirm fix with 3 affected customers","Lakshmi Venkat","Support",D(10,28),D(10,30),"Closed",D(10,29)),
 ("R10","Finance sign-off on metering logic","Nisha Agarwal","Finance",D(10,23),D(11,6),"Open",None),
 ("R10","Close metering accuracy gap to 99.9%","Arjun Iyer","Engineering",D(10,29),D(11,12),"Open",None),
 ("R10","Overage rate to Pricing committee","Rohit Bansal","Pricing",D(10,23),D(11,26),"Open",None),
]
df_act = pd.DataFrame([(f"A{i:03d}",)+a for i,a in enumerate(A,1)],
    columns=["action_id","release_id","description","owner","owner_function","raised_on","due_on","status","closed_on"])

df_own = pd.DataFrame([("Legal","Farah Khan"),("Pricing","Rohit Bansal"),("Finance","Nisha Agarwal"),
    ("Marketing","Tara D'Souza"),("Security","Imran Sheikh"),("Platform Eng","Suresh Pillai"),
    ("Support","Lakshmi Venkat"),("QA","Neha Batra"),("Docs","Kavya Rao"),("Product Ops","(you)")],
    columns=["function","owner"])

readme = [
 ["ReleaseOps Command Centre - synthetic dataset (all names, products and figures are fictional)"],
 [f"Report as-of date: {AS_OF.isoformat()} (end of W4). Reporting weeks W1-W4, TPM updates due Thursday 18:00 IST."],
 [""],
 ["Sheet","What it holds","Used for"],
 ["Releases","10 releases: type, owners, planned vs forecast GA, quality metrics","Portfolio view, readiness"],
 ["Milestones","Release milestones generated from the readiness checklist, with planned/forecast/actual dates","Slips, readiness %, process breakdown"],
 ["Weekly_Updates","36 TPM updates (40 expected: 10 releases x 4 weeks)","Missing/late/stale rules + LLM checks"],
 ["Reporting_Calendar","Week ending + submission deadline","Missing and late rules"],
 ["Action_Items","27 cross-functional action items","Overdue rule"],
 ["Readiness_Checklist","Required gates by release type (Conditional = only if commercial_change = Y)","Readiness gates"],
 ["Function_Owners","Owner per function","Follow-up drafts"],
 [""],
 ["Ground truth labels are in a SEPARATE file (ground_truth.csv). Do not load it into Power BI; it is only for the eval."],
 ["Missing updates are not rows here: expected = Releases x Reporting_Calendar; missing = expected minus submitted (do this as a cross join + anti join in Power Query)."],
]

def autosize(ws):
    for col in ws.columns:
        L = max(len(str(c.value)) if c.value is not None else 0 for c in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(10, L + 2), 70)

path = os.path.join(OUT, "releaseops_dataset.xlsx")
with pd.ExcelWriter(path, engine="openpyxl", datetime_format="yyyy-mm-dd hh:mm", date_format="yyyy-mm-dd") as xw:
    pd.DataFrame(readme).to_excel(xw, "README", index=False, header=False)
    for name, df in [("Releases",df_rel),("Milestones",df_ms),("Weekly_Updates",df_upd),
                     ("Reporting_Calendar",df_cal),("Action_Items",df_act),
                     ("Readiness_Checklist",df_chk),("Function_Owners",df_own)]:
        df.to_excel(xw, name, index=False)

wb = load_workbook(path)
hdr_fill = PatternFill("solid", fgColor="1F3864")
for ws in wb.worksheets:
    for row in ws.iter_rows():
        for c in row:
            c.font = Font(name="Arial", size=10, bold=c.font.bold)
    if ws.title != "README":
        for c in ws[1]:
            c.font = Font(name="Arial", size=10, bold=True, color="FFFFFF"); c.fill = hdr_fill
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
    autosize(ws)
ws = wb["README"]; ws["A1"].font = Font(name="Arial", size=12, bold=True)
for c in ws[4]: c.font = Font(name="Arial", size=10, bold=True)
ws.column_dimensions["A"].width = 22; ws.column_dimensions["B"].width = 90; ws.column_dimensions["C"].width = 35
for name, cols in [("Releases",["L"]),("Weekly_Updates",["H"])]:
    for col in cols:
        for c in wb[name][col][1:]: c.number_format = "0.0%"
for c in wb["Weekly_Updates"]["I"]: c.alignment = Alignment(wrap_text=True, vertical="top")
wb["Weekly_Updates"].column_dimensions["I"].width = 90
wb.save(path)

df_gt.to_csv(os.path.join(OUT, "ground_truth.csv"), index=False)

# ---------------- Jira-style export ----------------
status_map = {"Done":"Done","In progress":"In Progress","Not started":"To Do","Blocked":"Blocked","Open":"To Do","Closed":"Done"}
rows, n = [], 100
for r in releases:
    n += 1
    rows.append(dict(**{"Issue key":f"REL-{n}","Summary":f"{r[1]} {r[2]} release","Issue Type":"Epic",
        "Status":"Done" if r[9]=="Shipped" else "In Progress","Priority":"High" if r[3] in ("Major","Hotfix") else "Medium",
        "Assignee":r[6],"Created":"2026-08-01","Due Date":r[7].isoformat(),"Resolved":r[8].isoformat() if r[9]=="Shipped" else "",
        "Fix Version/s":f"{r[1]} {r[2]}","Components":r[3],"Labels":"release","Release ID":r[0]}))
tpm = rel_tpm
for m in ms_rows:
    n += 1
    rel = next(x for x in releases if x[0]==m[1])
    rows.append({"Issue key":f"REL-{n}","Summary":m[2],"Issue Type":"Task","Status":status_map[m[7]],
        "Priority":"High" if m[7]=="Blocked" else "Medium","Assignee":tpm[m[1]],"Created":"2026-08-15",
        "Due Date":m[4].isoformat(),"Resolved":m[6].isoformat() if m[6] else "","Fix Version/s":f"{rel[1]} {rel[2]}",
        "Components":m[3],"Labels":"milestone","Release ID":m[1]})
for a in df_act.itertuples():
    n += 1
    rel = next(x for x in releases if x[0]==a.release_id)
    rows.append({"Issue key":f"REL-{n}","Summary":a.description,"Issue Type":"Task","Status":status_map[a.status],
        "Priority":"Medium","Assignee":a.owner,"Created":a.raised_on.isoformat(),"Due Date":a.due_on.isoformat(),
        "Resolved":a.closed_on.isoformat() if a.closed_on else "","Fix Version/s":f"{rel[1]} {rel[2]}",
        "Components":a.owner_function,"Labels":"action-item","Release ID":a.release_id})
pd.DataFrame(rows).to_csv(os.path.join(OUT, "jira_export.csv"), index=False)
print("updates:", len(df_upd), "milestones:", len(df_ms), "actions:", len(df_act), "jira rows:", len(rows))
print("GT inconsistent:", df_gt.gt_inconsistent.sum(), "GT risk:", df_gt.gt_has_risk.sum())
