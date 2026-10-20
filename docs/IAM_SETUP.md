# Administrator action required — temporary Option B demo

**Console-viewing update2026-10-20:** deployment is already accepted; the original provisioning instructions below are historical. For Dev_1's new console-viewing request, review `CONSOLE_VIEW_ACCESS.md` and local `infra/iam/console-view-supplement.json`. Create/attach only **BtpDemoConsoleViewSupplement** after reviewing unavoidable discovery/sensitive-configuration scope. Do not recreate/change the existing six policies, detach unrelated access or modify the application. The agent has not granted itself access; after-attachment read-only verification is pending.

User approved Option B, CloudFront viewer HTTPS / HTTP origin, 24 hours after successful deployment, $5 before-tax **planning allowance, not a spending cap**. This approval does not let the agent change its own IAM access. No policies have been attached and no AWS resources provisioned by the agent. Use your separately authorized administrative identity in account **044854093109**. Never send credentials to chat or add them to GitHub.

## Exact policy files and console steps

**2026-10-20 execution amendment:** the first application stack reached ALB creation, which AWS rejected specifically for missing **ec2:DescribeAccountAttributes** (an ELB dependency). `operator.json` now adds only that read action to the existing Mumbai-only discovery statement (`Resource:*`, because the API has no resource-level scope). Administrator: IAM → Policies → **BtpDemoOperator** → Edit → JSON, replace with the updated `infra/iam/operator.json`, review/save as the default version. Do not change the other five policies or grant FullAccess. Agent has not edited its own attached policy. Retry waits for this administrator action, exact amended-commit green CI and verified rollback cleanup. No new paid resource or material cost change.

All JSON files are under `infra/iam/`. These are the action-enumerated policies for the prepared **Option B only** templates, publishing, verification and scoped cleanup. No ACM/Route53/domain, training, other application services or automated deployment permissions. Every Allow action is named, not `service:*`. Managed-policy non-whitespace limits are checked locally (<6144 characters per file). Action names were checked against the official AWS machine-readable service references, cached under ignored `data/tmp/iam-reference`. Effective access still depends on organization SCPs, existing user policies and boundaries; do not call this a proven minimal effective policy before server-side validation/deployment. If a CloudFormation provider requests an additional action, stop and diagnose its exact resource/action rather than attaching FullAccess.

1. Sign into the AWS Console using your authorized administrative identity, and verify account **044854093109**. IAM is global; deployment region is Mumbai.
2. Open **IAM → Policies → Create policy → JSON**. Use the exact content of each file, review validation findings, then create these two **boundary-only** policies:
   - `execution-boundary.json` → name **BtpDemoExecutionBoundary**.
   - `application-boundary.json` → name **BtpDemoApplicationBoundary**.
   Do **not** attach either boundary as an identity policy to Dev_1. Templates reference their exact account-scoped ARNs. Execution boundary permits only ECR auth/pull for `btp-demo-app` and writes to `/btp/btp-demo-app` log streams; application boundary explicitly denies all AWS actions. Boundaries set a ceiling, not a grant.
3. In the same Policies/Create/JSON flow create four customer-managed policies:
   - `operator.json` → **BtpDemoOperator**.
   - `network.json` → **BtpDemoNetwork**.
   - `services.json` → **BtpDemoServices**.
   - `roles.json` → **BtpDemoRoles**.
   Preserve the exact JSON conditions/resources. Do not replace it with AdministratorAccess, PowerUserAccess or service FullAccess. Do not modify an unrelated existing policy to make space.
4. Open **IAM → Users → Dev_1 → Permissions → Add permissions → Attach policies directly**. Select **only these four BtpDemo policies**, review and add. If the user has too few managed-policy attachment slots, stop for an administrator-reviewed quota/consolidation decision; do not detach unrelated policies or change its existing boundary.
5. Optional administrator **IAM Policy Simulator** check: Dev_1 should allow Mumbai `ec2:DescribeAvailabilityZones` and `cloudformation:ValidateTemplate`; IAM PassRole should allow only the two task roles with `iam:PassedToService=ecs-tasks.amazonaws.com`, never another role/service. CreateRole additionally needs the correct boundary and CloudFormation `aws:CalledVia` context. Simulation is diagnostic, not proof against every SCP/runtime behavior.
6. Tell the agent **“the six policies are created and the four deployment policies are attached”**. No credentials or policy screenshots containing secrets are needed. The agent will retry bounded read-only preflight, inspect the two boundary definitions without printing them, perform server-side template validation and require exact-commit green CI before creating anything.

