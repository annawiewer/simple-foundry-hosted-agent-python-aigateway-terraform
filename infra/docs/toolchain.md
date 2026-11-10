# GitHub tools for the Terraform application path

The optional [tool runner](../scripts/configure_tools.py) connects the GitHub
tool service to the Terraform-created Foundry project. It is separate from
Terraform and azd so GitHub credentials never enter Terraform arguments, state
or plans. The upstream Bicep provisioning path is not included in this repository.

**The November 7, 2026 hosted digest exercised all three real GitHub tools.**
An isolated ToolServer create/update/read/delete check also used public Learn
MCP and synthetic nonsecret headers, not GitHub credentials. It verified
nonsecret configuration, endpoint stability and ordinary-GET header omission,
not real credential rotation or the production runner's full lifecycle.
The [acceptance matrix](evidence-map.md) separates these results and their limits.

Creating a ToolServer uploads the explicitly selected
credential to Azure; creating a Toolbox writes to Foundry. Review and authorize
the actual target and credential separately.
These examples do not authorize changes to an existing deployment or reuse of
saved plans. Omitted header values do not prove what was stored or delivered.

## Owners and limits

| Component | Sole writer |
|---|---|
| Gateway, Foundry project, roles and `aigw-github` RemoteTool connection | Terraform |
| Complete `github` ToolServer, policies and selected GitHub credential | This explicitly invoked runner |
| One named Toolbox and its initial version | This explicitly invoked runner |
| Application/azd environment, runtime gateway key, agent and routine | Not changed by this runner |

Never run the Bicep configuration hooks over these resources. Do not add a
Terraform ToolServer stub or put credentials in tfvars, JSON inputs or receipts.
The runner does not call `gh`, `listSecrets`, azd, role-assignment APIs, inference
or tool invocation. It does not install dependencies, change CLI context,
register providers, delete resources, adopt existing resources or migrate state.

