# Manual prediction: bounded application update

2026-10-21 (Asia/Calcutta). User requested GitHub and AWS update. This is an application-only proposal, not an extension of hosting or broader provisioning approval.

- Existing account044854093109, Mumbai, stack btp-demo-app, repository btp-demo-app. Keep CloudFront E2KD3NUMXZ0BRD, ALB, networking, roles, logging, task sizing256/512 and one desired task unchanged. Existing rolling policy briefly permits two tasks. No new paid service, IAM change, model/data refresh or source download.
- Publish only the verified real image `beyond-the-pass:manual-local-v2`, ID `sha256:dc6e5fa4d40ec2364c9503dd491d29d4512c21cfd6fa221a105b3bb0ca4f3888`, from `data/package/manual-local-v2`. Source/package digest `1552c00ab006d1112642039a2960e2ea4a3dbc53e0914c0392cdf3a331afa292`; baked code identity is honestly `working-tree-<digest>`, not falsely relabelled as a Git SHA. Record exact green deployment commit separately and verify all staged source files against that committed working tree.
- Trusted artifact btp-exploratory-v1, manifest56846f43cfc8e23f809d16b27d85b144a8d634f8fa42870d2e6f59df7531fa14 remains byte-identical inside the new image. Reuse the original S3 release and original publication record as artifact provenance only. **No S3 writes or new publication prefix**, no new IAM permissions, no pretending the original S3 archive contains the new application. New application provenance is its ECR digest + exact CI commit + source digest, retained in ignored local update record.
- Use the existing stack template and `UsePreviousValue` for every parameter except ImageUri and CodeVersion. Never load, print or rotate origin secret values. Reject change sets unless they modify exactly Task (AWS::ECS::TaskDefinition, replacement) and Service (AWS::ECS::Service, no replacement). Stop for changed scope or material cost change. Existing original publisher/deployer pins are not changed or bypassed; separate bounded updater checks this plan and exact pins explicitly.
- Fresh actual routing inspection passed: all-path CloudFront POST allowed, CachingDisabled4135ea2d-6df8-44a3-9df3-4b5a84be39ad, AllViewerExceptHostHeader b689b0a8-53d0-40ab-baf2-68738e2966ac, HTTPS redirect, no extra behaviors; header-gated ALB forward and default fixed response. Body/Content-Type reach origin. Manual API is bounded/no-store and no other mutations/uploads enabled. No secret-bearing fields retained in diagnostic output. Safe evidence `data/tmp/manual-deployed-routing.json`, `manual-deployed-alb-routing.json`.
- Existing repository-scoped ECR publication and stack-scoped CloudFormation permissions should cover this operation; actual calls remain authoritative. Never self-grant or weaken boundaries if denied. Dev_1 viewing policies do not confer deployment authorization.
- Existing $5 before-tax allowance remains a planning allowance, not a cap. New image adds one bounded ECR image sharing unchanged layers; rolling overlap is bounded by existing circuit breaker. No duration extension: **manual teardown2026-10-21 06:12:53UTC /11:42:53IST**, no automatic teardown. Updater refuses mutation at/after that deadline.
- Before mutation: human confirms this plan, audited code-only commit/push, exact successful CI, trusted local release and real Docker reports. Afterward verify ECS digest, actual HTTPS readiness/versions, all200 comparisons, manual POST validation/parity, deterministic queue, unchanged936 metrics and browser flow. Preserve old image/record for rollback. Do not prune/delete rollback artifacts.

## Commands

The deployed template restricts CodeVersion to a 40-character Git SHA and uses it only for task tags/stack output. Set that parameter to the exact green deployment commit. The immutable image label and API runtime code_version remain the original verified `working-tree-<digest>`; record both identities honestly. No template/schema change or rebuild is required.

```powershell
$env:TEMP="$PWD\data\tmp"; $env:TMP=$env:TEMP
$env:OPENBLAS_NUM_THREADS='1'; $env:OMP_NUM_THREADS='1'; $env:AWS_PAGER=''
$approved=(Get-FileHash docs/MANUAL_DEPLOYMENT_PLAN.md -Algorithm SHA256).Hash.ToLowerInvariant()
.\.venv\Scripts\python.exe -m scripts.aws_app_update publish --approved-plan-sha256 $approved
.\.venv\Scripts\python.exe -m scripts.aws_app_update changeset --approved-plan-sha256 $approved
.\.venv\Scripts\python.exe -m scripts.aws_app_update execute --approved-plan-sha256 $approved
.\.venv\Scripts\python.exe -m scripts.aws_app_update verify
$env:BTP_BASE_URL='https://d1qxms20novn1p.cloudfront.net'; $env:BTP_VERIFY_TARGET='aws-manual'; $env:BTP_REMOTE_ACCEPTANCE='1'
node frontend/scripts/manual-browser-check.mjs
# Original teardown, unchanged:
$original=(Get-FileHash docs/DEPLOYMENT_PLAN.md -Algorithm SHA256).Hash.ToLowerInvariant()
.\.venv\Scripts\python.exe -m scripts.aws_release delete-app --approved-plan-sha256 $original
```

Rollback if needed before teardown: use the original ignored `data/tmp/aws-published.json` with the original `scripts.aws_release rollback` / original approved plan hash. It preserves previous parameters/secrets and original image pins. Wait and verify actual task identity; rolling/circuit-breaker rollback is not assumed successful without checks.

References: [AWS change-set parameters and previous template](https://docs.aws.amazon.com/cli/latest/reference/cloudformation/create-change-set.html), [CloudFront origin forwarding](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/controlling-origin-requests.html).
