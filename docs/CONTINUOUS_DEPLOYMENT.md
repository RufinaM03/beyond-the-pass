# CI and production CD

**Production and automatic CD verified:** manual OIDC deployment39649274769 succeeds at exact6578185, final stack UPDATE_COMPLETE/healthy task:5/public smoke and browser checks. After acceptance, automatic CD was enabled; successful same-commit CI39650491631 triggered actual **workflow_run39650767514, deploy job SUCCESS**, including OIDC, immutable-tag replay and live smoke. Replay makes no redundant stack update; the first manual run proves actual rolling deployment. Read `CD_IMPLEMENTATION_REPORT.md` and PROJECT_STATE.md for current release/run evidence, not historical blocker sections.

## Flow and safety

Completed bootstrap uses the user-supplied `arn:aws:iam::044854093109:role/BtpProductionImageDeployment` (not the initial proposed name). Repository variable `BTP_CD_ENABLED` is now **true**, set only after the first accepted manual rollout, and the same-commit automatic follow-on CD is verified. Normal later successful main CI deploys automatically; workflow_dispatch remains available. This switch is GitHub configuration only, not an AWS service or per-deployment approval requirement. Local publication was blocked by Windows commit headroom after a successful exact-SHA Docker build; the authorized Linux runner avoids weakening the local guard.

- `.github/workflows/ci.yml`: PR, main push and manual CI; locked Python3.12/frontend checks, fixture-only container and offline CloudFormation checks. No AWS credentials or real-data downloads. PRs never trigger production deployment.
- `.github/workflows/deploy.yml`: CI `workflow_run` completion on main, successful push/manual CI from the same repository only; also `workflow_dispatch` from main. Exact full commit checkout; gate verifies successful CI workflow identity and both required job conclusions before AWS authentication. CI for a PR/fork, failed/missing CI or non-main-history SHA is rejected.
- Normal successful main CI triggers CD automatically, without a per-deploy click. No GitHub Environment exists; no environment/protection setting is silently altered. The main-only OIDC trust substitutes for broad repo trust, not for repository code review/branch protection. Maintainers who can merge/push main can deploy code; configure branch protections separately if desired.
- One concurrency group, `cancel-in-progress: false`: never interrupt an active rollout. GitHub can replace older pending runs. Automatic runs recheck current main immediately before publication and change-set execution, so obsolete queued commits fail rather than roll production back. Explicit manual replay may select an older valid main-history commit.
- OIDC obtains one-hour credentials as BtpProductionImageDeployment. No static AWS keys/secrets. Trust/policy/admin setup in `GITHUB_OIDC_SETUP.md`; actions pinned to verified immutable GitHub revisions. Checkout credentials are not persisted. Deploy role cannot create/delete stacks, change networking/CloudFront/ALB/IAM, write S3, delete images, access Secrets Manager or change budgets. Existing CloudFront configuration read for output resolution is exact-distribution/CloudFormation-forwarded only; responses and origin headers must never be emitted or stored.
- Read one existing bounded S3 archive, verify its SHA256, reject links/traversal/oversize tar members, and verify the trusted manifest/dependencies/schema before joblib loading. No retraining or new snapshot. Stage serving-only files; build React/locked Python inside one Linux amd64 image. Model/data/200 demo/936 evaluation remain unchanged. CI's synthetic fixtures are never production artifacts.
- Build and real-container smoke precede ECR publication. Use full Git SHA tag in immutable btp-demo-app repository, resolve immutable digest. Replays reuse the existing immutable tag after identity checks; previous images are not deleted. No `latest` deployment.
- CloudFormation remains authoritative: use existing template, previous parameter values for everything except ImageUri/CodeVersion. No origin secret needs printing, writing or rotation. Validate and inspect a change set; reject anything except Task replacement and Service in-place update. No direct ECS registration/service mutation by the pipeline; ECS writes are CloudFormation-forwarded.
- Existing ECS rolling policy min100/max200 keeps the old healthy task while the new starts, up to two tasks briefly, with circuit breaker/rollback. Same256CPU/512MiB desired1 and Haswell kernel. No extra infrastructure or S3 writes.
- Wait for CloudFormation completion and ECS stability; verify exact expected task/image digest, container health and ALB healthy targets. Then actual CloudFront HTTPS smoke checks HTML/assets route shape, health/readiness/version, `/predict`, queue/evaluation/methodology, real model prediction parity, no-store POST and unchanged saved metrics. A200 error body alone is not acceptance.
- Build/push/change-set/service/health/smoke failures fail the workflow; no success masking. CloudFormation/ECS automatic rollback is verified by expected image identity, not mistaken for deployment success. Public-smoke failure marks the workflow failed and requires deliberate rollback review. No automatic destructive cleanup.

