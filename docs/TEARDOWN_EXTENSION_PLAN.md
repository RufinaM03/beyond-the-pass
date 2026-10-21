# Teardown behavior and minimal extension proposal

## Current hosting decision — supersedes the historical proposal below

On **22October2026IST**, user requested **at least two weeks** of hosting. Retain the current existing deployment until at least **5November2026 00:01:05IST** (14days from recorded2026-10-21T18:31:05Z checkpoint); do not schedule deletion at that time or stop/delete without subsequent explicit user instruction. The previous21October deadline and infrastructure pause below are superseded. No project automatic teardown exists; no timestamp-driven AWS change is needed to keep the service running. No new service, IAM change, S3 write, model replacement, stack recreation or budget-alert change is made. Using documented~$1.57/day low-traffic assumptions,14days is approximately$22before tax, not a hard cap or actual billing statement. Extra traffic/storage and ongoing hosting afterward remain billable.

Everything below records the earlier inspection/proposal, not current authorization to run deletion.

Prepared **21 October 2026 IST** after the user instructed **no infrastructure changes yet**. This instruction pauses the previously approved application update. No ECR push, S3 write, change-set creation/execution, IAM mutation, stack deletion or application deployment occurred. GitHub update is complete: commit `cdd3680e14963019a23e5de572c0cd3ad95b8d24`, [successful exact-commit CI](https://github.com/RufinaM03/beyond-the-pass/actions/runs/39480516113). Local suite91 Python tests and4 frontend tests pass. The AWS application still runs original task definition `btp-demo-app-app:2`, desired1/running1/pending0.

## 1. What causes teardown

**Only a human running the manual delete command.** The recorded deadline is **21 October 2026, 11:42:53 IST /06:12:53 UTC**. No project scheduler, automatic teardown, TTL or expiration job was implemented. The workflow has push/PR/manual CI triggers only, no scheduled teardown. The running service does not expire at that timestamp. `scripts/aws_app_update.py::DEADLINE` prevents new publication/update at/after the deadline; it does **not** stop or delete an existing deployment. Seven-day log retention, S3 old-version lifecycle and untagged-ECR expiry are unrelated to application teardown. This is project inspection, not an account-wide assertion that nobody has configured external automation.

The existing manual command hashes the original approved plan, then calls CloudFormation DeleteStack and waits for deletion:

```powershell
$approved=(Get-FileHash docs/DEPLOYMENT_PLAN.md -Algorithm SHA256).Hash.ToLowerInvariant()
.\.venv\Scripts\python.exe -m scripts.aws_release delete-app --approved-plan-sha256 $approved
```

**Do not execute it during this review.** No automatic budget-triggered stop is verified. Budget settings/alerts have not been changed or disabled; their presence/effectiveness has not been audited here.

## 2. Exact project removal scope

Read-only actual CloudFormation inventory finds **22 resources** in `btp-demo-app`. Actual deployed template inspection finds **no Retain deletion policies**. On successful deletion, CloudFormation attempts the following, not an instant guaranteed cleanup:

| Logical resource(s) | Effect |
|---|---|
| Service, Cluster, Task | Delete ECS service, stop its app/init task containers, remove cluster; deregister the stack's task definition. Older/inactive task-definition revisions are not promised purged. |
| Distribution | Delete CloudFront distribution E2KD3NUMXZ0BRD. |
| Alb, Http, OriginRule, Targets | Delete btp-demo-alb, HTTP listener, origin-header forwarding rule and btp-demo-targets target group. There is no domain-mode HTTPS listener/certificate in this deployed stack. |
| Logs | Delete `/btp/btp-demo-app` log group and contained application/init logs. |
| ExecutionRole, ApplicationRole | Delete only btp-demo-execution and btp-demo-application roles and their stack-managed policies, not Dev_1 or its policies/boundaries. |
| Vpc, SubnetA, SubnetB | Delete dedicated project VPC and both subnets. |
| AlbGroup, TaskGroup | Delete both project security groups. |
| Routes, InternetRoute, AssociationA, AssociationB | Delete route table/default internet route and both subnet associations. |
| Gateway, GatewayAttachment | Detach/delete the project internet gateway. |

Associated service-managed ALB/task network interfaces and public IP allocations should be released as their owners are deleted. Deletion can fail or take time; inspect final stack status/resources before claiming charges ended. The command does **not** delete `btp-demo-storage`, ECR repository/images, S3 bucket/object versions/bucket policy, administrator-created IAM policies, shared service-linked roles or budget alerts. Retained ECR/S3 storage continues to cost money. Scaling ECS to zero alone would leave ALB/IPv4/storage charges.

Evidence (ignored): `data/tmp/teardown-app-resources.json`, `data/tmp/teardown-template-policies.json`. Actual original image/model/snapshot remain unchanged.

## 3. URL impact

Successful teardown removes the serving service, load balancer and CloudFront distribution. **https://d1qxms20novn1p.cloudfront.net stops serving the application.** A deletion-in-progress response may be an error before removal completes. Local `http://127.0.0.1:8000/` is independent of AWS and is unaffected while its local process is running. Retained ECR/S3 artifacts do not themselves host the dashboard.

## 4. Is a timestamp change sufficient?

There is no running AWS timer to extend. To keep the existing deployment serving, an authorized human must agree a new manual cleanup date and not execute deletion early. A documentation edit alone neither creates automation nor changes an AWS resource. For consistency, also update the bounded application-updater's deadline guard and relevant plan/checkpoint/README notices after explicit approval. No ECS/CloudFront/CloudFormation/IAM/S3 change is needed **merely to continue hosting**. Publishing the new manual-input application remains a separate paused update, not a prerequisite for extension.

## 5. Current ongoing cost estimate

Public official AWS regional Price List JSON was fetched sequentially at **2026-10-20 19:08:24 UTC /21 October00:38:24IST**. Selected rates remain unchanged from the original estimate (ECS source publication changed, its selected rates did not). Exact response hashes/rates: `data/tmp/teardown-pricing/evidence.json`. No billing credentials/API access, credits, free allowances or tax assumptions.

| Item | Rate / basis | Approximate USD per24h |
|---|---|---:|
| One Linux x86 Fargate256CPU/512MiB | 0.25×$0.04256 +0.5×$0.004655 per hour | 0.3112 |
| ALB | $0.0239/hour | 0.5736 |
| Three public IPv4 minimum | $0.005/address-hour | 0.3600 |
| Fixed compute/ALB/IP subtotal | No ALB traffic/storage/logs included | **1.2448** |
| Budget1 average ALB LCU | $0.008/LCU-hour, assumption not measured usage | 0.1920 |
| CloudFront example traffic | 1GB India viewer egress +10k HTTPS +0.01GB toward origin, per example period | 0.1226 |
| ECR/S3/logs/request allowances | Original bounded estimate, not actual billing | ~0.0106 |
| **Illustrative total** | Low demo traffic assumptions | **~1.57/day** |

Original730-hour monthly scenario: **~$44 before tax**, with1GB/10k viewer requests for that whole month, not repeated daily. If the daily illustrative traffic/log quantities repeat every day, the corresponding730-hour scenario is roughly **$47.8/month** instead. Fixed subtotal alone is ~$37.86/730h. These are estimates, not a bill or spending cap. Additional addresses, requests, log volume, LCU load and traffic geography change the amount. Each extra IPv4 adds $0.12/day; no WAF/traffic cap is configured. Retained artifacts cost extra after app deletion. Original $5 allowance does not approve indefinite hosting; extension cost/duration must be explicitly accepted.

Primary sources: [Mumbai Fargate rates](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECS/current/ap-south-1/index.json), [Mumbai ALB rates](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSELB/current/ap-south-1/index.json), [IPv4 pricing](https://aws.amazon.com/vpc/pricing/), [CloudFront rates](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudFront/current/index.json). Storage/log references and original assumptions: `docs/AWS_PRICING.md`, `docs/DEPLOYMENT_PLAN.md`.

## Smallest proposed change — prepared, not applied

**New deadline: awaiting the user's exact date/time (IST).** Do not assume another24h, a month or indefinite operation. After explicit approval of that date and incremental cost:

1. Record one approved extension decision, preserving the original24h approval as historical evidence. Update current deadline notices in PROJECT_STATE.md/README.md and the bounded update plan; no edits to architecture/templates/model/artifacts.
2. Change only `scripts/aws_app_update.py::DEADLINE` to the approved UTC equivalent and rerun the existing boundary tests. Commit/push, obtain exact-commit CI if resuming application publication. The delete command itself has no timer and requires no code/CloudFormation update.
3. Keep manual teardown (no new scheduler/service), budget alerts, IAM, ECR/S3 contents, ECS size/count, ALB and CloudFront untouched. No stack deletion/recreation or AWS write needed to apply this extension.
4. Separately confirm when to resume the already prepared application-only release; do not conflate deadline approval with immediate application deployment.

Until a new date is approved, the original recorded deadline/guard remains in place. All infrastructure/application mutations are paused per the latest user instruction.
