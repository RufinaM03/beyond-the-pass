# Phase 6 deployment plan — Option B APPROVED / NOT DEPLOYED

Prepared 2026-10-19 for account `044854093109`, profile `beyond-the-pass`, region **ap-south-1 (Mumbai)**. User explicitly approved **Option B, default CloudFront viewer HTTPS with HTTP origin, 24 hours after successful deployment and a $5 before-tax planning allowance, not a cap**. Preconditions: administrator attaches scoped IAM access, exact deployment commit passes remote CI, and origin/API/public-surface review passes. No resource creation, ECR push, S3 upload, certificate request or deployment executed yet. A plan hash passed to the manual script acknowledges the independently obtained human approval; it is not authorization by itself. Stop for new approval if resource scope/cost materially changes.

Approval implementation amendment: fixed bucket `btp-demo-artifacts-044854093109-ap-south-1`, ECS cluster `btp-demo-cluster`, service `btp-demo-app`, ALB `btp-demo-alb`, target group `btp-demo-targets` and roles `btp-demo-execution`/`btp-demo-application` allow narrower IAM ARNs. Administrator-created execution/application boundary policies prevent role-policy escalation; these two nonbillable IAM policies add no runtime service or estimated charge. The agent will not create/attach policies or modify its own access. Exact six policy files, wildcard explanations and console steps: `IAM_SETUP.md`. Public origin/cache/API audit: `PUBLIC_SURFACE_REVIEW.md`. Runtime image remains the unchanged verified f668 revision; the new deployment commit versions infrastructure/operator tooling and must independently pass CI.

**Manual teardown:** deployment acceptance UTC +24 hours. Exact successful/deadline timestamps will be recorded only after acceptance. No automatic teardown/scheduler exists. Command: `.\.venv\Scripts\python.exe -m scripts.aws_release delete-app --approved-plan-sha256 $approved`, where `$approved` is the approved plan file SHA256. Then review retained ECR/S3 cleanup below; scaling to zero alone does not stop ALB charges.

## Verified prerequisites and release