Policy creation/attachment steps above are **for you**, not commands executed by the agent. They add no billable service. Fixed names and boundary references narrow identity scope without changing the approved network/compute/CloudFront resource counts or cost estimate. Existing resources at these names must never be silently adopted or overwritten.

## IAM scope and escalation protection

- CloudFormation control is limited to **btp-demo-storage** and **btp-demo-app** stacks in Mumbai. No permission to pass an arbitrary CloudFormation execution role; the prepared CLI uses the caller's forwarded credentials, not an extra service role. No certificate stack permission for Option B. `ListStacks` is deliberately **not** needed/granted; inspect the two known stacks by name instead of listing the account.
- Infrastructure mutation statements require **aws:CalledVia includes cloudformation.amazonaws.com**. Direct EC2/ALB/ECS/CloudFront configuration writes are not granted by these statements. Do not remove this condition if a call fails; diagnose it. Direct ECR image publish and bounded S3 release upload/cleanup are separate operator permissions.
- Task roles are exactly **btp-demo-execution** and **btp-demo-application**. CreateRole requires its corresponding pre-created boundary. Only the execution role may receive an inline policy; its boundary prevents a broader inline policy from granting arbitrary AWS access. No AttachRolePolicy/CreatePolicy/CreatePolicyVersion/PutUserPolicy/AttachUserPolicy/credential-management or arbitrary AssumeRole is granted. Permissions-boundary removal/replacement is explicitly denied on these two roles. PassRole permits only these two ARNs and only ECS tasks. Fixed role names require CAPABILITY_NAMED_IAM; this acknowledges IAM creation, not admin access.
- Two **AWS service-linked role** creation exceptions are exact ARNs for ECS and ELB, with matching `iam:AWSServiceName` restrictions. They may be needed if this account has never used these services. No arbitrary role creation or passing these service-linked roles. Do not delete these potentially shared roles at project teardown.
- Bucket is exactly **btp-demo-artifacts-044854093109-ap-south-1**, repository **btp-demo-app**, cluster **btp-demo-cluster**, service **btp-demo-app**, task family **btp-demo-app-app**, ALB **btp-demo-alb**, target group **btp-demo-targets**, logs **/btp/btp-demo-app**. Object uploads/reads/deletes are restricted to the pinned real release/code prefix, not parameter files or raw/full datasets. A bucket-name conflict is a blocker, not permission to use an existing bucket.

## Why wildcards remain

### 2026-10-20 cleanup correction — administrator action required

CloudFormation deletion reached `DELETE_FAILED` only for task definition `btp-demo-app-app:1`: AWS explicitly evaluates **ecs:DeregisterTaskDefinition on Resource \***. Its existing family-ARN Allow cannot authorize this operation. The [official ECS authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html) lists no supported resource type or service condition key for this action; the live service-reference JSON independently confirms that absence.

Using the authorized administrative identity: **IAM → Policies → BtpDemoServices → Edit → JSON**; replace with the current `D:/2026-27/PROJECTS/BEYOND_THE_PASS/infra/iam/services.json`, review, and save as the default policy version. No changes to the other five policies or policy attachments are needed. Agent does not apply this policy to itself.

The action moves out of the family-ARN statement into a single-action Allow with `Resource:"*"`, **Mumbai requested-region** and **CloudFormation CalledVia** conditions. Direct CLI deregistration remains unauthorized. No RunTask/ExecuteCommand/DeleteTaskDefinitions/admin permissions added; role/PassRole restrictions unchanged. IAM cannot enforce family or resource tags on this particular action. Restriction to the approved CloudFormation stack operations is an additional control, not an absolute family-level permission boundary: an operator who deliberately rewrites an approved stack template could affect other regional task definitions through it. Review this unavoidable scope before saving; do not substitute ECSFullAccess. After confirmation, retry only the existing failed stack deletion first and verify it is gone before provisioning again.

