# Dev_1 console viewing — administrator attachment required

**Verification complete2026-10-20:** administrator confirmed attachment; **85 allowed calls,0denied,0failed** as account044854093109/userDev_1. All seven project policy default versions match the local JSON documents; all five project identity policies are attached. GetUser reports **no user permissions boundary**,0inline policies and one group membership (group policy contents/SCPs not inspected). No remaining denial or observed boundary/SCP block for these requests; this is not proof of absence of account controls generally. Report:`data/tmp/console-access-after.json`. Agent made no IAM/application mutations and emitted no secret-bearing configuration/log bodies. The initially denied inspection below is historical before-attachment evidence.

## Identity and current evidence

Checked2026-10-20. Deployment and current CLI profile **beyond-the-pass** both resolve to account **044854093109**, principal **arn:aws:iam::044854093109:user/Dev_1**. This is the same user, not a separate deployment/admin role. Profile configuration shows an AWS CLI login session, Mumbai region and no configured assume-role/credential-process/SSO-session; only those flags were inspected, not credential files, tokens or environment credential values. ECS execution/application roles are workload roles, not the provisioning principal.

Deployment acceptance remains valid. Reproduced denials for **cloudfront:ListDistributions**, **cloudformation:ListStacks** and the previously documented **ecs:DescribeTaskDefinition** are viewing/discovery gaps, not failed deployment evidence. Existing local four deployment policies and two task boundaries were reviewed first. Live inspection of Dev_1's attached/inline/group policies, user boundary and BtpDemoOperator document was denied with **no identity-based policy allows**. Therefore exact live attachments/other effective policies are not independently confirmed yet; administrator must review them before attachment. No evidence establishes an SCP or user-boundary denial. Task-role boundaries do not themselves limit Dev_1.

## Recommended policy: additive gaps only

File: `infra/iam/console-view-supplement.json`. Customer-managed name: **BtpDemoConsoleViewSupplement**, default path `/`. It supplements the documented **BtpDemoOperator, BtpDemoNetwork, BtpDemoServices, BtpDemoRoles** rather than copying their existing reads. It is **not a standalone full viewer**, nor does attaching it make Dev_1 read-only: existing deployment writes, image publishing and bounded release-object download permissions remain until an administrator separately reviews/removes them. No existing policy is changed here.

| Requested area | Existing documented access retained | Added by this supplement |
| --- | --- | --- |
| CloudFormation | Named project DescribeStacks/outputs, events, ListStackResources, template reads | Console ListStacks; DescribeStackResources on the two **actual stack ARNs** below |
| ECS | Project cluster/service/task detail and ListTasks | ListClusters, ListTaskDefinitions/families; DescribeTaskDefinition using its required Resource*; ListServices restricted by ecs:cluster |
| ECR | Named project repository/image metadata, policy/tags | ListImages on the exact project repository |
| ALB | Mumbai load balancer/listener/rule/target/health descriptions | None; avoid duplicates |
| CloudFront | GetDistribution/GetDistributionConfig/tags, currently account distribution ARN pattern | ListDistributions for console navigation; no new duplicate configuration grant |
| Network | Mumbai VPC/subnet/route/ENI/SG/prefix-list reads | None; queries use actual project IDs |
| Metrics/logs | DescribeLogGroups, project streams/events, GetMetricStatistics | ListMetrics/GetMetricData for classic metric graphs; project FilterLogEvents/GetLogGroupFields; no Logs Insights query execution |
| IAM | GetRole/role-policy details for two workload roles; GetPolicy/GetPolicyVersion for two boundaries | Own-user access metadata; configuration of four project deployment policies/this supplement; versions of those seven policies |
| S3 | Project bucket location, object/version listings | Console bucket discovery; metadata/configuration only for exact project bucket |

Current resource identifiers (metadata, never origin-header values):

