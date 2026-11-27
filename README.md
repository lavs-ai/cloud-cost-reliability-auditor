# Cloud Cost + Reliability Auditor

A read-only Python CLI that audits an AWS account for the three things
that cost small teams the most money and sleep: **cost hotspots,
untested backups, and basic security hygiene**. It writes a
plain-language report a non-technical owner can act on.

Built by Lavanya Bangari (Melbourne, Australia) as a portfolio project
for Senior Cloud Engineer roles. It is the same kind of check behind
the AWS Bill Review and Backup Restore Test offered at
AgentCare Cloud — built as a reusable tool instead of a one-off
spreadsheet.

## What it checks

| Check | Source (read-only) | Finding if… |
|---|---|---|
| Top cost services | Cost Explorer, last 30 days | One service is ≥ 40% of the bill |
| Budget alarms | AWS Budgets | No budget is configured |
| Backup plans | AWS Backup | No plan exists, or a restore test cannot be verified |
| Public S3 buckets | S3 public access block + bucket ACL | A bucket grants access to AllUsers |
| Old access keys | IAM | An active key is older than 90 days |

It never creates, changes, or deletes anything. Every AWS call is a
`list` / `get` / `describe`.

## Run it

Demo mode — no AWS credentials, no network, sample data only:

```bash
python -m app.auditor --demo --output reports/
```

Real mode — needs AWS credentials with read-only permissions
(Cost Explorer, Budgets, Backup, S3, IAM read-only):

```bash
pip install boto3
python -m app.auditor --region ap-southeast-2 --output reports/
```

Output in both modes:

- `reports/report.md` — plain-language report, findings most severe first
- `reports/report.json` — the same findings, machine-readable

## Sample output

```
7 findings (2 critical, 3 high, 1 medium, 1 low)
Report written: reports/report.md
JSON written:   reports/report.json
```

Top findings in demo mode:

- **[CRITICAL] No restore test on record** — a backup plan exists, but no
  restore has ever been tested. A backup that has never been restored is
  unproven.
- **[CRITICAL] One S3 bucket allows public access** — confirm whether
  public access is intended; if not, enable Block Public Access.
- **[HIGH] No budget alarm found** — a cost spike would not trigger an alert.

See [docs/sample-report.md](docs/sample-report.md) for a full example
report. It is labelled as a sample from demo data, not a real client.

## Tests

```bash
python -m pytest app/test_auditor.py
# or, with no extra packages:
python app/test_auditor.py
```

Tests cover severity ranking, demo-data loading, and report generation
in demo mode. They need no AWS credentials.

## What this proves (for a Senior Cloud Engineer interview)

- **Cost control:** Cost Explorer + Budgets, not just "watch the bill".
- **Reliability:** a backup plan is not a restore test — the tool says
  so explicitly, because AWS Backup has no API that proves a restore.
- **Least privilege:** read-only by design; the tool cannot change
  anything even if run with the wrong credentials.
- **Failure handling:** if Cost Explorer is not enabled or a service
  call fails, that check is recorded as skipped, not a crash.
- **Plain-language reporting:** findings are written for the person who
  pays the bill, with a concrete next step each time.
