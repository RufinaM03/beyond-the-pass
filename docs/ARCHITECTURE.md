# Architecture

Current: **Phase 6 approved temporary demonstration deployed and accepted2026-10-20**. Default CloudFront viewer HTTPS → explicitly approvedHTTP ALB origin → one LinuxX86_64 Fargate256CPU/512MiB task, unchanged single release image/model/read-only200-case snapshot. Origin-facing prefix-list + secret-header gate, task8000ALB-only, all-path caching disabled; real read-back/HTTP/browser checks pass. Task-local Haswell kernel preserves the original strict prediction agreement without changing model/image or tolerances. Private ECR/S3 and seven-day CloudWatch logs; no NAT/runtime training/GenAI. Standard CloudFormation, manual operator deployment after exact-commit CI; OIDC automated deployment is deferred to Phase7.

Actual acceptance, IDs/evidence and **manual24h teardown due2026-10-21 11:42:53IST** are in `PHASE6_REPORT.md` / `PROJECT_STATE.md`; no automatic teardown. $5 before-tax allowance is not a cap. `DEPLOYMENT_PLAN.md` remains the unchanged approved resource/cost/HTTPS plan. Earlier preparation/phase descriptions below are historical, not current deployment status.

## Phase 6 deployment proposal (approval pending)

Latest amendment: user approved **Option B/default CloudFront HTTPS with HTTP origin**,24h after successful deployment,$5 before-tax planning allowance, not a cap. Administrator IAM action and exact Phase 6 commit green CI remain prerequisites. Fixed role/resource names plus execution/application permission boundaries narrow scope without changing paid resources. Console steps: `IAM_SETUP.md`; origin/API audit: `PUBLIC_SURFACE_REVIEW.md`. No IAM mutation/provisioning by the agent yet. No automatic teardown; record successful acceptanceUTC+24h when it actually occurs. Earlier pending-choice descriptions below are superseded by this amendment.

One unchanged Linux amd64 image contains React production build, Python3.12/FastAPI, trusted model/preprocessor and read-only 200-case SQLite. One worker/task, candidate256CPU/512MiB, separate empty application and narrowly scoped execution roles. ECR digest deployment, private versioned encrypted S3 release archive, seven-day CloudWatch logs; no training/data acquisition/runtime S3 access. Preserve original four features/936-example saved evaluation/aggregate-only history/two-ULP score policy.

Dedicated VPC/two public subnets/IGW; public task IPs for outbound HTTPS without NAT. Separate SGs restrict task8000 to ALB only. ALB IP targets use artifact readiness; ECS container check uses liveness; configurable120s grace. Rolling min100/max200 with circuit-breaker rollback allows a second task temporarily. Read-only root app with task-lifetime scratch: same-image capability-dropped short root init sets scratch permissions, then only non-root app runs. Local handoff passed; Fargate execution and quarter-CPU capacity remain unverified.

HTTPS choice is pending: controlled domain + Mumbai ACM + ALB443/80 redirect; or optional default CloudFront hostname, no caching (including APIs), full needed forwarding, origin prefix-list/random-header restrictions, **CloudFront→ALB HTTP explicitly requiring acceptance**. No HTTP-only success or implicit CloudFront/domain purchase. Current committed CI now green; new infrastructure changes are locally validated only. AWS auth works but required EC2/CloudFormation reads are denied; administrator-scoped access and plan approval precede any creation. Current prices, exact resources/commands and cleanup: `DEPLOYMENT_PLAN.md`, `AWS_PRICING.md`. No automated cloud deployment until Phase 7.

## Local data and training

Verified real inspection source → bounded pandas chunks → validated Parquet → chronological, vehicle-disjoint evaluation → baseline and modest scikit-learn candidate → trusted model and bounded sanitised SQLite demonstration snapshot. All training runs locally. Source verification, cohort feasibility, and actual schemas precede implementation; see `DATA_CONTRACT.md`.

Phase 1 uses pinned DVSA manifests, validated cached downloads, deterministic cross-year vehicle sampling, sequential archive workers, and an indexed local SQLite staging database plus sampled Parquet. This staging database is not the future bounded serving snapshot. Real-data quality checks precede model work; see `docs/ACQUISITION.md` and `docs/QUALITY_REPORT.md`. Training is not implemented.

## Application and release

React/Vite is built during a multi-stage Docker build. FastAPI/Uvicorn serves both API routes and the built frontend from one service. The runtime image includes locked Python dependencies, the trusted model, and the read-only SQLite snapshot. Run as a non-root user; prevent snapshot mutation; provide health checks. This is a demonstration release, not a live vehicle database.

Model/snapshot files stay outside Git. Plan a private, versioned S3 artifact bundle with provenance, feature/schema versions, checksums, and bounded size. CI must retrieve an explicitly approved bundle and verify its manifest before image packaging; never load untrusted pickle/joblib input. Exact artifact delivery and validation are future implementation work.

## AWS ECS design

Browser → HTTPS Application Load Balancer → ECS Fargate service → single application image pulled from ECR. CloudWatch receives bounded-retention application/container logs. S3 holds approved release artifacts and optional permitted data artifacts. No cloud training.

Standard CloudFormation templates will describe VPC/subnets/routes, security groups, ALB/listeners/target group, ECS cluster/task/service, ECR, S3, log groups, and IAM as needed. Only the ALB accepts public application traffic; task ingress is restricted to the ALB security group. ECS health checks and ALB health checks must agree on readiness. Separate task execution, application task, and deployment roles with least privilege. Never expose AWS credentials to the frontend.