| Scope | Reason / limitation |
|---|---|
| Resource `*` for regional describe/validation, ECS ListTasks, metrics/quotas, ECR token | These operations have no usable resource scope for the invoked discovery/list calls, or require account-level discovery. They are explicit actions with Mumbai requested-region restriction. ECS task/detail reads then restrict to this cluster/family. ECR token alone does not grant other-repository access. These reads may reveal regional resource metadata; never log credentials or broad outputs. |
| EC2 `vpc/*`, `subnet/*`, IGW/route-table/SG suffixes | AWS allocates IDs at creation, before exact ARNs are known. Only six resource types, Mumbai/account, explicit lifecycle actions and CloudFormation forwarding are allowed. The two-stack control restriction prevents creating arbitrary other stacks, but IAM cannot enforce every template property or exact future VPC ID. This is not absolute isolation from an operator who intentionally rewrites the approved stack template. Review templates/commit; after deployment an administrator can narrow to actual IDs. No EC2 instances/NAT/ENI creation permission is granted to Dev_1. ECS uses its service-linked role for networking. |
| ALB/listener/target-group suffix `*` | AWS-generated IDs under the **fixed approved names**, exact account/region. Child listeners/rules share the fixed ALB name. |
| ECS task-definition revision / task IDs | Revisions/task IDs allocated by ECS; family and cluster are fixed. |
| CloudFront CreateDistribution Resource `*` | Creation has no distribution ARN until allocated; requires the Project=BeyondThePass request tag and CloudFormation forwarding. Existing-distribution writes are account-scoped distribution ARN patterns, forwarding-only; CloudFront does not expose a resource-tag authorization key for these actions. After creation tighten the ID if desired. CloudFront is global, so do not impose Mumbai requested-region on its global API. |
| S3 release object suffix / log stream suffix | Only object names beneath the exact real release/code prefix and streams beneath the one log group. |
| Application boundary Deny `Action:*`, `Resource:*` | Intentional **deny all**, never an Allow or admin grant. |

All four deployment policies together exceed one managed-policy size limit; splitting keeps each below the limit without widening permissions. These are not permissions boundaries for Dev_1 and do not remove permissions from any already-attached user policies. An administrator should review existing grants separately without sharing credential contents.

Official references: [AWS service authorization JSON reference](https://servicereference.us-east-1.amazonaws.com/v1/iam/iam.json), [permissions boundaries](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html), [CloudFormation access control](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/control-access-with-iam.html), [CalledVia condition semantics](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-calledvia), [CloudFront action/resource scope](https://docs.aws.amazon.com/service-authorization/latest/reference/list_cloudfront.html).

## Teardown and remove temporary access

Manual app teardown (approved 24-hour demo; run from repository root after its successful deployment):

```powershell
$approved = (Get-FileHash docs/DEPLOYMENT_PLAN.md -Algorithm SHA256).Hash.ToLowerInvariant()
.\.venv\Scripts\python.exe -m scripts.aws_release delete-app --approved-plan-sha256 $approved
```

CloudFront removal can take time. Await deletion, do not merely set ECS desired count0; ALB/IPs still charge until removed. Private retained ECR/S3 cleanup commands and version-delete review are in `DEPLOYMENT_PLAN.md`. Preserve bounded evidence first. Remove these four temporary user-policy attachments **only after teardown and verification**. Administrator can then delete these four policies and the two boundary policies once task roles have been removed and no references remain; do not remove unrelated grants or shared service-linked roles.

**Teardown schedule rule:** successful deployment acceptance UTC timestamp +24 hours; exact timestamp will be recorded in `PROJECT_STATE.md` and local deployment evidence only after an actual success. No deployment has succeeded yet, so no timestamp is fabricated. **No automatic teardown, scheduler or reminder is implemented.** Keep a manual calendar reminder; a planning allowance does not stop charges.
