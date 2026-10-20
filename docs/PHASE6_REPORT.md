# Phase 6 execution — published release; deployment blocked

2026-10-20, Asia/Calcutta. User approved Option B/default CloudFront viewer HTTPS with **HTTP origin**,24h after successful acceptance,$5 before-tax planning allowance (not a spending cap). No automatic teardown or Phase 7 deployment automation. Trusted image/model/cohort/features/metrics and score-only2ULP comparison policy unchanged.

## Completed

- Intended STS identity/account, exact task-role boundary JSON and AWS template validation verified. Actual AZsa+b, CloudFront prefix-listpl-9aa247f3, SG rulesquota60 vs prefix weight55, Fargate64vCPU quota. One existing VPC vs quota5 before app attempt. No existing project resource names adopted. Administrator confirmed Basic scanning; registry-wide API read was not granted/claimed.
- Storage stack `btp-demo-storage` CREATE_COMPLETE, ARN `arn:aws:cloudformation:ap-south-1:044854093109:stack/btp-demo-storage/73c4fd90-cbf2-11f1-99a5-06483bdaff43`. Retained private versioned/encrypted bucket `btp-demo-artifacts-044854093109-ap-south-1`, ECR repository `btp-demo-app`.
- Published unchanged real image by immutable ECR index digest **sha256:ef69b2d2b4ac3e75d32744b745318e88e85e921cdfcec01004f139406f6f801f**, Linux amd64 child **sha256:e3e8399d60ad6038ba3ed259446b9c998e0d9fe05cfac53d1f56484cb797c99d**. ECR reports207,380,666bytes for image; parent/child share layers, do not sum those sizes as independent billed storage. No rebuild. Baked runtime revisionf668daf9447f2f97175c7355a9388f47354b2b75; publishing/operator commit06e49654173f98b6c7ff1beb04e610bd328a91bf had successful [CI39293846551](https://github.com/RufinaM03/beyond-the-pass/actions/runs/39293846551).
- Private S3 release tar and publication record uploaded successfully. `data/tmp/aws-published.json` pins registry/platform digests, original source/artifact provenance and bundle SHA256ae9706f0175926fc38d88880315209d7ba54f83fdf5a05078cd13ba392368741. Original release-manifest/model/snapshot file hashes unchanged. Never re-run publish blindly: immutable tag already exists; **reuse this verified record** for deployment.

## Docker diagnosis and bounded workaround

After morning resumption Docker API/container inventory recovered, no owned network diagnostic remained; unrelated stopped containers untouched. Host free RAM1.31GiB/commit1.34GiB observed, C:37.03GiB/D:59.72GiB. No cold build or large data processing. Existing-image128MiB read-only/capability-dropped diagnostic container reached registry HTTPS401 and exited/auto-removed, proving container connectivity without credentials.

The remaining login failure was specific: **error saving credentials / The stub received bad data** from Windows credential storage. Earlier hangs and low memory were separate observations, not a proven explanation for this error. Used a unique ignored D: `DOCKER_CONFIG` with Windows inheritance removed/current-user-only ACL, an empty entry for the target registry to avoid native-helper autodetection, bundled Buildx path, and the existing local named-pipe endpoint via process-only DOCKER_HOST. Password-stdin only, no credential logging, no reads of normal credential/config files. Docker may temporarily store base64 credentials in that private cache; it is not encrypted. Successful publish/logout completed; the entire newly created cache was removed after resolved-path/workspace/symlink checks. No user/global Docker setting, TLS weakening, reset/prune, image/volume deletion or pagefile change.

Reproducible helper: `scripts/publish_windows.ps1` retains all original publication validation/approval/account/exact-CI gates and creates/removes only its temporary authentication directory. Its PowerShell syntax is checked locally; the equivalent process-isolated method above actually published this release. **Do not execute it again for the already-published tag.** For a separately reviewed first publication only:

```powershell
$approved=(Get-FileHash docs/DEPLOYMENT_PLAN.md -Algorithm SHA256).Hash.ToLowerInvariant()
.\scripts\publish_windows.ps1 -ApprovedPlanSha256 $approved
```

References: [Docker credential storage/password-stdin](https://docs.docker.com/reference/cli/docker/login/), [Docker config helper detection](https://github.com/docker/cli/blob/v29.3.0/cli/config/config.go).

## Actual application attempt and blocker

Application stack ARN `arn:aws:cloudformation:ap-south-1:044854093109:stack/btp-demo-app/ed2f8ed0-cc46-11f1-8308-0afff9c88c63` failed at **ALB creation**, with AWS403 specifically denying **ec2:DescribeAccountAttributes** to Dev_1. Other CREATE_FAILED entries were cancellation, not independently diagnosed missing permissions. No successful ALB, CloudFront distribution, task definition/service/application deployment or public HTTPS acceptance. No training/data acquisition/model change.

CloudFormation reached **ROLLBACK_COMPLETE**, no DELETE_FAILED events. Saved resource evidence `data/tmp/aws-first-app-rollback.json`, then approved `delete-app` cleanup completed; subsequent DescribeStacks confirms **the failed app stack no longer exists**. Storage/release retained separately. No stale ROLLBACK_COMPLETE shell remains to block retry.

`infra/iam/operator.json` adds **only ec2:DescribeAccountAttributes** to its Mumbai-only discovery statement; wildcard resource is necessary for this account-level read API. Existing role boundaries/PassRole and other grants unchanged. `docs/IAM_SETUP.md` gives administrator-only policy-edit steps. **Agent has not modified its own attached policy.** New regression checks action presence/region/resource scope. Amended source must be committed/pushed and pass exact-commit CI before another deployment attempt. No new paid resource/material estimate change.

## Resume / teardown

1. Administrator updates BtpDemoOperator from the amended JSON and confirms. Recheck the specific read, intended identity, exact amended-commit green CI and failed-stack deletion; preserve Basic scanning/user approval.
2. Do not bootstrap or republish. Reuse `data/tmp/aws-published.json` and restricted `aws-parameters.json`; deploy through existing manual command with current approved plan hash.
3. After successful intended-digest deployment, perform actual CloudFront/ALB origin/cache/security checks, HTTPS production browser flow, inference/queue/evaluation comparisons, direct-task blocking and measured AWS startup/memory. None is claimed completed yet.
4. Record **successful acceptance UTC +24h** as exact manual teardown deadline, also in IST. No success timestamp/deadline exists yet; no scheduler/automatic teardown. App cleanup command remains `python -m scripts.aws_release delete-app --approved-plan-sha256 <approved plan hash>`; retained ECR/S3 version cleanup is separately documented in `DEPLOYMENT_PLAN.md`. Scaling to zero leaves ALB charges if an ALB is later deployed. Current retained storage has ongoing storage costs; no cost-cap guarantee.
