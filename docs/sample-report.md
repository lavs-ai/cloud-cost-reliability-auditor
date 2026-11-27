# Example report — sample output

> **This is a sample report generated from demo data (`--demo`). It is not a real AWS account and not a real client.**



Generated with:



```bash

python -m app.auditor --demo --output reports/

```



---



# Cloud Cost + Reliability Audit

**Account:** sample-account  
**Region:** ap-southeast-2  
**Date:** 2026-11-27  
**Mode:** demo (sample data)

> SAMPLE DATA ONLY — generated for demo mode. Not a real AWS account, not a real client.

**Total cost (last 30 days (sample)):** $892.50

**Findings:** 7 (2 critical, 3 high, 1 medium, 1 low)

## Findings (most severe first)

### [CRITICAL] No restore test on record

- **ID:** BACKUP-01 — **Category:** backup
- **What I found:** One backup plan was found, but no restore test date is recorded in the sample data. A backup that has never been restored is unproven.
- **What to do:** Run a restore test into an isolated location, record the result (pass/fail, time taken), and repeat on a schedule.

### [CRITICAL] One S3 bucket allows public access

- **ID:** SEC-01 — **Category:** security
- **What I found:** Bucket 'sample-public-assets' is recorded as publicly accessible in the sample data.
- **What to do:** Confirm whether public access is intended. If not, enable Block Public Access on the bucket and check what was exposed.

### [HIGH] EC2 is 46% of the sample bill

- **ID:** COST-01 — **Category:** cost
- **What I found:** Amazon Elastic Compute Cloud - Compute cost $412.18 in the sample period, 46.2% of the $892.50 total. No Savings Plan or Reserved Instance coverage is recorded in the sample data.
- **What to do:** Check instance sizes against actual CPU/memory use, and price a Savings Plan for the steady-state baseline before committing.

### [HIGH] No budget alarm found

- **ID:** COST-02 — **Category:** cost
- **What I found:** No AWS Budgets alarm is recorded in the sample data, so a cost spike would not trigger an alert.
- **What to do:** Create a monthly budget alarm at 80% of the expected spend, with an email alert.

### [HIGH] Access key older than 90 days still active

- **ID:** SEC-02 — **Category:** security
- **What I found:** User 'sample-deploy-user' has an active access key that is 214 days old in the sample data.
- **What to do:** Rotate the key: create a new key, update the workload, confirm it works, then deactivate the old key.

### [MEDIUM] Backup vault without a lifecycle rule

- **ID:** BACKUP-02 — **Category:** backup
- **What I found:** Vault 'sample-vault' has no lifecycle rule in the sample data, so old recovery points are kept indefinitely.
- **What to do:** Add a lifecycle rule that moves older recovery points to cold storage and then expires them.

### [LOW] CloudWatch is 6% of the sample bill

- **ID:** COST-03 — **Category:** cost
- **What I found:** Amazon CloudWatch cost $54.32 in the sample period. Log retention is not recorded in the sample data.
- **What to do:** Check log retention periods and drop verbose log groups to 14 or 30 days where long retention is not needed.

## How this audit was done

Read-only checks only. No resources were created, changed, or deleted. Cost data comes from Cost Explorer, budgets from AWS Budgets, backup plans from AWS Backup, bucket access from S3, and key ages from IAM. A backup plan existing does not prove a restore works — only a restore test proves that.
