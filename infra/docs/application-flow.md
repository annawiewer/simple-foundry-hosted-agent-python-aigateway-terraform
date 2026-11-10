# Guided Terraform application deployment

This opt-in path joins the Terraform infrastructure and tool handoffs to the
root Python agent, then separately enables its daily schedule. The application
helper generates the app-only manifest; there is no Bicep workflow in this
repository. Terraform still owns the
infrastructure; this is **not** a replacement `azd up` or Terraform apply wrapper.

**The normal container source-build path was accepted on November 7, 2026**,
using azd 1.37.2 and the pinned extensions. With registry sharing/default both
true, `docker.remoteBuild=true` built the seven shared application files in ACR
and deployed version 5. Its version-bound digest completed all three GitHub
tools through the intended gateway/model path with correlated telemetry.
The configured image is tagged, not digest-pinned; independent registry reads
matched the build digest before and after inference.

The earlier version 3 used the optional digest-pinned image path and project-local
registry sharing. Its on-demand digest and one manual daily-routine dispatch
remain separate accepted results. The original routine is still disabled;
neither result proves a 09:00 scheduler firing. RemoteTool sharing remains
explicitly project-local, unlike the repaired shared registry.

Every deployment requires separate target-specific approval; these examples
do not authorize changes to an existing deployment. The
[source-build qualification](evidence-map.md#shared-registry-source-build-qualification)
records the existing-environment prerequisites, observed limitations and final
preservation checks. It is not fresh-from-empty lifecycle certification.

## The complete sequence

| Step | Owner and action |
|---|---|
| 1. Infrastructure | Follow the [preparation guide](architecture.md#offline-and-deployment-preparation); review and separately authorize each fresh Terraform plan/apply. |
| 2. Telemetry | Finish the [native telemetry handoff](native-telemetry.md) and fresh second-stage plan/apply, or deliberately retain the supported legacy mode. Pending telemetry stops application preparation. |
| 3. GitHub tools | Follow the [tool guide](toolchain.md): explicit-credential ToolServer creation, fresh Terraform RemoteTool connection plan/apply, then Toolbox creation/readback. |
| 4. Prepare the app | Run the offline `prepare` operation below with the applied contract, connected bootstrap and configured Toolbox receipt. |
| 5. Launch the agent | After separate authorization, select its authentication mode and run `deploy-agent`. No routine is deployed by this step. |
| 6. Bind and verify the runtime identity | Independently read the exact deployed agent version's principal; review its opt-in Terraform role bindings and any required tenant authorization, then [verify one on-demand digest](#verify-one-on-demand-digest) and its traces. |
| 7. Enable the schedule | Only after runtime acceptance, explicitly run `enable-schedule`. Verify the definition and one approved dispatch, then pause a bounded demonstration or separately approve continued daily use. |

Keep **all original Terraform inputs and every applied telemetry/tool handoff**
on subsequent plans. Never reuse saved plans, run Bicep mutation hooks against
these resources or let azd provision the Terraform-owned infrastructure.

## Prerequisites and boundaries

Use Python **3.10+** for this standard-library helper; the copied application
keeps its existing Python 3.13 container and frozen `uv.lock`.
The generated project targets **stable azd 1.37.x**, with exactly **1.0.0**
installed for each of:

- `azure.ai.agents`
- `azure.ai.routines`
- `azure.ai.inspector`
- `azure.ai.projects`
- `azure.ai.connections`
- `azure.ai.toolboxes`

This is the reviewed **source compatibility baseline**; live acceptance used
azd **1.37.2** with these **1.0.0** extensions, not every stable 1.37.x release
or deployment mode. Version checks
use `installedVersion`, never a newer version merely advertised in the catalog.
Older betas, missing dependencies and unreviewed newer versions stop before a
deployment intent. Tool installation/upgrades and an existing azd login must
be handled separately; the helper does not install, log in or switch accounts.
It preserves the caller's CLI profile-directory settings and an explicitly
supplied process-local `AZURE_DEV_USER_AGENT`, not ambient service-principal
secrets or GitHub credentials. The user-agent is forwarded to child processes
without being written into the prepared project.

The target is the already-provisioned public-cloud project in the supplied
subscription/tenant. The caller needs its existing deployment/build/data-plane
permissions and working network access. The helper sets
`AZD_AGENT_SKIP_ROLE_ASSIGNMENTS=true` to disable the agent extension's automatic
developer-RBAC repair; it does not grant missing permissions. Project tool
access must already be enabled. The contract must include the owned registry
connection ID matching the project and exported connection name. Both boolean
sharing choices are accepted; sharing is not a substitute for project ownership
or registry pull permissions. See [project-local compatibility](architecture.md#project-local-registry-compatibility).
Managed-identity model access also requires a grant for the actual deployed
agent identity, not merely the account/project grants; see the
[postdeployment identity handoff](#3-bind-the-deployed-agent-identity).

Use a private parent directory outside the repository, with appropriate OS
access controls. The helper creates a new child directory but does not certify
Windows ACLs. Use an exclusively owned agent name; its routine name will be
`<agent-name>-daily`. Independently verify that these names are appropriate and
that no routine is already active for the agent before confirming deployment.
The helper does **not** check remote name absence, atomically lock resources,
pause an existing schedule or prevent another actor from changing the agent.
azd may create a new version of an existing named agent and upsert an existing
named routine. Confirmation includes acceptance of that target/name ownership.

## 1. Export and prepare offline

After the final reviewed infrastructure and tool stages, export only the named
nonsecret contract to a new file. The bootstrap and receipt below come from
the tool guide, not from invented endpoint values.

```powershell
$TerraformRoot = (Resolve-Path '.\infra').Path
$ApplicationFlow = Join-Path $TerraformRoot 'scripts\application_flow.py'
$Private = 'C:\private\my-new-deployment' # Existing, access-controlled directory.
$Subscription = '<approved-subscription-uuid>'
$Tenant = '<approved-tenant-uuid>'
$Contract = Join-Path $Private 'deployment.applied.json'
$ConnectedBootstrap = Join-Path $Private 'tools.connected.json'
$BoxReceipt = Join-Path $Private 'toolbox.created.jsonl' # Or latest configured inspection/rotation receipt.
$ApplicationWorkspace = Join-Path $Private 'hosted-application'

$Document = terraform "-chdir=$TerraformRoot" output -json deployment_contract
if ($LASTEXITCODE -ne 0) { throw 'Contract export failed.' }
$Document | Out-File -LiteralPath $Contract -Encoding utf8 -NoClobber

python -B $ApplicationFlow prepare `
  --workspace $ApplicationWorkspace `
  --subscription-id $Subscription --tenant-id $Tenant `
  --contract $Contract --bootstrap $ConnectedBootstrap --tool-receipt $BoxReceipt `
  --repository '<owner/repository>' --agent-name '<unique-lowercase-agent-name>'
if ($LASTEXITCODE -ne 0) { throw 'Application preparation stopped.' }
```

`prepare` itself makes no CLI or Azure call. It reuses the environment adapter
and tool receipt validators, checks matching context/connection/Toolbox version
and repository, and rejects incomplete outcomes. For custom model profiles,
pass `--model-alias-key` and `--mini-model-alias-key`; both must advertise Responses.
Re-export older contracts that lack `agents.registry_connection_id`; do not
invent that field or substitute a parent-account/other-project connection.
These are local consistency checks, not current Azure readback, endpoint
ownership proof, role propagation or working network/credential verification.

The new workspace contains:

| Artifact | Purpose |
|---|---|
| `azure.yaml` | JSON-form YAML containing only the hosted agent and gated routine, with provision/down guards |
| `app` | Exactly the seven shared Docker/runtime/lock files needed for the hosted build |
| `.azure` | A new azd environment with only the validated nonsecret seed values |
| `prepared.json` | Nonsecret bindings and hashes to detect accidental changes |

State, tfvars, credentials, receipts, `.git`, infrastructure, mutation hooks and
dependencies are not copied into `app`. The helper does not create an
`azure.ai.project`, connection, Toolbox or memory-store service. It supplies
`FOUNDRY_PROJECT_ENDPOINT` and the existing-project marker; it does not create
another registry owner or opt into registry-reuse provisioning.

Do not edit the prepared snapshot, add files/hooks or run raw `azd up`, `down`
or a bulk deploy there. Both services are disabled unless their process-only
gate is set by the selected helper operation; service hooks also check that
operation. The saved environment must not contain those gates or a runtime key.
The pinned hosted extension may save `ENABLE_HOSTED_AGENTS=true` and
`ENABLE_CAPABILITY_HOST=false` during predeploy. Only those exact additional
boolean values are accepted; they do not prove activation, relax the original
saved context, or turn an unconfirmed receipt into success. Other global
outputs, including conditional `AI_PROJECT_*` settings, remain rejected.
Hashes are drift detection, **not** signatures, ownership locks or protection
against someone deliberately rewriting the workspace and receipts.

### Default: build and deploy the source

For the normal route, use `prepare` without `--prebuilt-image`, then follow
[the agent deployment step](#2-explicitly-deploy-the-agent). No separate
`az acr build` or image-passthrough preparation is needed. The generated
[`manifest`](../scripts/application_flow.py#L146-L193) uses
`docker.remoteBuild=true`, the existing registry handoff and only the copied
`app` context; it omits `registryConnectionId` and does not provision infrastructure.

On the accepted toolchain, the integrated build produced a tagged image
reference for the new version. Record the exact run, source hashes and output
image; independently match the deployed reference and its registry tag/digest
before accepting runtime behavior. A successful build or unchanged tag string
does not make that reference immutable. If a digest-pinned deployment is
required, use the optional route below instead. Keep the
[local-versus-cloud timeout boundary](#stops-receipts-and-later-lifecycle-work)
in mind before authorizing either build path.

### Optional existing image

By default, preparation selects the integrated ACR remote-build path.
To deploy an image already built in the contract's registry, add
`--prebuilt-image` to the **prepare** command for a new workspace:

```powershell
python -B $ApplicationFlow prepare `
  --workspace $ApplicationWorkspace `
  --subscription-id $Subscription --tenant-id $Tenant `
  --contract $Contract --bootstrap $ConnectedBootstrap --tool-receipt $BoxReceipt `
  --repository '<owner/repository>' --agent-name '<unique-lowercase-agent-name>' `
  --prebuilt-image '<declared-registry-host>/<repository>@sha256:<64-lowercase-hex-digest>'
if ($LASTEXITCODE -ne 0) { throw 'Application preparation stopped.' }
```

Use the digest returned by successful image-build/registry readback, not a CI
success flag or a mutable tag. The image host must match the contract's exact
`agents.registry_endpoint`, not a hostname inferred from the registry ARM name.
Foreign registries, tag-only references, credentials, URLs, query strings and
malformed digests are rejected before the workspace is created.

This selects `docker.imagePassthrough=true` and the literal pinned `image`;
it omits `remoteBuild` and the optional `registryConnectionId`. Like the
source-build manifest, it uses platform-default ACR handling rather than
passing the ACR connection as an external-registry credential selector.
The full connection ARM ID is still required
and checked against the exact project and connection name in the Terraform
contract. It is not a `--from-package` override. The seven shared
application files are still copied unchanged into `<workspace>\app`:
`Dockerfile`, `.dockerignore`, `pyproject.toml`, `uv.lock`, `main.py`,
`repo_digest_agent.py`, and `github_mcp_middleware.py`. No infrastructure,
connection, role or routine is created by preparation.

The previous `--use-default-acr` spelling remains accepted with
`--prebuilt-image`, but is no longer needed for new workspaces. This default
retains exact-registry image validation, full connection ARM-ID ownership
checks and no-role-assignment safeguards. It does not grant pull access or
prove which identity the hosted service will use. Verify image retrieval and
the actual runtime identity independently.

The historical `not_a_registry_connection` failure came from explicitly
selecting the ordinary ManagedIdentity ACR connection in a prebuilt manifest.
It was not a demonstrated failure of the normal source-build path, which
already omitted that selector. Neither omitting the selector nor a successful
image pull proves that Azure honored the connection's requested sharing flag.

The selection is recorded in `prepared.json`, validated against the saved
registry, and included in manifest integrity checks and the deployment's
prepared fingerprint. Do not edit a prepared image selection in place.
Existing image-less and named-connection workspaces retain their original
validation and deployment semantics; the helper does not silently migrate
them. Prepare a new workspace to use the corrected ACR default. Prebuilt workspaces whose
manifests contain the full registry connection ARM ID must be prepared again in
a new workspace; preserve their original manifests, local state and receipts.
Run the same `deploy-agent`
command below; neither deployment nor schedule activation accepts an image
override. Build success, image existence, pull permissions and the actual
deployed image still require independent evidence; offline preparation does
not query the registry or certify the image's contents.

### Build the selected source in the existing registry

**This is the optional digest-pinned route**, not a prerequisite for the
[normal integrated build](#default-build-and-deploy-the-source).
An immutable image need not be an unexplained prerequisite. The first
`prepare` command creates a reviewable build context without deploying anything.
After approving the build, submit **only its `app` directory** to the declared
registry. This keeps local state and credentials out of the upload and builds
the Linux AMD64 image expected by the hosted runtime, even on an ARM64 developer
machine. The source boundary is enforced by
[`application_flow.py` (`prepare`)](../scripts/application_flow.py).

Before executing `az acr build`, record the unique tag, UTC submission time and
source-file hashes. The example keeps its variables in memory; it does not
persist a build receipt for you.

```powershell
$Prepared = Get-Content -LiteralPath (Join-Path $ApplicationWorkspace 'prepared.json') -Raw |
  ConvertFrom-Json
$Registry = $Prepared.environment.AZURE_CONTAINER_REGISTRY_NAME
$RegistryId = $Prepared.environment.AZURE_CONTAINER_REGISTRY_RESOURCE_ID
$RegistryGroup = ($RegistryId -split '/')[4]
$ImageTag = "source-$([guid]::NewGuid().ToString('N'))"
$ImageRepository = $Prepared.agent_name
$RegistryHost = $Prepared.environment.AZURE_CONTAINER_REGISTRY_ENDPOINT
$BuildContext = (Resolve-Path (Join-Path $ApplicationWorkspace 'app')).Path
$Dockerfile = Join-Path $BuildContext 'Dockerfile'
$SubmittedAt = [DateTimeOffset]::UtcNow

az acr build --subscription $Subscription `
  --registry $Registry --resource-group $RegistryGroup `
  --file $Dockerfile --platform linux/amd64 `
  --image "${ImageRepository}:$ImageTag" --timeout 900 --no-wait --no-logs `
  --output json $BuildContext | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Warning 'Submission is uncertain; reconcile the unique tag before any retry.'
}

# Successful asynchronous submission can return no JSON. Discover, do not resubmit.
$Deadline = (Get-Date).AddMinutes(16)
$RunId = $null
$Run = $null
do {
  if (-not $RunId) {
    $Runs = @(az acr task list-runs --subscription $Subscription `
      --registry $Registry --resource-group $RegistryGroup --top 20 `
      --output json | ConvertFrom-Json -ErrorAction Stop)
    if ($LASTEXITCODE -ne 0) { throw 'Run discovery failed; preserve the tag and submission time.' }
    $MatchingRuns = @($Runs | Where-Object {
      @($_.outputImages | Where-Object {
        $_.registry -ceq $RegistryHost -and
        $_.repository -ceq $ImageRepository -and $_.tag -ceq $ImageTag
      }).Count -eq 1
    })
    if ($MatchingRuns.Count -gt 1) { throw 'Multiple matching runs; reconcile without resubmitting.' }
    if ($MatchingRuns.Count -eq 1) {
      $RunId = $MatchingRuns[0].runId
      if ([DateTimeOffset]$MatchingRuns[0].createTime -lt $SubmittedAt) {
        throw 'The discovered run predates this submission.'
      }
    }
  }
  if ($RunId) {
    $Run = az acr task show-run --subscription $Subscription `
      --registry $Registry --resource-group $RegistryGroup --run-id $RunId `
      --output json | ConvertFrom-Json -ErrorAction Stop
    if ($LASTEXITCODE -ne 0) { throw 'Build readback failed; preserve the run ID.' }
    if ($Run.status -in @('Succeeded', 'Failed', 'Canceled', 'Error', 'Timeout')) { break }
  }
  Start-Sleep -Seconds 10
} while ((Get-Date) -lt $Deadline)
if (-not $Run -or $Run.status -ne 'Succeeded') {
  throw 'No accepted image: preserve the unique tag, time and any run ID; inspect without resubmitting.'
}
if ($Run.platform.os -cne 'linux' -or $Run.platform.architecture -cne 'amd64') {
  throw 'The completed run has the wrong platform.'
}
$Images = @($Run.outputImages | Where-Object {
  $_.registry -ceq $RegistryHost -and
  $_.repository -ceq $ImageRepository -and $_.tag -ceq $ImageTag
})
if ($Images.Count -ne 1 -or $Images[0].digest -cnotmatch '^sha256:[0-9a-f]{64}$') {
  throw 'The successful run did not identify one matching immutable image.'
}
$ManifestDigest = az acr repository show --subscription $Subscription `
  --name $Registry --image "${ImageRepository}:$ImageTag" --query digest --output tsv
if ($LASTEXITCODE -ne 0 -or $ManifestDigest -cne $Images[0].digest) {
  throw 'Registry manifest and source-bound build disagree.'
}
$PrebuiltImage = "${RegistryHost}/${ImageRepository}@$ManifestDigest"
```

Use an absolute Dockerfile path: a relative `--file Dockerfile` can resolve
against the caller's directory rather than the prepared context. The bounded
discovery above reads only the 20 most recent runs and may remain inconclusive
on a busy registry or before output-image metadata appears. Keep the matched
run ID and independently verified digest with the recorded submission details.
An inconclusive
readback is not permission to submit another build.
Prepare a **new release workspace** with the same applied handoffs and repository,
passing `$PrebuiltImage` to `--prebuilt-image`. The platform-default ACR path
is selected automatically. Do not edit the
build workspace's manifest or reuse a deployment receipt. Retain the source
revision and confirm that the seven release files match the uploaded context.
An ACR build consumes build capacity; neither a successful build nor a digest
proves hosted pull, identity or application readiness.

## 2. Explicitly deploy the agent

Choose **one** authentication mode after independent approval:

```powershell
python -B $ApplicationFlow deploy-agent `
  --workspace $ApplicationWorkspace `
  --subscription-id $Subscription --tenant-id $Tenant `
  --managed-identity --confirm-agent-deployment
if ($LASTEXITCODE -ne 0) { throw 'Stop. Preserve the application receipt and review the remote outcome.' }
```

Or, if a runtime gateway key is deliberately required, populate a dedicated
process environment variable through your approved secret-handling mechanism.
Do not put its value in shell history or the command line:

```powershell
python -B $ApplicationFlow deploy-agent `
  --workspace $ApplicationWorkspace `
  --subscription-id $Subscription --tenant-id $Tenant `
  --gateway-key-env SELECTED_GATEWAY_RUNTIME_KEY --confirm-agent-deployment
if ($LASTEXITCODE -ne 0) { throw 'Stop. Preserve the application receipt and review the remote outcome.' }
```

The helper never retrieves a gateway key or GitHub credential. A selected
gateway key reaches **only the agent-deployment child process**, not tooling
inspection or schedule deployment. Core service `env` expansion delivers it to
the intended Foundry agent configuration; the helper does not write it into
its files, receipts or azd dotenv, or place it in subprocess arguments.
Raw deploy stdout/stderr are discarded. This is still a **secret-delivery
operation**: these safeguards do not certify every azd/extension cache, log or
cloud diagnostic. Qualify those separately and protect the private workspace.
Unexpected dotenv entries stop completion rather than being echoed or cleaned up.

Only the selected agent service is deployed. The helper never invokes the agent
or GitHub tools to test it. A `cli-completed` receipt requires azd success plus
matching locally registered agent name/version/endpoint. It is not independent
GET readback, image-pull proof, successful model/tool use or hosted identity
acceptance. The original shared application determines runtime behavior.

## 3. Bind the deployed agent identity

Read the exact deployed name/version independently from the project data plane:

```http
GET <project-endpoint>/agents/<agent-name>/versions/<version>?api-version=v1
```

Use `instance_identity.principal_id`, not an application/client ID, the Foundry
account identity or the project identity. Recheck it after a version/identity
change; deployment success alone does not establish runtime authorization.
The helper deliberately retains `AZD_AGENT_SKIP_ROLE_ASSIGNMENTS=true`.

Add a separately reviewed nonsecret input file to the **same root and workspace**,
retaining all original inputs and applied telemetry/tool handoffs:

```hcl
hosted_agent_principals = {
  digest = "<verified-agent-instance-principal-uuid>"
}
```

The map defaults to empty, normalizes UUID case and rejects duplicate principals
and account/project identities. Labels are stable Terraform address keys.
The root adds only these selected bindings:

| Role | Exact scope | Controlling input |
|---|---|---|
| AI Gateway Models User | This AI Gateway | `enable_foundry_gateway_model_access` |
| Monitoring Metrics Publisher | The agent Application Insights component | `enable_foundry_monitoring_integration` |

No hosted-agent Tools User, Contributor or subscription/resource-group grant is
added. Toolbox tool access continues through the separately authorized project
identity. Do not list the same Models User binding in `gateway_access_principals`
while hosted model access is enabled. Monitoring-only bindings may coexist with
a separately owned model caller.

Review a fresh refresh-enabled plan with **all** existing inputs plus this file,
then separately authorize apply and read back the exact role scopes/principal.
Changing/removing a label, principal or integration flag can remove permissions;
do not treat that as an automatic release or identity-migration operation.

**Existing grants need explicit ownership review.** In the November 7 acceptance,
the two previously operational runtime grants were independently checked and
adopted into the original authoritative state through an import-only plan:
zero Azure resource mutations, unchanged outputs and lineage, 42 managed
resources and 14 scoped roles. A fresh ordinary plan then reported no changes.
For another deployment, if adopting matching grants, use explicit
imports to these addresses rather than creating duplicate owners:

```hcl
import {
  to = azapi_resource.hosted_agent_runtime_access["models-digest"]
  id = "<gateway-resource-id>/providers/Microsoft.Authorization/roleAssignments/<existing-assignment-uuid>?api-version=2022-04-01"
}
import {
  to = azapi_resource.hosted_agent_runtime_access["monitoring-digest"]
  id = "<agent-insights-resource-id>/providers/Microsoft.Authorization/roleAssignments/<existing-assignment-uuid>?api-version=2022-04-01"
}
```

Import reads explicitly select the role-assignment API used by this root.
Independently verify the existing assignment's name, principal, role and scope
against the configuration's deterministic UUIDv5 name. Stop on a mismatch,
replacement or unrelated change; do not copy/fork state or force adoption.
These are illustrative import blocks, not an instruction to apply them to the
accepted environment.

Tenant authorization is a separate prerequisite. The accepted run needed an
owner-approved exception for exactly the deployed Agent Identity in an enabled
Conditional Access policy. Terraform does not change tenant policies, and RBAC
cannot substitute for that authorization. Do not copy the exception broadly.

### Verify one on-demand digest

Use the same pinned azd/extensions and approved login/profile as deployment.
The helper does not change your shell's directory or selected azd environment.
Read the prepared bindings and inspect the deployed service explicitly:

```powershell
$Prepared = Get-Content -LiteralPath (Join-Path $ApplicationWorkspace 'prepared.json') -Raw |
  ConvertFrom-Json
azd ai agent show $Prepared.agent_name `
  --cwd $ApplicationWorkspace --environment $Prepared.environment.AZURE_ENV_NAME `
  --output json --no-prompt
if ($LASTEXITCODE -ne 0) { throw 'Agent readback failed; do not invoke.' }
```

Match the returned project, name and version to the completed
`agent.receipt.jsonl` and the independent version readback above. Copy the
displayed **Responses invocation endpoint** for that agent; the receipt's
`agent.endpoint` is a version-resource URL, not an invocation URL.
In the accepted source-build run, generic `azd show --output json` returned
only project/service mappings; the actual endpoint came from
`azd ai agent show`. Do not infer a deployed endpoint from project metadata.
Keep the repository from `prepare`, available as
`$Prepared.environment.GITHUB_REPOSITORY`.

**Obtain separate approval before the next command:** it creates a real
session/conversation and runs model and GitHub-tool requests. Use an empty
private directory outside the prepared workspace so invocation context cannot
change the deployment snapshot required by `enable-schedule`. The explicit
endpoint/version selects the target, not an ambient azd environment:

```powershell
$AgentVersion = '<independently-verified-version>'
$ResponsesEndpoint = '<verified-responses-invocation-endpoint>'
$VerificationWorkspace = Join-Path $Private 'on-demand-check'
New-Item -ItemType Directory -Path $VerificationWorkspace -ErrorAction Stop | Out-Null

azd ai agent invoke `
  --agent-endpoint $ResponsesEndpoint --version $AgentVersion `
  --new-session --new-conversation --timeout 300 --debug-latency=false `
  --cwd $VerificationWorkspace --no-prompt --output raw `
  "Create a concise daily repo digest for $($Prepared.environment.GITHUB_REPOSITORY)." |
  Out-File -LiteralPath (Join-Path $VerificationWorkspace 'response.txt') `
    -Encoding utf8 -NoClobber -ErrorAction Stop
if ($LASTEXITCODE -ne 0) { throw 'Invocation failed or is unconfirmed; preserve evidence and stop.' }
```

Keep the response, returned session/request/trace IDs and UTC run window private.
Confirm the resolved agent version and a completed response, not merely HTTP
200, CLI exit zero or an active hosted version. Inspect the agent trace for
successful calls to all three GitHub tools and truthful results; empty results
must agree with the selected repository. In the agent and gateway Application
Insights resources, correlate that run's IDs/time window with the intended
gateway/model and GitHub backend requests. Missing or contradictory evidence
means acceptance is incomplete; do not enable the schedule or blindly retry
after a timeout. No redeployment or `azd up` is needed for this check.

The version 5 source-build run completed all three read-only tools. It scanned
0 pull requests, 0 issues and 20 workflow runs; none of those workflows had
failed. The shared middleware reports `scanned_count` and
`possibly_truncated`, and the digest describes observations, not exhaustive
repository totals. An earlier MCP request returned 499 with an inbound
`AuthorizationServiceError`; subsequent actual tool calls and the final digest
completed successfully. That trace is not error-free; see the
[recorded qualification limits](evidence-map.md#shared-registry-source-build-qualification).

## 4. Separately enable the daily schedule

Review the agent receipt and complete the intended runtime checks under their
own approval before enabling automation:

```powershell
python -B $ApplicationFlow enable-schedule `
  --workspace $ApplicationWorkspace `
  --subscription-id $Subscription --tenant-id $Tenant `
  --confirm-enable-schedule
if ($LASTEXITCODE -ne 0) { throw 'Stop. Preserve the schedule receipt and review its remote state.' }
```

This deploys only `<agent-name>-daily`, not the agent again. It requires a complete
matching agent receipt and unchanged recorded azd state. The definition is enabled
when this operation applies it: **09:00 `America/Los_Angeles`**, using the repository
explicitly selected in `prepare`, unlike the upstream Bicep manifest's fixed
repository prompt. It does not invoke an immediate test run.
The routine references the agent name, not a permanently pinned agent version;
later external changes are not detected by these local receipts.

The routine uses the stable camelCase authoring fields `agentName`,
`cronExpression` and `timeZone`. Their names and the agent binding are checked
by the offline application-flow tests.

### Verify the routine and pause a demonstration

Use the explicit project endpoint and tenant for remote routine commands.
Do not rely on `--environment` to override a previously selected routine
context. First inspect the deployed definition and match its agent, repository
input, enabled state, cron and timezone to the prepared manifest:

```powershell
$Routine = "$($Prepared.agent_name)-daily"
$RoutineContext = @(
  '--project-endpoint', $Prepared.environment.FOUNDRY_PROJECT_ENDPOINT,
  '--tenant-id', $Tenant, '--no-prompt', '--output', 'json', '--timeout', '90s'
)
azd ai routine show $Routine @RoutineContext
if ($LASTEXITCODE -ne 0) { throw 'Routine readback failed.' }
```

A manual dispatch is real model/tool use and requires approval. It proves the
routine action path, not that the wall-clock scheduler has fired at 09:00.
For a bounded demonstration, pause the routine in `finally`, including after
a failed or uncertain dispatch:

```powershell
try {
  azd ai routine dispatch $Routine --async @RoutineContext
  if ($LASTEXITCODE -ne 0) {
    throw 'Dispatch is unconfirmed; inspect execution history rather than dispatching again.'
  }
} finally {
  azd ai routine disable $Routine @RoutineContext
  if ($LASTEXITCODE -ne 0) { throw 'Pause is unconfirmed: inspect and reconcile the routine now.' }
}
azd ai routine show $Routine @RoutineContext
if ($LASTEXITCODE -ne 0) { throw 'Paused-state readback failed.' }
azd ai routine run list $Routine --top 10 @RoutineContext
if ($LASTEXITCODE -ne 0) { throw 'Execution-history readback failed.' }
```

Confirm the routine is disabled; disabling preserves its definition and is
not evidence that an already dispatched run was canceled. Dispatch is
asynchronous: retain its dispatch/action correlation IDs and use bounded
`run list --top 10` readbacks. In the pinned extension, `--async` suppresses
descriptive output; it does not wait for agent completion. A dispatch
acknowledgment, a `Finished` delivery record or an unrelated historical run is
not enough: match dispatch, session and response IDs to the expected agent
version's completed digest and successful model/tool telemetry.

**Empty CLI history can be a compatibility issue, not a failed run.** The pinned
CLI expects a `value` collection; the accepted service returned `data`.
If CLI history is empty or null, use this single bounded GET with the same
approved Azure login, explicit project and tenant. It performs no dispatch,
keeps the token in memory, rejects redirects and caps the response at 1 MiB:

```powershell
$AccessToken = az account get-access-token --subscription $Subscription `
  --tenant $Tenant --resource https://ai.azure.com --query accessToken --output tsv
if ($LASTEXITCODE -ne 0 -or -not $AccessToken) { throw 'Routine-history authentication failed.' }
$Handler = [System.Net.Http.HttpClientHandler]::new()
$Handler.AllowAutoRedirect = $false
$Client = [System.Net.Http.HttpClient]::new($Handler)
$Client.Timeout = [TimeSpan]::FromSeconds(60)
$Client.MaxResponseContentBufferSize = 1MB
$Response = $null
try {
  $Client.DefaultRequestHeaders.Authorization =
    [System.Net.Http.Headers.AuthenticationHeaderValue]::new('Bearer', $AccessToken)
  $RunsUrl = "$($Prepared.environment.FOUNDRY_PROJECT_ENDPOINT.TrimEnd('/'))/routines/" +
    "$([Uri]::EscapeDataString($Routine))/runs?api-version=v1&limit=10"
  $Response = $Client.GetAsync($RunsUrl).GetAwaiter().GetResult()
  $Response.EnsureSuccessStatusCode() | Out-Null
  $History = $Response.Content.ReadAsStringAsync().GetAwaiter().GetResult() |
    ConvertFrom-Json -ErrorAction Stop
  if ($null -ne $History.data) { $Runs = @($History.data) }
  elseif ($null -ne $History.value) { $Runs = @($History.value) }
  else { throw 'History returned no recognized collection; do not redispatch.' }
  $Runs | Select-Object id, dispatch_id, action_correlation_id, status, phase, session_id, response_id
} finally {
  if ($Response) { $Response.Dispose() }
  $Client.Dispose()
  $AccessToken = $null
}
```

Inspect only the matching dispatch; preserve uncertain or incomplete results.
An empty bounded page is not proof of absence. Do not automatically redispatch
after a timeout, empty CLI output or an inconclusive history read.
The November 7 acceptance used this API shape to recover the completed run and
correlate its session/response with agent and gateway traces. The routine was
independently verified disabled afterward.

Leaving the daily routine enabled is a separate operator decision that permits
recurring usage. If that is the intended outcome, omit the demonstration pause
only after explicit approval and verify the resulting enabled state.

## Stops, receipts and later lifecycle work

Each operation gets one exclusive append-only journal:
`agent.receipt.jsonl` or `schedule.receipt.jsonl`. A durable `pending` record
precedes the deploy process; success records `cli-completed`. Failure,
interruption, timeout or mismatched completion metadata records `unconfirmed`
when possible. A partial journal also blocks progression.

**Never delete or edit a receipt, regenerate a workspace or blindly rerun a
mutation to get past a stop.** A cloud operation or its remote build can continue
after a local timeout. The helper makes no second deployment attempt and does
not automatically enable the schedule, recover, roll back, rotate credentials,
update an existing release or delete resources. Retain all artifacts, separately
inspect the remote outcome and review the next action. An already completed
workspace is also single-attempt, not an unattended release pipeline.

The total command deadline defaults to 900 seconds and accepts
`--timeout-seconds` from 30 to 1800. Prerequisite failure before an intent is not
a deployment attempt; a separately approved tool installation can resolve that
specific prerequisite. Do not equate any source/offline success with full parity.

This is a local CLI deadline, not an ACR server-side build limit. The inspected
[azd 1.37.2 source-build request](https://github.com/Azure/azure-dev/blob/bb2c1200d6672417522ad1c52195080cb934793a/cli/azd/pkg/project/container_helper.go#L1172-L1193)
does not set the cloud `Timeout` field. If a separate cloud-build ceiling is
required, establish that bound before deployment; stopping the local process
does not establish that the remote run has stopped.

## Reviewed azd source contracts

Source inspection is pinned to Azure/azure-dev commit
`1273b0ddd9a04b09352f67632a6f1e3952fc5df0`, not a moving branch:

| Contract | Canonical source |
|---|---|
| Core service selection and deployment | [deploy action](https://github.com/Azure/azure-dev/blob/1273b0ddd9a04b09352f67632a6f1e3952fc5df0/cli/azd/internal/cmd/deploy.go) and [service importer](https://github.com/Azure/azure-dev/blob/1273b0ddd9a04b09352f67632a6f1e3952fc5df0/cli/azd/pkg/project/importer.go) |
| Process fallback and service gates | [environment](https://github.com/Azure/azure-dev/blob/1273b0ddd9a04b09352f67632a6f1e3952fc5df0/cli/azd/pkg/environment/environment.go) and [service config](https://github.com/Azure/azure-dev/blob/1273b0ddd9a04b09352f67632a6f1e3952fc5df0/cli/azd/pkg/project/service_config.go) |
| Automatic role repair opt-out | [developer RBAC check](https://github.com/Azure/azure-dev/blob/1273b0ddd9a04b09352f67632a6f1e3952fc5df0/cli/azd/extensions/azure.ai.agents/internal/project/developer_rbac_check.go) |
| Existing-project gate | [ACR feature](https://github.com/Azure/azure-dev/blob/1273b0ddd9a04b09352f67632a6f1e3952fc5df0/cli/azd/extensions/azure.ai.agents/internal/synthesis/acr_feature.go) |
| Agent environment and completion | [hosted service target](https://github.com/Azure/azure-dev/blob/1273b0ddd9a04b09352f67632a6f1e3952fc5df0/cli/azd/extensions/azure.ai.agents/internal/project/service_target_agent.go) |
| Explicit endpoint and version-bound on-demand invocation | [invoke command](https://github.com/Azure/azure-dev/blob/1273b0ddd9a04b09352f67632a6f1e3952fc5df0/cli/azd/extensions/azure.ai.agents/internal/cmd/invoke.go) |
| Routine authoring | [camelCase parser](https://github.com/Azure/azure-dev/blob/1273b0ddd9a04b09352f67632a6f1e3952fc5df0/cli/azd/extensions/azure.ai.routines/internal/pkg/routines/authoring.go) |
| Routine dispatch and history | [dispatch command](https://github.com/Azure/azure-dev/blob/1273b0ddd9a04b09352f67632a6f1e3952fc5df0/cli/azd/extensions/azure.ai.routines/internal/cmd/routine_dispatch.go), [run-list command](https://github.com/Azure/azure-dev/blob/1273b0ddd9a04b09352f67632a6f1e3952fc5df0/cli/azd/extensions/azure.ai.routines/internal/cmd/routine_run.go) and [wire models](https://github.com/Azure/azure-dev/blob/1273b0ddd9a04b09352f67632a6f1e3952fc5df0/cli/azd/extensions/azure.ai.routines/internal/pkg/routines/api_models.go) |
