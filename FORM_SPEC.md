# TPM weekly status form: setup (about 20 minutes)

Use **Microsoft Forms** (forms.office.com, free with a personal Microsoft account) or Google Forms.
Title: **Weekly TPM Status Update**

| # | Question (use this wording) | Type | Settings |
|---|---|---|---|
| 1 | Release | Choice (dropdown) | Required. Options exactly as below |
| 2 | Reporting week | Choice (dropdown) | Required. W5, W6, W7, W8 |
| 3 | Your name | Text | Required |
| 4 | RAG status | Choice | Required. Green / Amber / Red |
| 5 | % complete | Text, number restriction 0–100 | Required |
| 6 | Status update | Long text | Required. Help text: "What changed, what's blocked, what you need, and from whom." |

Release options (the import reads the `R01`-style ID, so keep it at the start):
```
R01 - Query Engine 5.0
R02 - Cloud Connector 3.1
R03 - Admin Console 2.4
R04 - Data Catalog 1.0
R05 - ML Feature Store 2.2
R06 - Query Engine 4.9.2
R07 - Connector Pack 3.0.5
R08 - Workload Manager 6.1.1
R09 - Auth Service 2.8-HF1
R10 - Billing Integration 1.3
```

## Collect and import
1. Submit 4–6 test responses yourself as different TPMs for **W5**. Include one late one and one "Green but blocked" one.
2. Microsoft Forms: **Responses → Open in Excel** → save the file into the project folder.
   Google Forms: **Responses → Download responses (.csv)**.
3. Run:
   ```
   python src/run_weekly.py --form "Weekly TPM Status Update.xlsx"
   ```
   Invalid rows (unknown release, bad RAG, empty text) are rejected with a reason in `outputs/ingest_rejected.csv`.
   A resubmission for the same release + week replaces the earlier one.

To try it without building the form: `python src/run_weekly.py --form samples/sample_ms_forms_export.xlsx`
(8 rows: 1 resubmission, 2 invalid). **This adds a W5 to your data.** To undo it, delete
`data/form_updates.csv` and `data/calendar_extra.csv`.

## Power BI
In Power Query, **Append** `data/form_updates.csv` to `Weekly_Updates`, and `data/calendar_extra.csv` to `Reporting_Calendar`.

## Known limitation (say it if asked)
The form updates the status text and RAG only. Milestone and action-item data is a static snapshot (as of 13 Nov).
In a real setup it would be refreshed from a weekly Jira export. So in W5, "Green but data disagrees" can fire on
milestone data that is a week old.
