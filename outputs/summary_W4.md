\## Weekly release summary - W4 (as of 2026-11-13)



\*\*Needs a decision\*\*

\- \*\*Query Engine 5.0 (R01):\*\* Should it ship with the 3% join regression documented as a known issue? Deadline and decision-maker not stated.

\- \*\*Data Catalog 1.0 (R04):\*\* Should GA wait for the partner connector, or should 1.0 ship without it and add it in 1.1? Deadline and decision-maker not stated.



\*\*What changed this week\*\*

\- \*\*R04 Data Catalog moved to Red.\*\* The 18 Dec GA is no longer achievable, and 15 Jan is proposed. The partner hasn't returned the T\&Cs, and Legal won't clear GA without them. Legal review is blocked and has slipped 31 days.

\- \*\*R01 Query Engine 5.0:\*\* The GA forecast moved from 4 Dec to 18 Dec. Security sign-off is now expected 4 Dec because the pen-test vendor slot is only available from 1 Dec. The regression is at 3%.

\- \*\*R02 Cloud Connector:\*\* GA is likely to move from 20 Nov to 27 Nov. The Pricing committee outcome from 12 Nov is still pending, and the price list can't be published without an approved SKU.

\- \*\*R05 ML Feature Store:\*\* Platform Eng's v2 identity API slipped from Sprint 46 to Sprint 48, and code freeze moved from 13 Nov to 20 Nov. The 11 Dec GA holds only if QA is compressed to one week.

\- \*\*R07 Connector Pack:\*\* GA moved from 13 Nov to 20 Nov because Salesforce tests are still failing; the SAP connector is fixed. Elsewhere, R08's scheduler deadlock is resolved and verified in QA.



\*\*Who owes what\*\* (all items are overdue)



| Owner | Function | Item | Due | Days overdue |

|---|---|---|---|---|

| Farah Khan | Legal | R04: Chase partner counsel on T\&C redlines | 2026-11-04 | 9 |

| Nisha Agarwal | Finance | R10: Sign-off on metering logic | 2026-11-06 | 7 |

| Deepak Joshi | Engineering | R08: Submit W3 status update | 2026-11-07 | 6 |

| Imran Sheikh | Security | R01: Confirm pen-test slot or alternative vendor | 2026-11-07 | 6 |

| Karan Gupta | Engineering | R05: Submit W3 status update | 2026-11-07 | 6 |

| Rahul Menon | Product | R02: Escalate SKU approval | 2026-11-10 | 3 |

| Sneha Reddy | Engineering | R04: Fix 5 search-indexing P1s | 2026-11-12 | 1 |

| Rohit Bansal | Pricing | R02: Price list draft | 2026-11-12 | 1 |

| Priya Nair | Engineering | R07: Fix Salesforce API v61 failures | 2026-11-12 | 1 |

| Arjun Iyer | Engineering | R10: Close metering gap to 99.9% | 2026-11-12 | 1 |



\*\*Reporting hygiene:\*\* The R10 update from Arjun Iyer is missing, and the R01 update from Vikram Shah was 17.5 hours late. No stale updates are flagged.



\*\*Portfolio:\*\* Of the 8 active releases, 3 are Green (R02, R03, R08), 3 are Amber (R01, R05, R07), 1 is Red (R04) and 1 has no RAG this week (R10). Two releases have shipped and are Green (R06, R09). \*\*R02 reports Green, but its data disagrees:\*\* Pricing approval is blocked with a 9-day slip, and GA is likely moving to 27 Nov.