- App stack: `arn:aws:cloudformation:ap-south-1:044854093109:stack/btp-demo-app/8e6e41c0-cc4b-11f1-b4c7-02fff94de1e3`.
- Storage stack: `arn:aws:cloudformation:ap-south-1:044854093109:stack/btp-demo-storage/73c4fd90-cbf2-11f1-99a5-06483bdaff43`.
- Cluster/service: `arn:aws:ecs:ap-south-1:044854093109:cluster/btp-demo-cluster`, `arn:aws:ecs:ap-south-1:044854093109:service/btp-demo-cluster/btp-demo-app`; task family `btp-demo-app-app`, currently revision2. Existing task read ARN is cluster-limited with generated task-ID wildcard to accommodate replacement.
- ECR: `arn:aws:ecr:ap-south-1:044854093109:repository/btp-demo-app`.
- Distribution: `arn:aws:cloudfront::044854093109:distribution/E2KD3NUMXZ0BRD`.
- ALB: `arn:aws:elasticloadbalancing:ap-south-1:044854093109:loadbalancer/app/btp-demo-alb/e0101f6f7909da5d`; listener suffix `/6fefbe1b94da670f`; target group `arn:aws:elasticloadbalancing:ap-south-1:044854093109:targetgroup/btp-demo-targets/73d7edaa1bda6b4c`.
- VPC `vpc-075644fa1a404906e`; subnets `subnet-005be2118d520ccb0`, `subnet-028b075c360150405`; route table `rtb-0bc814e0aea1036a8`; ALB/task SGs `sg-0a9373fd402095035`, `sg-076995b63103a5c05`. Task ENI IDs are discovered read-only from the current task rather than pinned to a replaceable ENI.
- Log group `/btp/btp-demo-app`; role ARNs `arn:aws:iam::044854093109:role/btp-demo-execution` and `arn:aws:iam::044854093109:role/btp-demo-application`; bucket `arn:aws:s3:::btp-demo-artifacts-044854093109-ap-south-1`.

## Wildcards and sensitive configuration — review before attaching

- `cloudformation:ListStacks`, ECS cluster/family/definition lists and **DescribeTaskDefinition** do not support project resource ARNs. Mumbai requested-region condition limits these. They can expose other regional metadata/task-definition configuration, including environment variables. A family-prefix CLI filter is not an IAM boundary. Existing family-ARN DescribeTaskDefinition grant cannot authorize that API.
- `ecs:ListServices` requires Resource* but supports **ecs:cluster**, so an ArnEquals condition limits it to the actual project cluster. Existing ListTasks grant is already Mumbai-wide; this supplement does not repeat or broaden it.
- Classic AWS/ECS metric reads/listing require Resource*: individual classic metrics have no ARN and cannot be namespace/dimension-restricted through these permissions. The current authorization reference's optional **dataset** resource applies to dataset/OTLP features, not this classic-metric request. Requested region is Mumbai; other regional metrics may be readable. Verification filters AWS/ECS/project dimensions, but those filters are not IAM enforcement.
- **CloudFront ListDistributions and S3 ListAllMyBuckets are account-wide discovery** and cannot be filtered to one distribution/bucket by IAM. They are global, so do not apply a Mumbai-only requested-region condition. S3 discovery grants bucket names/metadata, not object contents. **CloudFront list responses can contain origin custom-header values for other distributions in this account**, not only this project. If that unavoidable disclosure is unacceptable, do not attach the list statement; use existing direct project configuration access instead and accept console landing-page limitations.
- User explicitly authorized viewing project CloudFront configuration/ALB rules containing the origin-header shared secret. IAM cannot mask individual fields. Existing GetDistribution/GetDistributionConfig and ALB DescribeRules already permit those reads; the former currently has a broader account distribution pattern. This additive policy cannot narrow existing grants. No secret is printed, logged, committed, screenshotted, rotated or included in reports. The verifier selects safe fields **inside the AWS CLI query** and never emits raw service/config/log bodies. New diagnostic errors redact X-Btp header names and64-hex values. Do not enable `--debug`, save full configuration responses or share console screenshots of origins/rule conditions.
- Existing EC2 and ELB describe APIs mostly lack usable per-resource IAM scopes; regional metadata may be visible. Existing **DescribeVpcAttribute** does support VPC ARNs but is already broader in BtpDemoOperator; this supplement adds no duplicate or broader EC2 grant. ECR metadata remains repository-scoped: use the named project repository; an unfiltered account-wide repository landing page can remain denied. IAM role listing is not added; use direct named-role pages, not all-account role browsing. Broad ancillary console widgets/tabs may remain denied by design.
- Supplement contains only explicit read/list operations. **No writes/deletes, PassRole, policy attachment, credential/token retrieval, Secrets Manager, SSM parameters, KMS decrypt, ECR login/pull or S3 object-content permissions** are added. Logs/application and authorized configuration reads are the requested exception for operational content. Billing/Cost Explorer/Organizations permissions are not included.

## Exact administrator-console steps

