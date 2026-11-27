#!/usr/bin/env python3
"""Cloud Cost + Reliability Auditor.

Read-only audit of an AWS account: cost hotspots, budget alarms,
backup/restore status, and basic security hygiene. Writes a
plain-language Markdown report and a machine-readable JSON report.

Usage:
    python -m app.auditor --demo --output reports/
    python -m app.auditor --region ap-southeast-2 --output reports/

Demo mode needs no AWS credentials and no network access: it reads
app/sample_data.json, which is clearly labelled sample data.

Real mode needs AWS credentials with read-only permissions
(Cost Explorer, Budgets, Backup, S3, IAM read-only). It makes no
changes to the account: every boto3 call is a read (list/get/describe).
If a service call fails (for example, Cost Explorer is not enabled),
that check is recorded as "unknown" instead of crashing the audit.
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

SAMPLE_FILE = Path(__file__).with_name("sample_data.json")


def severity_rank(finding):
    """Lower number = more severe. Unknown severities sort last."""
    return SEVERITY_ORDER.get(finding.get("severity", "info"), 99)


def sort_findings(findings):
    """Most severe first; stable within a severity."""
    return sorted(findings, key=severity_rank)


def count_by_severity(findings):
    counts = {}
    for f in findings:
        counts[f.get("severity", "info")] = counts.get(f.get("severity", "info"), 0) + 1
    return counts


def load_demo_data():
    with open(SAMPLE_FILE, encoding="utf-8") as fh:
        data = json.load(fh)
    return data


def findings_from_sample(data):
    """Demo mode: findings come from the sample file, already labelled."""
    return list(data.get("findings", []))


def findings_from_aws(region):
    """Real mode: read-only boto3 checks. Each check is guarded so one
    failing service does not stop the rest of the audit."""
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        print("boto3 is not installed. Install it with: pip install boto3",
              file=sys.stderr)
        return [], ["boto3 is not installed"]

    findings = []
    warnings = []

    def add(severity, category, fid, title, detail, recommendation):
        findings.append({
            "id": fid, "severity": severity, "category": category,
            "title": title, "detail": detail, "recommendation": recommendation,
        })

    # --- Cost: top services, last 30 days ---------------------------------
    try:
        ce = boto3.client("ce", region_name=region)
        end = datetime.date.today()
        start = end - datetime.timedelta(days=30)
        resp = ce.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        groups = resp["ResultsByTime"][0]["Groups"]
        totals = []
        for g in groups:
            amount = float(g["Metrics"]["UnblendedCost"]["Amount"])
            totals.append((g["Keys"][0], amount))
        totals.sort(key=lambda x: x[1], reverse=True)
        total = sum(a for _, a in totals)
        if totals and total > 0:
            top_service, top_amount = totals[0]
            share = top_amount / total * 100
            if share >= 40:
                add("high", "cost", "COST-01",
                    f"{top_service} is {share:.0f}% of the bill",
                    f"{top_service} cost ${top_amount:,.2f} of ${total:,.2f} "
                    f"in the last 30 days.",
                    "Check instance sizes against actual use, and price a "
                    "Savings Plan for the steady-state baseline.")
    except (BotoCoreError, ClientError, KeyError, IndexError, ValueError) as exc:
        warnings.append(f"Cost Explorer check skipped: {exc}")

    # --- Budgets: is there any budget alarm? ------------------------------
    try:
        budgets = boto3.client("budgets", region_name=region)
        sts = boto3.client("sts", region_name=region)
        account = sts.get_caller_identity()["Account"]
        resp = budgets.describe_budgets(AccountId=account)
        if not resp.get("Budgets"):
            add("high", "cost", "COST-02", "No budget alarm found",
                "No AWS Budgets are configured, so a cost spike would not "
                "trigger an alert.",
                "Create a monthly budget alarm at 80% of the expected spend, "
                "with an email alert.")
    except (BotoCoreError, ClientError) as exc:
        warnings.append(f"Budgets check skipped: {exc}")

    # --- Backup: plans exist, but is there a restore test? ----------------
    # Backup has no direct "last restore test" API, so this check reports
    # what can be known read-only and is honest about what it cannot prove.
    try:
        backup = boto3.client("backup", region_name=region)
        plans = backup.list_backup_plans().get("BackupPlansList", [])
        if not plans:
            add("critical", "backup", "BACKUP-01",
                "No backup plan found",
                "No AWS Backup plan is configured.",
                "Create a backup plan covering the resources that matter, "
                "then run a restore test.")
        else:
            add("medium", "backup", "BACKUP-01",
                "Restore test not verified",
                f"{len(plans)} backup plan(s) found, but AWS Backup has no "
                "API that proves a restore was tested. This needs a manual "
                "restore test, recorded with the date and result.",
                "Run a restore test into an isolated location, record the "
                "result, and repeat on a schedule.")
    except (BotoCoreError, ClientError) as exc:
        warnings.append(f"Backup check skipped: {exc}")

    # --- S3: buckets that allow public access ------------------------------
    try:
        s3 = boto3.client("s3", region_name=region)
        for bucket in s3.list_buckets().get("Buckets", []):
            name = bucket["Name"]
            try:
                pab = s3.get_public_access_block(Bucket=name)
                blocked = all(pab["PublicAccessBlockConfiguration"].values())
            except (BotoCoreError, ClientError):
                blocked = False
            if not blocked:
                try:
                    acl = s3.get_bucket_acl(Bucket=name)
                    public = any(
                        g.get("Grantee", {}).get("URI", "").endswith(
                            "AllUsers")
                        for g in acl.get("Grants", []))
                except (BotoCoreError, ClientError):
                    public = False
                if public:
                    add("critical", "security", "SEC-01",
                        f"S3 bucket {name} allows public access",
                        f"Bucket '{name}' grants access to AllUsers.",
                        "Confirm whether public access is intended. If not, "
                        "enable Block Public Access and check what was exposed.")
    except (BotoCoreError, ClientError) as exc:
        warnings.append(f"S3 check skipped: {exc}")

    # --- IAM: access keys older than 90 days --------------------------------
    try:
        iam = boto3.client("iam", region_name=region)
        now = datetime.datetime.now(datetime.timezone.utc)
        for user in iam.list_users().get("Users", []):
            for key in iam.list_access_keys(
                    UserName=user["UserName"]).get("AccessKeyMetadata", []):
                if key["Status"] != "Active":
                    continue
                age = (now - key["CreateDate"]).days
                if age > 90:
                    add("high", "security", "SEC-02",
                        f"Access key for {user['UserName']} is {age} days old",
                        f"Active access key for user '{user['UserName']}' "
                        f"was created {age} days ago.",
                        "Rotate the key: create a new key, update the "
                        "workload, confirm it works, then deactivate the old key.")
    except (BotoCoreError, ClientError) as exc:
        warnings.append(f"IAM check skipped: {exc}")

    return findings, warnings


def render_markdown(findings, meta):
    """Plain-language report. `meta` describes the run (demo or real)."""
    counts = count_by_severity(findings)
    lines = [
        "# Cloud Cost + Reliability Audit",
        "",
        f"**Account:** {meta.get('account', 'unknown')}  ",
        f"**Region:** {meta.get('region', 'unknown')}  ",
        f"**Date:** {meta.get('date', '')}  ",
        f"**Mode:** {meta.get('mode', '')}",
        "",
    ]
    if meta.get("label"):
        lines += [f"> {meta['label']}", ""]
    if meta.get("total_cost_usd") is not None:
        lines += [
            f"**Total cost ({meta.get('period', 'last 30 days')}):** "
            f"${meta['total_cost_usd']:,.2f}",
            "",
        ]
    summary = ", ".join(
        f"{n} {sev}" for sev, n in sorted(
            counts.items(), key=lambda kv: SEVERITY_ORDER.get(kv[0], 99))
    ) or "no findings"
    lines += [f"**Findings:** {len(findings)} ({summary})", ""]
    if meta.get("warnings"):
        lines += ["## Warnings", ""]
        for w in meta["warnings"]:
            lines.append(f"- {w}")
        lines.append("")
    lines += ["## Findings (most severe first)", ""]
    if not findings:
        lines += ["No findings. That means the checks that ran found nothing "
                  "to flag — it does not mean the account is fully safe.",
                  ""]
    for f in sort_findings(findings):
        lines += [
            f"### [{f['severity'].upper()}] {f['title']}",
            "",
            f"- **ID:** {f['id']} — **Category:** {f['category']}",
            f"- **What I found:** {f['detail']}",
            f"- **What to do:** {f['recommendation']}",
            "",
        ]
    lines += [
        "## How this audit was done",
        "",
        "Read-only checks only. No resources were created, changed, or "
        "deleted. Cost data comes from Cost Explorer, budgets from AWS "
        "Budgets, backup plans from AWS Backup, bucket access from S3, and "
        "key ages from IAM. A backup plan existing does not prove a restore "
        "works — only a restore test proves that.",
        "",
    ]
    return "\n".join(lines)


def run(demo, region, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()

    if demo:
        data = load_demo_data()
        findings = findings_from_sample(data)
        meta = {
            "account": data.get("account", "sample-account"),
            "region": data.get("region", region),
            "date": today,
            "mode": "demo (sample data)",
            "label": data.get("label"),
            "period": data.get("period"),
            "total_cost_usd": data.get("total_cost_usd"),
            "warnings": [],
        }
    else:
        findings, warnings = findings_from_aws(region)
        meta = {
            "account": "see JSON report (caller identity not printed here)",
            "region": region,
            "date": today,
            "mode": "real (read-only AWS calls)",
            "warnings": warnings,
        }

    findings = sort_findings(findings)
    markdown = render_markdown(findings, meta)
    report = {
        "meta": meta,
        "findings": findings,
        "counts_by_severity": count_by_severity(findings),
    }
    (output_dir / "report.md").write_text(markdown, encoding="utf-8")
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")

    counts = count_by_severity(findings)
    summary = ", ".join(f"{n} {sev}" for sev, n in sorted(counts.items()))
    print(f"{len(findings)} findings ({summary or 'none'})")
    print(f"Report written: {output_dir / 'report.md'}")
    print(f"JSON written:   {output_dir / 'report.json'}")
    if meta.get("warnings"):
        for w in meta["warnings"]:
            print(f"Warning: {w}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only AWS cost + reliability auditor.")
    parser.add_argument("--demo", action="store_true",
                        help="Use sample data; no AWS credentials needed.")
    parser.add_argument("--region", default="ap-southeast-2",
                        help="AWS region for real mode (default: ap-southeast-2).")
    parser.add_argument("--output", default="reports",
                        help="Directory for report.md and report.json "
                             "(default: reports).")
    args = parser.parse_args(argv)
    return run(demo=args.demo, region=args.region, output_dir=args.output)


if __name__ == "__main__":
    sys.exit(main())
