# Interview notes — Cloud Cost + Reliability Auditor

## 1. "Walk me through a project you built recently."

> I built a read-only CLI that audits an AWS account for cost hotspots,
> untested backups, and basic security hygiene, and writes a
> plain-language report. It runs in demo mode with sample data, or in
> real mode with boto3. The point was to turn the checks I do by hand
> for a Bill Review or a Backup Restore Test into a repeatable tool —
> same checks every time, findings ranked by severity, each one with a
> concrete next step.

## 2. "How did you handle the fact that a backup plan doesn't prove a restore works?"

> That's the key design decision. AWS Backup has no API that says "a
> restore was tested on this date". So the tool reports the plan
> honestly — "plan found, restore test not verified" — and tells the
> user to run a restore test into an isolated location and record the
> result. I didn't fake a green check. A tool that claims a backup is
> fine because a plan exists is worse than no tool at all.

## 3. "What permissions does it need, and why read-only?"

> Read-only only: Cost Explorer, Budgets, Backup, S3 and IAM read
> permissions. An audit tool should never be able to change the thing
> it's auditing — if it runs with the wrong credentials, the worst it
> can do is read. If a service call fails, for example Cost Explorer
> isn't enabled, that check is recorded as skipped and the rest of the
> audit still runs.

## 4. "How would you run this in production, on a schedule?"

> As a scheduled job — for example a weekly Lambda or a GitHub Actions
> cron — writing the JSON report to S3, with an alert only when a
> critical finding appears. The report itself stays human-readable, so
> the person who pays the bill can act on it without opening the AWS
> console. I'd keep the blast radius at zero: same read-only role,
> no write permissions, no secrets in the repo.

## 5. "What would you do differently with more time?"

> Three things: pull Savings Plan and Reserved Instance coverage from
> Cost Explorer so the cost advice is specific, add a check for
> CloudWatch log retention because that's a quiet cost leak, and add a
> second output format — a one-page summary for the owner, with the
> full findings as an appendix. I'd also add a dry-run flag that lists
> the exact API calls before making them.

## Trade-offs

1. **Demo mode vs live data.** Demo mode makes the tool showable in an
   interview with no credentials, but the sample data can go stale.
   The sample file is labelled as sample, and the real-mode checks are
   the same code path, so the demo never pretends to be a real audit.
2. **Severity is a judgement, not a measurement.** "EC2 is 46% of the
   bill" is high severity because concentration is a risk, not because
   46% is a magic number. The thresholds are in the code and easy to
   change per account.
3. **Breadth over depth.** Five checks, done well, beat twenty shallow
   ones. A dedicated security tool would go deeper on IAM and S3; this
   tool's job is to catch the common, expensive mistakes first.
