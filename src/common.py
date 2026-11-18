"""Shared paths and loaders."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"
PROMPTS = ROOT / "prompts"
RESP = ROOT / "responses"
for p in (OUT, PROMPTS, RESP):
    p.mkdir(exist_ok=True)

WORKBOOK = DATA / "releaseops_dataset.xlsx"
FORM_UPDATES = DATA / "form_updates.csv"        # written by ingest_form.py
CALENDAR_EXTRA = DATA / "calendar_extra.csv"    # weeks added by ingest_form.py

RISK_CATEGORIES = ["Schedule", "Quality", "Security", "Commercial", "Dependency"]
FUNCTIONS = ["Legal", "Pricing", "Finance", "Marketing", "Security", "Platform Eng",
             "QA", "Support", "Docs", "Partner"]

DATE_COLS = {"Weekly_Updates": ["submitted_at"],
             "Reporting_Calendar": ["week_ending", "submission_deadline"]}


def week_num(w):
    return int(str(w).lstrip("W"))


def load(sheet: str) -> pd.DataFrame:
    """Reads a sheet from the workbook. Weekly_Updates and Reporting_Calendar also include
    rows added through the form intake (ingest_form.py)."""
    df = pd.read_excel(WORKBOOK, sheet_name=sheet)
    extra = {"Weekly_Updates": FORM_UPDATES, "Reporting_Calendar": CALENDAR_EXTRA}.get(sheet)
    if extra is not None and extra.exists():
        add = pd.read_csv(extra, parse_dates=DATE_COLS[sheet])
        df = pd.concat([df, add], ignore_index=True)
    if sheet == "Weekly_Updates":
        df = df.drop_duplicates(["release_id", "week"], keep="last")   # a form resubmission replaces the earlier one
    return df


def current_week() -> str:
    cal = load("Reporting_Calendar")
    return max(cal["week"], key=week_num)


def as_of() -> pd.Timestamp:
    """Report date = week ending of the latest reporting week."""
    cal = load("Reporting_Calendar")
    return pd.Timestamp(cal["week_ending"].max())


AS_OF = as_of()