Networking and availability remain explicit plan decisions: private task subnets require costed NAT or suitable VPC endpoints; a smaller demonstration topology requires a documented security and cost tradeoff. Do not silently create a NAT gateway. Specify region, task CPU/RAM/count, ALB subnets, outbound connectivity, image/artifact storage, log retention, teardown, and rollback before approval.

No domain is currently owned. Public HTTPS requires a controlled domain, editable DNS, a region-matched ACM certificate, validation records, and a DNS record pointing to the ALB. Certificate/domain details remain pending; local development is independent of this decision.

## Planned GitHub Actions delivery

Pull requests: locked dependency installation, focused tests, data-contract/fixture checks, frontend build, and container validation without production credentials. Use small clearly synthetic fixtures for tests; evaluation claims require real data.

Approved releases: GitHub environment approval and branch restrictions → GitHub OIDC assume-role with restricted repository/environment subject and audience → verified artifact bundle → build one immutable image → push to ECR → update CloudFormation/ECS → wait for service stability → smoke-test health, API, and frontend. Scope `id-token: write` to deployment jobs and pin actions. Record image digest, model/snapshot versions, and rollback target. Infrastructure creation remains separately gated by the user's approved plan and estimate. No workflows are added in Phase 0.

## Approval and acceptance gates

Before AWS provisioning, provide an itemized estimate using current regional pricing for Fargate compute, ALB/LCU, public IPv4, networking/egress or endpoints, ECR/S3, CloudWatch, DNS/domain, and optional state/support storage. State usage assumptions, monthly baseline, deployment overhead, and teardown steps. Obtain user approval of the concrete plan and estimate. There is no current cost estimate.

Later deployment acceptance requires an actual accessible HTTPS URL, verified service health and application behavior, CI/CD evidence, rollback verification, and recorded resource identifiers. Never report a planned deployment as completed.

## Implemented local Phase 1B / 2 boundary

The local data layer now includes a separate verified 2024 monthly-CSV adapter, deterministic 2022–2024 sample, indexed SQLite staging, Parquet annual labels, index-only feature/audit matrices and integrity manifests. `docs/PHASE2_REPORT.md` records conditional cross-release linkage, actual attrition and strict vehicle-disjoint chronological partitions. The staging database is not the read-only demonstration snapshot. Model readiness is blocked by sparse training history, limited holdout positives and unresolved availability/revision semantics; no training occurred. The one-image FastAPI/React/ECS design and all infrastructure approval gates remain unchanged.

## Phase 5 local packaging / credential-free CI

Latest acceptance supersedes the earlier capacity blocker below: real Linux amd64 release image built and all 200 HTTP predictions/readonly smoke checks passed. Machine-precision portability permits only score differences up to 2 ULPs; original hashes, schema, all non-score fields/explanation terms and Phase 3 inference stay exact. Observed startup 25.040 s and 166.2 MiB container memory are measurements, not ECS capacity guarantees. Earlier remote CI succeeded; latest rerun queued during reported GitHub Actions degradation. Full evidence/current commands: `docs/PHASE5_REPORT.md`. No AWS provisioning.

Bounded staging copies only approved serving files into an ignored, checksum-verified context. Pinned multi-stage Linux amd64 image builds React and installs locked Python 3.12, runs one non-root Uvicorn worker, readonly SQLite and disposable temp storage. Production validation rejects explicitly synthetic fixtures; PR CI requires neither real artifacts nor DVSA/AWS credentials. Actual remote fixture image/test smoke runs succeeded; local real-image build is pending host commit capacity after a safe cancellation. No AWS/CloudFormation resources, cloud deployment job or image registry push added. The one-image ECS/X86_64 design and domain/cost approval gates remain intact. See `docs/PHASE5_REPORT.md` for actual evidence and remaining acceptance work.

## Implemented Phase 4 local application

`backend/app.py` now loads the pinned release once per process, checks feature/version compatibility and all 200 stored predictions, then serves bounded read-only parameterized queries and unchanged Phase 3 inference. Each request opens its own immutable/query-only SQLite connection; no shared cross-thread writable connection. Saved full-cohort metrics are a separate verified JSON resource, never recomputed on the demo. `/api/health` is liveness; `/api/ready` is artifact readiness. Artifact failure gives 503, not fallback scores. Frontend build availability is checked separately on page requests.

React/Vite production assets are served through the same FastAPI/Uvicorn origin. Only known SPA routes fall back to index HTML; API errors and missing assets remain 404. Index-time advisory counts and aggregate prior-history panels honestly reflect the available export; no dated timeline/item text is invented. Model explanations are exact noncausal logistic terms; recurrence stays descriptive. Demo capacity and the saved 936-example evaluation are explicitly separated. Reproduction/security limits and actual checks are in `docs/PHASE4_REPORT.md`. No Docker/AWS/CI implementation yet; the single-image ECS architecture, domain decision and approval/estimate gates remain unchanged.

## Phase 3 exploratory serving artifacts (historical checkpoint)

Phase 3 supersedes the earlier stop-before-training boundary with an explicitly exploratory four-current-feature logistic model and two baselines, not a recurrence/production-readiness claim. The fixed trusted release contains preprocessing/model, schema/metrics/model card/protocol/integrity metadata and a capped 200-case read-only historical serving snapshot. That snapshot is separate from staging and row-level evaluation outcomes. Runtime helpers verify pinned hashes/dependency versions before deserialization; scores have deterministic noncausal current-feature explanations and insufficient/unsupported states. Recurrence remains a separate descriptive panel. No backend/UI/container/cloud deployment exists; next is Phase 4 API and dashboard against `docs/API_CONTRACT.md`. The one-image ECS architecture and cost/domain approval gates are unchanged.