## Trigger and inspect

For a diagnosed OIDC failure, `.github/workflows/oidc-check.yml` is manual-only/main-only and does not deploy. It verifies the workflow token's signature against GitHub public JWKS and prints **only booleans, relative lifetime and STS error codes**, never the JWT, bearer token or returned AWS credentials. One regional STS authentication probe is made; only InvalidIdentityToken triggers a single global comparison probe to isolate regional/provider validation behavior. Any successful temporary credentials are discarded, not exported. This grants no new permissions and changes no AWS resources. Synthetic cryptographic tests run in CI. Normal deployment authentication retries are bounded to3; do not rerun unexplained failures blindly.

```powershell
gh run list --workflow ci.yml --limit 3
gh run list --workflow deploy.yml --limit 3
gh workflow run deploy.yml --ref main -f sha=<full-valid-main-sha>
```

Manual SHA must contain the CD bootstrap files and have successful required main CI. For a release predating CD tooling, use the explicit previous-image rollback command below rather than pretending old commits contained deployment code. Leaving sha blank redeploys current main after its CI passes. No meaningless application commit is needed to test CD. The workflow never writes back to Git, so cannot create recursive commit/deploy loops.

```powershell
aws cloudformation describe-stacks --stack-name btp-demo-app --profile beyond-the-pass --region ap-south-1 --query 'Stacks[0].Outputs[?OutputKey==`CodeVersion` || OutputKey==`ImageUri` || OutputKey==`TaskDefinition`]'
Invoke-RestMethod https://d1qxms20novn1p.cloudfront.net/api/versions
```

The job summary/artifact `production-deployment-<run-id>` contains only nonsecret deployment JSON: commit, CI URL, digest, change-set summary, prior image/code/task identity and actual verification results. No model/snapshot, tokens, parameter values or origin header is uploaded. The original S3 archive remains original artifact provenance, not falsely relabelled as new application code.

## Rollback and manual teardown

Keep the prior ECR image and download the failed/new run's `production-release.json` into ignored `data/tmp`. On a current CI-passed CD tooling checkout, explicitly roll back to its recorded previous immutable image through the same two-resource CloudFormation change-set gate:

```powershell
$env:BTP_AWS_PROFILE='beyond-the-pass'; $env:AWS_PAGER=''
$env:TEMP="$PWD\data\tmp"; $env:TMP=$env:TEMP
$env:OPENBLAS_NUM_THREADS='1'; $env:OMP_NUM_THREADS='1'
.\.venv\Scripts\python.exe -m scripts.cd_release rollback --sha (git rev-parse HEAD) --record data/tmp/production-release.json
```

This requires exact successful current main CI; if main has advanced, intentionally use `--allow-older` only for a valid main-history tooling checkout. Review recorded previous identity before running. It reuses previous stack parameters/secret values, waits for stability and verifies prior code/image/public readiness. It does not resurrect an inactive task definition manually; CloudFormation creates the needed revision. First rollback may remove Try Prediction if the previous accepted release predates that page. Older deployment evidence remains retained; rollback is not an excuse to claim the feature is still deployed.

The old21October11:42:53IST deadline was operational/documentary, not an AWS expiration. User explicitly superseded it and asked the application remain running. No teardown after deployment. When separately authorized, use the original `scripts.aws_release delete-app` and approved original deployment-plan hash; see PROJECT_STATE.md for exact command/removal scope. ECR/S3 remain retained/billable. No scheduler/service was created, budget alert disabled, or cost cap promised.