1. Sign in with the separately authorized **administrative identity**, account **044854093109**. Do not send credentials, tokens or screenshots of sensitive configuration to chat.
2. Open **IAM → Users → Dev_1 → Permissions**. Inspect attached policies, group memberships, inline policies and the **permissions boundary** section. Confirm the documented four BtpDemo deployment policies; do not attach the two workload boundary policies to Dev_1. If an equivalent console-view policy already exists, review/update that instead of creating a duplicate. If existing access differs from the documented baseline, stop and report policy names/boundary status only.
3. Open **IAM → Policies → Create policy → JSON**. Paste the contents of local `infra/iam/console-view-supplement.json`. Review all statements and the account-wide discovery limitations above. Resolve any validation errors without replacing it with FullAccess.
4. Set name **BtpDemoConsoleViewSupplement**, path `/`, description **Read-only console discovery and metadata gaps for Beyond the Pass; no object content or mutations**. Create the policy. If this policy already exists, inspect it and edit/create a new default version rather than duplicate it.
5. **IAM → Users → Dev_1 → Permissions → Add permissions → Attach policies directly**. Select **only BtpDemoConsoleViewSupplement**, review, then **Add permissions**. Leave all other policies/boundaries unchanged. If the attachment quota is reached, stop for an administrator-reviewed consolidation/quota decision; do not detach unrelated policies.
6. In Dev_1's console verify the upper-right account/user, choose **Mumbai/ap-south-1** for regional services (CloudFront/IAM are global), then refresh/reopen the affected pages after propagation. Confirm attachment in this chat; the agent will run the read-only verification below, not attach anything to itself.

The agent creates local files only. Policy attachment is an administrator action. This does not modify/redeploy any application resource or extend the approved demonstration lifetime. **Manual teardown deadline remains21October2026 11:42:53IST; no automatic teardown.**

## Verification and denial diagnosis

Run using the same Dev_1 login profile, explicit Python3.12, no new dependencies or data access:

```powershell
$env:TEMP="$PWD\data\tmp"; $env:TMP=$env:TEMP; $env:AWS_PAGER=''
.\.venv\Scripts\python.exe -m scripts.check_console_access --profile beyond-the-pass --output data/tmp/console-access-after.json
```

The script checks STS account/principal **before** other calls; only known read/list calls follow. Reports record allowed/denied status, resource metadata, precise AWS denial text and boundary metadata, not secret-bearing response bodies or object contents. It checks both existing and added capabilities; deleted/absent resources are reported separately from IAM denial. Before-attachment report:`data/tmp/console-access-before.json` (40allowed/26denied); verified after-attachment report:`data/tmp/console-access-after.json` (85allowed/0denied/0failed; includes additional metadata probes). Seven actual project-policy documents were compared in memory with local JSON, recording only version/equality, never raw documents.

If a denial persists, record exact action, resource and AWS error reason. A missing identity Allow is not proof of a boundary/SCP issue. An explicit boundary/SCP/session/resource-policy denial must be diagnosed at that layer; another Allow cannot override it. After attachment, GetUser can reveal Dev_1's boundary ARN, and scoped project GetPolicy/GetPolicyVersion can verify project policy versions. Other group/inline/boundary documents, SCPs/RCPs, session constraints and account controls may remain unreadable: an authorized administrator must inspect them. Do not grant IAM/Organizations full read just to speculate, and do not confuse the ECS task-role boundaries with the user's boundary. Billing console access is a separate optional decision, including its account-level IAM-access setting; not requested or changed here.

## Official action validation

Current official machine-readable references fetched2026-10-20 for CloudFormation, CloudFront, CloudWatch, EC2, ECR, ECS, ELB, IAM, Logs and S3. Every supplement action exists and is classified read/list, not write/tagging/permission-management. Local audit records URLs, retrieval times, checksums and supported resource types in `console-view-policy-audit.json`; full cached references remain ignored under `data/tmp/viewer-reference/`.

Primary references: [AWS service reference data](https://docs.aws.amazon.com/service-authorization/latest/reference/service-reference.html), [CloudFront action scopes](https://docs.aws.amazon.com/service-authorization/latest/reference/list_cloudfront.html), [CloudFront list response and custom headers](https://docs.aws.amazon.com/cloudfront/latest/APIReference/API_ListDistributions.html), [ECS scopes/condition keys](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html), [CloudWatch scopes](https://docs.aws.amazon.com/service-authorization/latest/reference/list_cloudwatch.html), [S3 bucket discovery](https://docs.aws.amazon.com/AmazonS3/latest/userguide/list-buckets.html), [IAM evaluation logic](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html).