**Exclusive ownership is a prerequisite, not a service lock.** The selected
2025 ToolServer path must not rely on `If-None-Match` for atomic creation; see
the [pinned CLI warning and its limits](tool-credential-boundary.md#selected-2025-contract).
A preceding GET cannot prevent another writer racing the PUT. Toolbox creation
is also a GET followed by a non-idempotent version POST. The operator must
exclude competing Bicep, Terraform, hook and manual writers before confirming
ownership. Existing names are rejected, even if they look compatible.
Credential rotation uses the fresh specific ETag and rejects drift; live ETag
enforcement still requires qualification.

Every invocation requires a new append-only `.jsonl` receipt in an existing
private directory. A durable intent is written before a mutation. Keep the
latest receipt, including failures: it binds the owner, configuration, target,
ETag and known Toolbox version. Receipts are not secrets or Terraform state,
but contain deployment metadata and should remain outside Git.

New ToolServer creation uses **version-2 receipts** and a versioned request
hash. Version-1 receipts still validate against their original request body
and hash, including existing Toolbox metadata. Inspection preserves that
version; it never upgrades or rewrites historical records. Version-1 receipts
cannot authorize credential rotation or Toolbox creation. A changed
configuration needs separate review; there is no automatic migration writer.
The explicit compatibility-repair command below is a separately authorized
transition, not a way to use v1 receipts for ordinary writes.

## Before running

Use the full application root, Python 3 and an existing Azure CLI login for the
explicit subscription, tenant and public Azure cloud. No extra Python package
or gateway CLI extension is required. The root must already be deployed under
reviewed ownership, with project tool access enabled.
The caller also needs existing ToolServer management and Foundry Toolbox
data-plane permissions. The runner does not grant them automatically.

Select a repository-restricted, read-only GitHub credential through your approved
secret-handling process. Populate a named environment variable without putting
the value in shell history. The runner reads only the variable explicitly named
by `--credential-env`; it never retrieves the current GitHub CLI login.
`--confirm-read-only-credential` is an operator attestation, **not an automated
permissions audit**. Neither a token prefix nor `X-MCP-Readonly` proves least
privilege. The configured tools are `list_pull_requests`, `list_issues` and
`actions_list`; the credential must restrict which repositories they can read.

The runner requests endpoint `required=true` so an endpoint failure fails the
federation, plus Medium gateway tool content safety with `scope=resource`.
This is retained configuration, not proof of runtime policy enforcement.
The [native support review](evidence-map.md#native-content-safety-support-boundary)
identifies content safety as unsupported for this gateway resource/API; do not
rely on that requested policy for MCP protection. Optional
`--allow-client-cidr` arguments select an MCP-only IP allow list; repeat the flag
for multiple IPv4/IPv6 ranges. Omitting it allows all caller IPs at that policy
layer. The model-only Terraform `model_allowed_client_cidrs` input is deliberately
not reused. Rotation preserves the complete original tool configuration rather
than changing policies, tools, backend or IP rules.

## 1. Export the applied bootstrap

These are illustrative PowerShell commands for a separately approved deployment.
Set the paths and IDs for that deployment; use host-native paths on other systems.

```powershell
$TerraformRoot = (Resolve-Path '.\infra').Path
$Runner = Join-Path $TerraformRoot 'scripts\configure_tools.py'
$Private = 'C:\private\my-new-deployment' # An existing private directory.
$Subscription = '<approved-subscription-uuid>'
$Tenant = '<approved-tenant-uuid>'
$Bootstrap = Join-Path $Private 'tools.bootstrap.json'

$Document = terraform "-chdir=$TerraformRoot" output -json gateway_toolchain_bootstrap
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap export failed.' }
$Document | Out-File -LiteralPath $Bootstrap -Encoding utf8 -NoClobber
```

Use this named, nonsecret output, not a state file or the entire Terraform output.
The helper verifies its API, IDs, workspace, project endpoint and selected CLI
subscription/tenant. It will not switch your account for you.

## 2. Create the GitHub ToolServer

After explicit approval to upload the selected credential:

```powershell
$ServerReceipt = Join-Path $Private 'toolserver.created.jsonl'
$ToolVariables = Join-Path $Private 'tools.ready.tfvars.json'

python -B $Runner create-toolserver `
  --bootstrap $Bootstrap --subscription-id $Subscription --tenant-id $Tenant `
  --repository '<owner/repository>' `
  --credential-env SELECTED_GITHUB_MCP_TOKEN `
  --confirm-read-only-credential --confirm-exclusive-owner `
  --receipt $ServerReceipt --tfvars $ToolVariables
if ($LASTEXITCODE -ne 0) { throw 'Stop and inspect the retained receipt.' }
```

This performs one PUT only after the precise missing-ToolServer response. It
then uses bounded GETs to check the owner and complete nonsecret configuration.
It accepts absent/empty credential headers and null placeholders for only
`Authorization`, `X-MCP-Readonly` and `X-MCP-Tools`. Unknown header names or any
non-null values, including masks and empty arrays, stop the flow. Null
placeholders are not classified as exposed secrets, but do not prove the
stored credential or restriction-header values.
The full PUT response is not projected, and raw HTTP/CLI errors are not logged.

The runner exports the service-returned URL from one unambiguous
`properties.gatewayEndpoints` entry with `api=mcp`, or the legacy
`properties.mcpEndpointUrl`. If both are returned, they must agree. URLs must
remain on the declared gateway origin; optional base-URL metadata must be
credential-free, on that origin, and consistent with the invocation path.
Path and case are preserved; no route is invented.

Version-2 readback requires the boolean `required=true` and resource-scoped
policies. Explicit fail-open behavior, missing safety evidence, unknown
configuration fields or policy drift block the handoff. Read-only version-1
inspection also recognizes its original explicit `failureMode=failClosed`
when `required` is absent, but never accepts an explicit `required=false`.
`configured` means matching nonsecret readback, not a working MCP call,
effective credential permissions or clean cloud diagnostic logs.

### Explicit repair of an unconfirmed legacy creation

Use this only after separately reviewing and authorizing an existing-resource
update and credential re-submission. It requires the original version-1
`create-toolserver` receipt with an attempted mutation and pending/unconfirmed
status, plus explicit `--confirm-receipt-upgrade`. A new or configured receipt,
an already-repaired receipt, or a legacy Toolbox is not eligible.

```powershell
$RepairedReceipt = Join-Path $Private 'toolserver.repaired.jsonl'
$RepairedToolVariables = Join-Path $Private 'tools.repaired.tfvars.json'

python -B $Runner repair-toolserver `
  --bootstrap $Bootstrap --subscription-id $Subscription --tenant-id $Tenant `
  --previous-receipt $ServerReceipt --confirm-receipt-upgrade `
  --credential-env SELECTED_GITHUB_MCP_TOKEN `
  --confirm-read-only-credential --confirm-exclusive-owner `
  --receipt $RepairedReceipt --tfvars $RepairedToolVariables
if ($LASTEXITCODE -ne 0) { throw 'Stop and inspect the retained repair receipt.' }
$ServerReceipt = $RepairedReceipt
$ToolVariables = $RepairedToolVariables
```

The fresh GET must differ from the version-2 contract only by the exact boolean
`required=false`. Identity, owner, policy scope, headers and returned URLs still
have to pass their checks. The runner sends one complete version-2 PUT with the
fresh ETag, retained endpoint ID and explicitly selected credential. It does not
assume omitted/null headers preserve secrets and does not retrieve stored ones.
The endpoint ID and invocation URL must remain unchanged in actual readback.

The new version-2 journal carries `upgraded_from_sha256`, calculated over the
exact legacy receipt bytes. Historical bytes/hashes are never rewritten, and
subsequent inspection/Toolbox receipts retain this provenance. A failed or
uncertain repair is not retried; keep its new receipt and inspect. A matching
management readback still does not prove runtime credential or policy behavior.

## 3. Let Terraform create its connection

Review a fresh plan using **all original inputs** plus the new explicit
`$ToolVariables` file (`tools.ready.tfvars.json` after creation, or
`tools.repaired.tfvars.json` after confirmed repair). Retain any existing native-telemetry handoff and other
overrides. Do not let an omitted input undo earlier integration or monitoring.
The planned change should be the existing root-owned RemoteTool connection and
any other deliberately reviewed changes, not a second ToolServer owner.

After separately authorizing and applying that current configuration, export
`gateway_toolchain_bootstrap` again to a new `tools.connected.json` file using
the same guarded export pattern. That new output must identify the applied
`aigw-github` connection and the verified tool endpoint.

## 4. Create the Toolbox and review its runtime values

```powershell
$ConnectedBootstrap = Join-Path $Private 'tools.connected.json'
$BoxReceipt = Join-Path $Private 'toolbox.created.jsonl'
$RuntimeValues = Join-Path $Private 'tools.runtime.review.json'

python -B $Runner create-toolbox `
  --bootstrap $ConnectedBootstrap --subscription-id $Subscription --tenant-id $Tenant `
  --previous-receipt $ServerReceipt --toolbox-name repo-digest `
  --confirm-exclusive-owner --receipt $BoxReceipt --environment-json $RuntimeValues
if ($LASTEXITCODE -ne 0) { throw 'Stop and inspect the retained receipt.' }
```

Before creating anything, the runner rechecks the ToolServer and the actual
Terraform-managed RemoteTool authentication, audience and target. It makes one
Foundry version POST, retains the returned version, and checks its default
version, ownership metadata and single MCP tool entry. It uses the same
connection reference and `require_approval: never` entry defined by
[`toolbox_body`](../scripts/configure_tools.py#L499-L506); that setting relies on your separately
reviewed read-only credential and tool restriction.

For this single-project managed-identity flow, `isSharedToAll` must be an
explicit boolean; both true and false are accepted without changing sharing.
Missing/nonboolean values or a reported connection error block the Toolbox
request. Record any discrepancy between requested and returned sharing rather
than treating false as true or claiming general service semantics.
For a verified project-local connection, select
[`share_foundry_remote_tool_connection = false`](architecture.md#project-local-remotetool-compatibility)
on the Terraform owner and retain it on later plans; the Toolbox runner does
not reconcile Terraform sharing on your behalf.
All project identity, authentication, audience, target and credential checks
remain in force; runtime authorization still requires a real invocation.

The Toolbox endpoint follows the canonical Foundry versioned route using the
validated project, name and service-returned version. This is different from the
ToolServer endpoint, which is taken directly from its GET response.
The review JSON contains only `TOOLBOX_NAME`, `TOOLBOX_ENDPOINT` and
`GITHUB_REPOSITORY`. It is not automatically imported into azd or the application.
No role is granted and no application key is retrieved. Continue with the
[guided application flow](application-flow.md), using this configured receipt
and a fresh applied deployment contract. Its offline preparation, explicit agent
deployment and separately enabled schedule never rerun the tool writer.
Hosted/runtime acceptance remains a separate gate.

## Rotation and uncertain outcomes

For rotation, explicitly select the replacement read-only credential and use
the **latest** receipt, preferably the Toolbox receipt so its version is retained:

```powershell
python -B $Runner rotate-credential `
  --bootstrap $ConnectedBootstrap --subscription-id $Subscription --tenant-id $Tenant `
  --previous-receipt $BoxReceipt `
  --credential-env SELECTED_REPLACEMENT_GITHUB_TOKEN `
  --confirm-read-only-credential --confirm-exclusive-owner `
  --receipt (Join-Path $Private 'toolchain.rotated.jsonl')
if ($LASTEXITCODE -ne 0) { throw 'Stop and inspect the retained receipt.' }
```

Rotation requires the current readback/ETag to match the receipt and resends the
whole owned configuration with the new credential. Changed policies, extra
sources, missing/conflicting ETags or a changed frontend endpoint cause a stop.
It never reads the old secret, retries a write or creates another Toolbox version.
After runtime verification, revoke the old GitHub credential through its issuer;
this helper does not revoke or roll back credentials.

If a request times out, is interrupted or cannot be verified, **do not rerun
create**. The server might already have applied it. Use `inspect-toolserver` or
`inspect-toolbox` with the failed receipt and a new receipt path. These operations
make only Azure GETs, plus normal Azure CLI authentication; they do not retrieve
GitHub credentials or perform automatic repair.

```powershell
python -B $Runner inspect-toolserver `
  --bootstrap $ConnectedBootstrap --subscription-id $Subscription --tenant-id $Tenant `
  --previous-receipt (Join-Path $Private 'toolchain.rotated.jsonl') `
  --receipt (Join-Path $Private 'toolchain.inspected.jsonl')
```

A partial last journal line is treated as unconfirmed; a complete earlier intent
must exist. Wrong owners/configuration, unknown resources, changed Toolbox
defaults or missing receipts require manual review, not implicit adoption.
Use `inspect-toolbox` with the latest retained Toolbox handle to verify it after
rotation. Optional `--tfvars` and `--environment-json` handoffs are exclusive
new files; no automatic Terraform variable file is accepted. A failed handoff
write is recoverable by inspection, not by repeating the cloud mutation.
The total deadline is 300 seconds by default, configurable up to 600 seconds.
ToolServer readiness is limited to 30 GETs. No deletion or teardown is automated.

See the [contract sources and remaining acceptance gates](tool-credential-boundary.md)
before any live qualification.
