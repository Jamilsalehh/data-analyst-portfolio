# Jamil Saleh · Data Analyst Portfolio

I'm an Operations & Data Reporting Associate at a Lebanese digital payments company. I build the pipelines and dashboards that operations, support and partner teams use every day. Before that I worked in after-sales support and quality assurance at the same company, so I know what happens behind the numbers.

**Tools:** SQL (BigQuery) · Power BI (DAX, Power Query) · Looker Studio · Google Sheets & Apps Script · Excel · Power Automate · Power Apps
**Based in:** Beirut (GMT+3) · open to remote work · [LinkedIn](https://www.linkedin.com/in/jamil-saleh-bb4b26266) · Jamil200316@gmail.com

> **About the data:** Every project here runs on **synthetic data**. Projects 1–5 rebuild work I did on the job. I recreated them on generated data for a fictional wallet, "Northwind Pay", because the real data is confidential. Project 6 is a personal project. Each folder includes the script that generated its data.

---

## Projects

| # | Project | Business question | Tools | Headline finding |
|---|---|---|---|---|
| 1 | [Contact Center Performance](01-contact-center-performance) · [live dashboard](https://lookerstudio.google.com/reporting/ec5d03d7-f557-4b7f-9f77-3b7b0cb357e8) | Why did phone service drop over the summer, and where are callers giving up? | SQL · BigQuery · Looker Studio | Answer rate fell from 90% to 78% when the team shrank. 44% of abandoned calls happen during 2 lunch hours. |
| 2 | [Cross-border Payout Failure Monitoring](02-payout-failure-monitoring) | Why do international payouts fail, and who should fix each failure? | Power BI · DAX · Power Query | 61% of failures are wrong receiver details. 76% of manual retries were on errors a retry can't fix. |
| 3 | [Card Top-up Failure Investigation](03-card-topup-investigation) | One bank's cards stopped working. Whose problem is it, and what is it costing? | SQL (CTEs, window functions) | 0 of 3,888 top-ups accepted across 3 gateways points to the issuer, not the gateways. About $231K of top-ups were blocked. |
| 4 | [Agent-Network Collections Pipeline](04-agent-collections-pipeline) | Turn messy monthly exports into a trusted dashboard, and find growth in it | Google Sheets · Apps Script · Looker Studio | A tested, re-runnable pipeline with data-quality checks. Regular agents cross-sell insurance at 29%, against 76% at branches. |
| 5 | [QA Scorecard Automation](05-qa-scorecard-automation) | Get QA feedback to agents while it still matters | Microsoft Forms · Power Automate · Excel · Power BI | Feedback time went from 5 days to 2 minutes. Repeat mistakes fell from 48% to 9%. |
| 6 | [Digital Wallet Retention & Cohorts](06-wallet-retention-cohorts) | Which users stay, and which acquisition channels pay back? | SQL · Power BI | Users who pay a bill in their first 14 days retain 1.8× better. Social ads return $0.42 per $1 spent. |

## Skills by project

| | SQL | Power BI / DAX | Looker Studio | Sheets / Apps Script | Excel | Power Automate / Apps | Data cleaning | Stakeholder write-up |
|---|---|---|---|---|---|---|---|---|
| 1 Contact center | ● | | ● | | | | ● | ● |
| 2 Payout failures | | ● | | | | | ● | ● |
| 3 Card top-ups | ● | | ○ | | | | ● | ● (escalation note) |
| 4 Collections pipeline | | | ● | ● | | | ● | ● |
| 5 QA automation | | ● | | | ● | ● | | ● |
| 6 Wallet retention | ● | ● | | | | | | ● |

● main focus · ○ optional extra

## How each project is organised
```
README.md        the case study: problem → approach → findings → recommendation
BUILD_GUIDE.md   how the dashboard/flow is built, with the numbers to expect
data/            synthetic CSVs
sql/ or apps_script/ or FLOW_SPEC.md   the actual work
scripts/         how the synthetic data was generated + chart scripts
images/          charts and dashboard screenshots
```