- STS authenticated `arn:aws:iam::044854093109:user/Dev_1`; configured profile region is Mumbai. Credentials were neither opened nor printed.
- Current committed HEAD **1fb3961094a78683f25d56d65b8afa302d04a2a1** has [successful CI](https://github.com/RufinaM03/beyond-the-pass/actions/runs/39282257023). The image's runtime revision **f668daf9447f2f97175c7355a9388f47354b2b75** also has [successful CI](https://github.com/RufinaM03/beyond-the-pass/actions/runs/39280918052). The previous queued-run blocker is resolved. New, uncommitted Phase 6 infrastructure/script/CI changes have only local validation, not remote green CI. No commits, pushes or deployment automation added by this phase.
- Preserve `beyond-the-pass:phase5-real`, local image ID `sha256:ef69b2d2b4ac3e75d32744b745318e88e85e921cdfcec01004f139406f6f801f`, Linux amd64, 899,190,202 bytes reported locally. **This is not an ECR digest.** After approval, publish this verified image unchanged; resolve the registry digest and Linux amd64 child manifest, then deploy `repository@sha256:...`, never a mutable tag. ECR-compressed storage/transfer size remains unmeasured.
- Production context `data/package/phase5-real-portable` retains its original source digest `febb635ed5a9efbaf5ae1418dc16a1e9da098fba4214cb4f98b8fedd79f307aa`. Production validation rejects fixtures. Model `btp-exploratory-v1`, data `dvsa-2022-2024-splitmix1000-v1`, trusted manifest SHA256 `56846f43cfc8e23f809d16b27d85b144a8d634f8fa42870d2e6f59df7531fa14` stay unchanged. Four current features, 200 demonstration cases, 936 saved evaluation examples, aggregate-only history, and score-only two-ULP numeric policy remain unchanged.
- Docker Linux engine ready. This phase observed free RAM 4.50 GiB, C: 37.56 GiB, D: 59.96 GiB. No rebuild, training, source download/rescan, Docker reset/prune or storage relocation. Phase 5 startup 25.040 s / memory 166.2 MiB were single observations at **1 CPU**, not evidence that quarter-CPU Fargate will meet startup or production capacity targets.

## Exact infrastructure and networking

Standard CloudFormation JSON, no SAM application, Lambda, API Gateway, Kubernetes, NAT, RDS, EFS, endpoints or extra service:

1. `btp-demo-storage` (`infra/bootstrap.json`): one immutable-tag private ECR repository `btp-demo-app` with AES256 encryption, basic scan-on-push disabled (no enhanced Inspector enrollment); only untagged images expire after 30 days. One fixed-name private S3 bucket `btp-demo-artifacts-044854093109-ap-south-1`, SSE-S3, versioning, bucket-owner enforced ownership, all four public-access blocks, deny non-TLS requests. Abort incomplete uploads after one day; expire noncurrent versions after 30 days. Current release objects remain until explicit cleanup. **ECR, S3 and its TLS bucket policy are retained on stack deletion.** No public artifacts or raw/full datasets uploaded.
2. `btp-demo-app` (`infra/application.json`): dedicated `10.74.0.0/16` VPC, DNS enabled; two /24 public subnets in two **verified distinct account-available zones**; one IGW/attachment, one route table/default internet route, two associations. No existing VPC modified. No separately allocated Elastic IPs.
3. Two SGs: ALB inbound 80/443 from internet in domain mode (80 redirects), or only port 80 from the regional AWS-managed CloudFront origin-facing prefix list in CloudFront mode. ALB outbound TCP8000 limited to the dedicated VPC CIDR. Task inbound **only TCP8000 from ALB SG**; outbound TCP443 internet for ECR/S3/logs via public IP/IGW. No SSH, IPv6, ECS Exec or direct public app ingress. VPC resolver DNS remains available. Public task IPs avoid NAT hourly charges, but are routable addresses: isolation relies on SGs, not private subnets. No task AWS API permissions; execution role alone pulls its one ECR repository and writes its one log group (ECR auth token requires `Resource:*`).
4. One internet-facing IPv4 ALB across both subnets, IP target group HTTP8000, readiness `/api/ready` (30s interval, 10s timeout, 2 healthy/3 unhealthy), 30s deregistration. TLS termination at ALB for option A; ALB→task HTTP on isolated VPC paths in either mode. One ECS cluster, standard Container Insights disabled, one Fargate application task initially, platform 1.4.0, X86_64/Linux, 20 GiB included ephemeral storage. No autoscaling.
5. Candidate `small`: **256 CPU / 512 MiB**. Other valid, separately cost-reviewed choices: `memory` = 256/1024; `cpu` = 512/1024. One existing Uvicorn worker. App user10001, dropped capabilities, read-only root and immutable/query-only SQLite. Fargate does not provide Docker tmpfs: one task-lifetime scratch volume mounts at `/tmp/btp`. A short, nonessential **same-image init container** runs only fixed `os.chmod('/scratch', 0o1777)` as root with **all capabilities dropped**, read-only root; app depends on its successful exit. It is not another service/worker. This preserves the verified image unchanged and solves root-owned Fargate volume permissions. Local Docker verified this exact permission handoff and non-root write/delete, then removed only its newly created volume. Fargate behavior remains to be checked. Scratch is ephemeral disk, not the local 64 MiB tmpfs quota; no writable model/data mount. No ongoing root process.
6. Separate execution and application IAM roles; application role has no attached permissions. One CloudWatch log group `/btp/btp-demo-app`, initial **7-day retention**, stdout/stderr, 1 MiB nonblocking buffer per container; secrets/header values must never be logged. No ALB access-log bucket, detailed monitoring, WAF or paid custom metrics. ECS standard metrics will be read for observed memory/CPU after deployment; enabling Container Insights requires another cost review.
7. ECS rolling deployment min100/max200, desired1: **up to two application tasks temporarily**. Circuit breaker with rollback; first deployment has no previous completed release to roll back to. Grace configurable60–600s, starts120s. ECS container **liveness `/api/health`** (start period120s); ALB **artifact readiness `/api/ready`**. Retune only against measured AWS behavior; a service that rolled back to an old release is not success. Grace is not an application-start guarantee.

## HTTPS decision — user choice still required

User reconfirmed on 2026-10-19: **no domain available**, then explicitly selected **Option B** and accepted its HTTP origin. No domain purchase, ACM certificate or Route53 resources authorized. Option A below remains an unselected comparison only. Provisioning still waits for the user's IAM/CI/security prerequisites.

**A — controlled domain + ACM + ALB (recommended for encrypted public origin).** Supply a domain/subdomain you control and can edit DNS for. Optional `btp-demo-certificate` uses `infra/certificate.json` in Mumbai with DNS validation. Existing Route53 zone ID enables managed validation; otherwise add ACM's exact validation CNAME at your DNS provider while the certificate stack waits. No hosted zone/domain is created by these templates. Supply the issued regional ARN to the app; ALB443 uses TLS1.2/1.3 policy and ALB80 redirects to443. Add DNS alias/CNAME to the ALB (use a subdomain unless provider supports an apex alias). ACM integrated non-exported certificate has no extra certificate charge; domain registration, DNS provider/optional Route53 charges are **not priced until an actual name/provider is chosen**, and are outside the service estimate below. No CloudFront resources in A. Browser→ALB encrypted; ALB→task HTTP inside VPC.

**B — default CloudFront HTTPS hostname, no owned domain.** Adds exactly one conditional distribution, using its AWS certificate/default `*.cloudfront.net` hostname, `PriceClass_All` (India included), pay-as-you-go assumptions. Browser HTTP redirects to HTTPS. **CloudFront→public ALB uses HTTP80, NOT TLS.** No claim of end-to-end encryption; the private origin header travels unencrypted on that leg. This is an explicit demonstration trade-off, not a confidential-data solution. To encrypt that leg use a controlled origin domain + valid cert, requiring a revised hybrid plan. Public ALB AWS hostname cannot obtain a certificate you control. No self-signed workaround.

For B, prefix-list SG restriction plus randomly generated header **name and value**: listener default403; only matching header forwards. `NoEcho` parameters passed through an ignored local file, never CLI literal arguments/logs/Git/S3. Authorized CloudFront/ALB configuration readers can still access these secrets: NoEcho is not a secret vault. Restrict IAM readers, rotate through a reviewed update, never log them. Prefix-list restriction alone does not restrict to *your* distribution; the header provides that additional control. Global managed list consumes SG quota weight55; verify regional ID and sufficient rule quota after permissions are fixed. ALB direct internet access should time out due to SG; other distributions without the secret should receive403.

Caching disabled **for the entire distribution**, including `/api/*`, using official managed CachingDisabled policy. Forward all viewer query strings/cookies/headers except Host via AllViewerExceptHostHeader; CloudFront sets origin Host. Allow all seven HTTP methods (API supports only its documented subset), POST body forwarded, OPTIONS forwarded, HTTPS redirects, error caching TTL0 for configured errors. No SPA error-page substitution: API/asset404s remain404s. No origin domain/DNS/certificate required by B, but origin HTTP must be expressly accepted. No cache invalidation costs assumed.

AWS implementation references: [valid Fargate sizes](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html), [ephemeral bind-mount permissions](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/bind-mounts.html), [CloudFront ALB restrictions](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/restrict-access-to-load-balancer.html), [managed cache policies](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-cache-policies.html), [request forwarding policies](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-origin-request-policies.html). No resource has been tested in AWS yet.

## Current official prices and estimate (USD, before tax)

Retrieved **2026-10-19** from official AWS regional Price List files, not US-East pricing or a third-party calculator. Exact source paths, publication dates, SHA256 and selected SKUs are recorded in `docs/AWS_PRICING.md`; raw responses stay ignored under `data/tmp/aws-pricing`. Sources are linked there and below. No promotional credits, account free-tier allowances, committed discounts or currency conversions assumed. Refresh before approval if delayed; these are estimates, not a cap.

Assumptions: one continuously running Linux x86 quarter-CPU/0.5GiB task; two ALB public IPv4 addresses plus one task address **minimum**; budget average **1 ALB LCU** (not an asserted minimum/measurement), 1GB ECR billed storage allowance, 0.01GB total current/noncurrent S3 artifacts, 100 S3 PUT/LIST +100 GET requests per period, 1GB viewer egress per period. Logs: 0.01GB ingestion/retained storage for 24h, 0.1GB for month; full retained amount costed conservatively despite seven-day expiry. Storage prorated 24/730 for daily column. B additionally assumes10,000 HTTPS requests and0.01GB request-body transfer toward origin per period, all served from India pricing. Other viewer locations have different rates; no traffic ceiling is configured. Month =730h, not a promise about calendar length.

| Item / current rate | 24h | 730h month |
|---|---:|---:|
| Fargate: $0.04256/vCPU-h + $0.004655/GiB-h | $0.3112 | $9.4663 |
| ALB: $0.0239/h | $0.5736 | $17.4470 |
| ALB usage budget:1 LCU × $0.008/h | $0.1920 | $5.8400 |
| Public IPv4:3 × $0.005/address-h | $0.3600 | $10.9500 |
| ECR:1GB × $0.10/GB-month | $0.0033 | $0.1000 |
| S3 Standard:0.01GB × $0.025/GB-month | <$0.0001 | $0.0003 |
| S3 requests:$0.005/1000 PUT; $0.0004/1000 GET | $0.0005 | $0.0005 |
| Logs:$0.67/GB ingestion + $0.03/GB-month retained | $0.0067 | $0.0700 |
| A:1GB Mumbai internet egress × $0.1093/GB | $0.1093 | $0.1093 |
| **A service subtotal, excludes domain/DNS** | **$1.56** | **$43.98** |
| B replaces A egress:1GB × $0.109 +10k HTTPS × $0.012/10k +0.01GB × $0.16 to origin | $0.1226 | $0.1226 |
| **B service subtotal, no owned domain, origin HTTP** | **$1.57** | **$44.00** |

No fixed charge for VPC/subnets/IGW, separate IAM roles, ECS cluster orchestration on Fargate, included20GiB storage or integrated ACM certificate. Standard CloudFormation resources have no extra orchestration fee. S3 SSE-S3 avoids KMS requests. Same-region ECR pulls assumed; S3/ALB→CloudFront origin transfer waived per AWS pricing, not double-counted as internet egress. No ALB reserved-LCU commitment. Request/upload/health-probe load contributes to LCU; actual usage is the maximum of LCU dimensions, not a guaranteed1LCU. AWS may scale ALB nodes/public addresses; each additional address adds $0.12/day / $3.65/month. Actual ECR compressed size, logs, requests and data transfer must be measured.

Rolling overlap allowance: one extra task plus its IPv4 for15min = **$0.0045** at small size, before any incremental LCU/transfer/logs. Failures/retries can extend this; 2h extra task/IP ≈$0.0359. B's distribution provisioning time may also keep ALB/task resources running beyond the intended test duration. Increasing to256/1024 adds ~$1.70/month compute;512/1024 adds ~$9.47/month compute, before overlap. Do not resize without demonstrated need/review.

**Proposed first approval: a manually monitored 24-hour deployment, $5 planning allowance before tax, then explicit cleanup review**; or approve ongoing ~$44/month service baseline with a $55 planning allowance before tax. These allowances are not enforced ceilings. Public unauthenticated demo/API has no WAF/rate-limiting cost or traffic guarantee. Unexpected traffic, scaling, forgotten resources and retries can exceed them. AWS Budgets alerts (not created here) are delayed notifications, **not a spending cap**. Scaling ECS to zero leaves ALB, its IPv4 addresses, ECR, S3 and retained logs billable. Full app-stack deletion is needed to stop the main hourly charges; retained storage still costs money.

Official pricing pages: [Fargate](https://aws.amazon.com/fargate/pricing/), [ALB/LCU](https://aws.amazon.com/elasticloadbalancing/pricing/), [IPv4](https://aws.amazon.com/vpc/pricing/), [ECR](https://aws.amazon.com/ecr/pricing/), [S3](https://aws.amazon.com/s3/pricing/), [logs](https://aws.amazon.com/cloudwatch/pricing/), [CloudFront](https://aws.amazon.com/cloudfront/pricing/), [transfer](https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer). Region-specific rates come from the linked official machine-readable files, not example prices on these pages.

## Permissions — blocker, do not attach AdministratorAccess

Actual access denied for this IAM user: **ec2:DescribeAvailabilityZones**, **ec2:DescribeManagedPrefixLists**, **cloudformation:ListStacks**, **cloudformation:ValidateTemplate** (no identity-policy allow). STS success does not establish deployment rights. No broad account-resource audit performed, no assumption that this AWS account is empty. Server-side validation remains pending; local cfn-lint passes. An authorized administrator must review a least-privilege deployment policy/execution role rather than attach AdministratorAccess.

Required operation families, constrained to this account/region/project resources wherever AWS supports resource scoping:
- Read-only preflight: STS identity; CloudFormation ValidateTemplate/DescribeStacks/DescribeStackEvents/ListStacks/GetTemplate; EC2 DescribeAvailabilityZones/DescribeManagedPrefixLists/DescribeSecurityGroups/DescribeNetworkInterfaces; ECS DescribeClusters/DescribeServices/ListTasks/DescribeTasks/DescribeTaskDefinition; ELB DescribeTargetHealth/DescribeLoadBalancers/DescribeListeners; CloudWatch GetMetricStatistics/ListMetrics and Logs DescribeLogStreams/GetLogEvents. Service quotas for Fargate task/vCPU capacity and SG prefix-list weights must be checked. Some describe/list/create actions require wildcard resources; this is not a justification for wildcard admin.
- Operator's approved writes: CloudFormation Create/Describe/Execute/DeleteChangeSet, Create/Update/DeleteStack; ECR GetAuthorizationToken plus scoped BatchCheckLayerAvailability/InitiateLayerUpload/UploadLayerPart/CompleteLayerUpload/PutImage/DescribeImages/BatchGetImage/GetDownloadUrlForLayer for `btp-demo-app`; S3 PutObject/GetObject/GetObjectVersion limited to the generated artifact bucket/release prefix. Optional scoped cleanup requires ListBucketVersions/DeleteObject/DeleteObjectVersion, ECR BatchDeleteImage/DeleteRepository.
- CloudFormation provisioning principal needs service-specific create/update/tag/delete/describe for the **exact resource types in these templates**: VPC/subnets/IGW/route table/routes/associations/SG rules; ECR repository/lifecycle/encryption; S3 bucket/versioning/encryption/public block/ownership/lifecycle/policy; ECS cluster/task definitions/service; ELBv2 load balancer/listeners/rules/target group/attributes; Logs group/retention; IAM Create/Get/Tag/DeleteRole and Put/Get/DeleteRolePolicy for the two stack-generated roles. IAM PassRole limited to these roles, **iam:PassedToService = ecs-tasks.amazonaws.com**. May require CreateServiceLinkedRole conditioned to `ecs.amazonaws.com` / `elasticloadbalancing.amazonaws.com` if absent. Do not create or grant a more privileged CloudFormation execution role as a workaround.
- A: ACM RequestCertificate/DescribeCertificate/DeleteCertificate; Route53 change only the approved existing zone if managed validation/DNS selected. B: scoped CloudFront Create/Get/Update/DeleteDistribution/TagResource plus read managed policy metadata and the regional CloudFront prefix list. CloudFront is global even though the stack is Mumbai. No AWS OIDC deploy role or GitHub cloud secrets this phase.

This is an administrator review checklist, **not a claimed complete or tested IAM policy**. Effective permissions, boundaries/SCPs, quotas, available AZs/prefix-list ID, ECR scanning account settings and name conflicts remain to be verified before bootstrap. A denied permission is a blocker, not permission to weaken isolation.

## Exact commands and dependency order (NOT executed unless marked)

Run from project root, using Python3.12 on D:. Keep generated paths ignored; never print the parameter file (it contains random origin credentials). Do not type secrets in chat/CLI. `scripts.aws_release` checks the expected account before AWS operations; mutating actions require the current human-approved plan hash. Pure local validation and parameter preparation need no provisioning authorization.

```powershell
# Local validation; executed successfully during preparation:
.\.venv\Scripts\python.exe -m scripts.aws_release validate
.\data\tools\cfn\Scripts\cfn-lint.exe -r ap-south-1 -t infra/*.json
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m scripts.package_release validate --mode release --context data/package/phase5-real-portable
# Reproduce isolated infrastructure validator, never install into serving venv:
$env:TEMP="$PWD\data\tmp"; $env:TMP=$env:TEMP; $env:PIP_CACHE_DIR="$PWD\data\cache\pip"
.\.venv\Scripts\python.exe -m venv data/tools/cfn
.\data\tools\cfn\Scripts\python.exe -m pip install -r requirements-infra.lock
# After scoped permissions are granted (read-only; prior calls denied):
aws ec2 describe-availability-zones --profile beyond-the-pass --region ap-south-1
aws ec2 describe-managed-prefix-lists --profile beyond-the-pass --region ap-south-1 --filters Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing
aws cloudformation validate-template --profile beyond-the-pass --region ap-south-1 --template-body file://infra/application.json
```

**Only after explicit approval**, set `$approved` to the SHA256 of the approved `docs/DEPLOYMENT_PLAN.md` (the validate command prints it). A changed plan needs renewed review. This variable is not an AWS credential. No script is invoked automatically by CI.

```powershell
$approved = (Get-FileHash docs/DEPLOYMENT_PLAN.md -Algorithm SHA256).Hash.ToLowerInvariant()
.\.venv\Scripts\python.exe -m scripts.aws_release bootstrap --approved-plan-sha256 $approved
.\.venv\Scripts\python.exe -m scripts.aws_release publish --approved-plan-sha256 $approved
```

`publish` revalidates the real context/fixtures gate, checks the exact local image ID/architecture/code/artifact labels, uses password-stdin (no printed token), pushes an immutable code tag, queries ECR digest, verifies Linux amd64 manifest and logs out. It records `data/tmp/aws-published.json`, uploads only the bounded release tar/checksum record to private S3, not archives/full cohort. It does not build a substitute image. If interrupted, inspect ECR/S3 for partial completion before retrying an immutable tag; no destructive auto-cleanup. Preserve the release record for rollback, never overwrite it without archiving the prior approved record.

**A only, optional certificate first** (use actual controlled domain; no sample fake domain is a deployment input):

```powershell
# Set $domain to the controlled subdomain; HostedZoneId omitted means manual DNS.
aws cloudformation deploy --profile beyond-the-pass --region ap-south-1 --stack-name btp-demo-certificate --template-file infra/certificate.json --parameter-overrides DomainName=$domain
# While waiting, a second terminal can list/describe this requested certificate,
# add its exact validation CNAME at your provider, then await ISSUED.
aws acm list-certificates --profile beyond-the-pass --region ap-south-1
aws acm describe-certificate --profile beyond-the-pass --region ap-south-1 --certificate-arn $certificateArn
```

Set `$zoneA`/`$zoneB` from successful account AZ discovery, not guessed zone names. Set `$certificateArn` from the **issued** Mumbai certificate or `$prefixListId` from successful prefix-list discovery. Prepare exactly one HTTPS branch (local ignored file; refuses overwrite to prevent accidental header rotation):

```powershell
# A:
.\.venv\Scripts\python.exe -m scripts.aws_release parameters --https domain --zone-a $zoneA --zone-b $zoneB --certificate $certificateArn
# OR B, only if HTTP origin explicitly approved:
.\.venv\Scripts\python.exe -m scripts.aws_release parameters --https cloudfront --zone-a $zoneA --zone-b $zoneB --prefix-list $prefixListId
# Restrict data/tmp/aws-parameters.json ACL to the operator; don't echo its contents.
.\.venv\Scripts\python.exe -m scripts.aws_release deploy --approved-plan-sha256 $approved
.\.venv\Scripts\python.exe -m scripts.aws_release status
```

Domain DNS alias/CNAME must then point to the output ALB name. `deploy/status` waits for stable ECS, checks actual task definition, running/pending counts, HEALTHY app, actual digest against the published Linux manifest, and healthy ALB targets; this is **not yet HTTPS/application acceptance**. Record any drain/startup retries rather than declaring success early. Service/version checks must also pass the checklist below. CloudFormation's circuit breaker is not proof that the intended release is running.

### After-approval acceptance, not performed yet

- Save stack/resource IDs, endpoint, ECR top-level and Linux digest, immutable local/source manifest and runtime code/artifact versions. HTTPS with a valid chain and HTTP redirect; A DNS and certificate, or B CloudFront deployed/default certificate and deliberate HTTP origin. Check direct ALB bypass blocked in B without logging origin credentials.
- GET `/api/health`, `/api/ready`, `/api/versions`: expected baked code `f668...`, fixturefalse, manifest hash, model/data versions, 200/936. HTTPS production HTML, actual built JS/CSS, all SPA routes; missing assets/API remain404, never cached SPA200.
- Compare an actual case POST prediction against the unchanged local release with `backend.app.predictions_agree` (score-only ≤2ULP, every other field exact), preferably all200; saved `/api/evaluation` byte-equivalent JSON to the trusted metrics. Queue capacity0/10/500 and pagination/bounds/unknown cases, deterministic score/case-ID order, 200-case limit independent of936 evaluation. Use complete query strings through B to test forwarding. Verify POST/validation and aggregate-only index history, no fabricated timelines/outcome inputs.
- Inspect task ENI public IP via ECS/EC2 read APIs; attempt TCP8000 externally (`Test-NetConnection $taskPublicIp -Port 8000`) and require blocked, alongside SG inspection. Successful ALB access does not prove this. Do not open ingress to make a probe pass.
- Inspect only bounded app/init logs without secrets; collect actual ECS standard MemoryUtilization/CPUUtilization and timestamps for stable startup. Compute observed task memory against allocated memory; record intervals, not a peak/capacity guarantee. `/api/ready` success verifies artifacts; image pull/init/startup and quarter-CPU behavior still need AWS evidence. Stop/clean up failed resources with approval, do not keep retrying quota/IAM errors.

### Rollback and cleanup (manual, destructive only with approval)

Rollback before a second release: first deployment has **no previous successful ECS version**; failed CloudFormation resources may need stack deletion. For a later reviewed release preserve its previous approved `aws-published.json` outside the current record and reapply the previous digest/parameters through CloudFormation (do not leave ECS in manual drift). Current script intentionally accepts only this plan's pinned code/artifact; another code version needs a reviewed script/plan, not a fixture override. A rollback to this exact approved release can use:

```powershell
.\.venv\Scripts\python.exe -m scripts.aws_release rollback --record data/tmp/previous-approved-published.json --approved-plan-sha256 $approved
# Repeat HTTPS/version/digest acceptance, not just stable-service checks.
# Delete application resources, including CloudFront if B, after approved cleanup:
.\.venv\Scripts\python.exe -m scripts.aws_release delete-app --approved-plan-sha256 $approved
```

CloudFront disable/deletion propagation can take time; await stack-delete-complete and inspect failure events before concluding hourly charges stopped. App deletion removes service/tasks/ALB/network/IAM/log group; log evidence must be saved first if required. Optional certificate cleanup after listeners are removed:

```powershell
aws cloudformation delete-stack --profile beyond-the-pass --region ap-south-1 --stack-name btp-demo-certificate
aws cloudformation wait stack-delete-complete --profile beyond-the-pass --region ap-south-1 --stack-name btp-demo-certificate
```

Remove only this app's DNS records at the provider; do not delete a shared zone/domain. Bootstrap deletion deliberately retains ECR/S3: get its outputs **before deleting its stack**, inspect exact repository name and bucket, and separately approve loss of rollback artifacts. To erase all retained artifacts, list bucket versions/delete markers and feed only those verified keys/version IDs through `s3api delete-objects` (≤1000/version batch); `aws s3 rm --recursive` alone is insufficient for a versioned bucket. The following commands are for **separately approved destructive cleanup only**. Set `$artifactBucket` from that exact stack's output and `$reviewedVersionBatchFile` to an ignored local JSON file with `Objects` entries of `Key`/`VersionId` taken from that bucket's listing. Do not invent IDs or use an unrelated bucket. Review each batch before deleting, repeat until both versions and delete markers are empty, then delete the bucket:

```powershell
aws cloudformation describe-stacks --stack-name btp-demo-storage --profile beyond-the-pass --region ap-south-1 --query 'Stacks[0].Outputs'
aws s3api list-object-versions --bucket $artifactBucket --profile beyond-the-pass --region ap-south-1
aws s3api delete-objects --bucket $artifactBucket --delete "file://$reviewedVersionBatchFile" --profile beyond-the-pass --region ap-south-1
aws s3api delete-bucket --bucket $artifactBucket --profile beyond-the-pass --region ap-south-1
aws ecr delete-repository --repository-name btp-demo-app --force --profile beyond-the-pass --region ap-south-1
aws cloudformation delete-stack --stack-name btp-demo-storage --profile beyond-the-pass --region ap-south-1
aws cloudformation wait stack-delete-complete --stack-name btp-demo-storage --profile beyond-the-pass --region ap-south-1
```

Alternatively retain storage and record continuing charges. Never run broad account-wide cleanup, Docker pruning or delete unrelated resources. Recheck remaining stack/resources and billing afterward; billing is delayed.

## Approved choice and outstanding prerequisites

1. **B selected and HTTP origin accepted.** $5 before-tax planning allowance /24 hours after successful deployment approved, not a hard cap.
2. Authorized administrator must create the boundary policies and attach the four scoped deployment policies described in `IAM_SETUP.md`. No agent self-grant, AdministratorAccess or permission-boundary bypass.
3. Commit/push reviewed Phase 6 files, obtain exact-commit green remote CI, recheck IAM/quota/name/server-template prerequisites. Check structural origin/API audit before provisioning; execute live checks after provisioning. New paid resources or a materially changed estimate require another review.

Until these pass: **no provisioning; no public URL, resource IDs, ECR registry digest, AWS memory observation or deployment/HTTPS success claimed.** Phase 7 automated deployment remains out of scope.
