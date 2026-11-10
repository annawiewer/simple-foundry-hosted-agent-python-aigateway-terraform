# Native gateway telemetry

The root, `gateway-only` and `existing-models` default to native OpenTelemetry.
Use **two explicit stages in the same Terraform root and workspace**, retaining
the original inputs. Terraform remains the only infrastructure writer; the
separate readiness helper performs GETs, not resource or role changes.

| Stage | Configuration | Terraform ownership |
|---|---|---|
| Initial | `gateway_telemetry_mode = "OpenTelemetry"`, `gateway_native_telemetry = null` | Gateway, Log Analytics and Insights with managed ingestion enabled; no exporter or DCR publisher yet |
| Ready | Same inputs plus the helper's explicit handoff | One gateway-identity Monitoring Metrics Publisher grant on the returned DCR, then the `appinsights` OpenTelemetry exporter |

`gateway_monitoring.configuration_status` is `pending`, `configured`, or
`legacy`. **Configured is not delivery proof.** Native export uses returned
metrics/logs/traces endpoints, managed identity with the Monitor audience,
and `payloadCapture = false`; it does not use a connection string.
The [acceptance matrix](evidence-map.md#acceptance-matrix) records separate
delivery evidence: the November 7, 2026 current-source hosted digest and routine
dispatch correlated native gateway, agent, model and GitHub backend spans.
That does not qualify every
signal, target, Portal dashboard or exporter migration.

## Prerequisites

Complete the [preparation route](architecture.md#offline-and-deployment-preparation)
and qualify the target before any apply. These commands create billable
resources; inspect each interactive apply plan before confirming.
Existing deployments must first read [legacy compatibility](#legacy-compatibility).

Use Python 3 and an existing Azure CLI login in **public Azure** with the same
subscription and tenant as Terraform. The CLI principal needs to read the
owned Insights component. The Terraform principal also needs permission to
assign the publisher role at the generated DCR, which can be in a different
managed resource group. Required providers/service enablement must already be
available. The helper does not install tools, log in, select accounts, register
providers or grant permissions.

## Stage one: provision managed ingestion

From the repository root in PowerShell 7, select the prepared root and its
original variable file. Create a private directory outside the checkout first;
replace the paths below with your own. Keep state, plans and inputs private.

```powershell
$ErrorActionPreference = 'Stop'
$TerraformRoot = (Resolve-Path 'infra').Path
# Alternatively: infra\examples\gateway-only or existing-models.
$Inputs = (Resolve-Path "$TerraformRoot\terraform.tfvars").Path
$PrivateDirectory = (Resolve-Path 'C:\private\my-environment').Path

terraform "-chdir=$TerraformRoot" init -input=false -lockfile=readonly
if ($LASTEXITCODE -ne 0) { throw 'Initialization failed.' }
terraform "-chdir=$TerraformRoot" plan -input=false "-var-file=$Inputs"
if ($LASTEXITCODE -ne 0) { throw 'Stage-one plan failed.' }
terraform "-chdir=$TerraformRoot" apply "-var-file=$Inputs"
if ($LASTEXITCODE -ne 0) { throw 'Stage-one apply failed; do not continue.' }
```

Leave `gateway_native_telemetry` unset/null for this initial stage. A successful
apply can report `pending`: the service generates the DCR and OTLP endpoints
asynchronously. That status must not be interpreted as a working exporter.

## Readiness: produce a nonsecret handoff

Export **only the named bootstrap output**, not state or the full output
envelope. Use new filenames; the helper refuses to overwrite a handoff.

```powershell
$BootstrapPath = Join-Path $PrivateDirectory 'gateway-bootstrap.json'
$Handoff = Join-Path $PrivateDirectory 'gateway-native.ready.tfvars.json'
$Bootstrap = terraform "-chdir=$TerraformRoot" output -json gateway_telemetry_bootstrap
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap output failed.' }
$Bootstrap | Out-File -LiteralPath $BootstrapPath -Encoding utf8 -NoClobber

python -B infra\scripts\wait_for_telemetry.py `
  --bootstrap $BootstrapPath `
  --subscription-id '<subscription UUID>' `
  --tenant-id '<tenant UUID>' `
  --tfvars $Handoff
if ($LASTEXITCODE -ne 0) { throw 'Readiness failed; do not proceed to stage two.' }
```

The [helper](../scripts/wait_for_telemetry.py) checks CLI/token context, exact
Insights and Log Analytics IDs, same-subscription DCR scope and credential-free
HTTPS endpoints. It supports the service's canonical and fallback property
names, rejects conflicting values, and never contacts the OTLP endpoints.
Only an optional `api-version` query is accepted in those endpoints.

Defaults are at most 60 Insights GET attempts, a 10-second polling interval
and a 600-second budget; `--max-attempts` and `--timeout-seconds` can only lower
those limits. HTTP socket timeouts are capped at 30 seconds. Authorization,
redirects, mismatched resources and malformed values fail closed. Timeout or
incomplete readiness is not permission to guess values or widen a grant.
The file contains only `gateway_native_telemetry`; no access token, connection
string or tool credential is saved. Automatic Terraform variable filenames
are rejected so a handoff cannot be loaded accidentally.

## Stage two: review and configure native export

Use a **fresh, normal refresh-enabled plan**, the same workspace and **all
original inputs**, plus the handoff. Do not mix unrelated infrastructure
changes into this step or use `-refresh=false`, `-refresh-only` or `-target`.

```powershell
terraform "-chdir=$TerraformRoot" plan -input=false "-var-file=$Inputs" "-var-file=$Handoff"
if ($LASTEXITCODE -ne 0) { throw 'Stage-two plan failed.' }
terraform "-chdir=$TerraformRoot" apply "-var-file=$Inputs" "-var-file=$Handoff"
if ($LASTEXITCODE -ne 0) { throw 'Stage-two apply failed; configuration is incomplete.' }
terraform "-chdir=$TerraformRoot" output -json gateway_monitoring
```

The managed Insights resource's normal refresh supplies the observed values.
Preconditions bind them and the handoff to the actual gateway identity,
Insights component and Log Analytics workspace before the DCR grant/exporter.
The generated DCR remains service-owned; Terraform owns only its scoped grant.
The second stage should add just that grant and the exporter. Stop on unrelated
changes, replacement, incomplete values or changed endpoints.

Keep loading the handoff for **every subsequent plan/apply**. Removing it
would select the pending configuration and plan exporter removal, blocked by
`prevent_destroy`. If readiness changes, rerun the helper into a new file and
review another fresh plan; do not edit or fabricate service-generated values.
Each deployment still needs separate runtime checks for role propagation and
delivery; a configured output is insufficient. The actual hosted agent may also
need its own publisher grant at agent Insights scope, distinct from this
gateway-to-DCR grant. Follow the
[postdeployment identity handoff](application-flow.md#3-bind-the-deployed-agent-identity).

## Legacy compatibility

An existing connection-string exporter can explicitly retain its old body:

```hcl
gateway_telemetry_mode   = "ApplicationInsights"
gateway_native_telemetry = null
```

For direct module callers, the input names are `telemetry_mode` and
`native_telemetry`. The root/examples forward those inputs. The helper's file
uses the root/example name; custom wrappers must forward it explicitly.

The exporter retains its `appinsights` name; a `moved` block preserves its old
uncounted Terraform address. Kind changes request replacement, and
`prevent_destroy` blocks it. These are configuration guards, **not an exercised
migration or an Azure deletion lock**. Compatibility mode alone does not make
the earlier API/default changes a safe upgrade; review the original inputs and
[root opt-outs](architecture.md#optional-application-integration) too.

Do not delete/recreate an exporter, bypass the guard, manipulate state or run
Bicep mutation/recovery hooks to complete these steps. Legacy-to-native migration
and teardown require their own ownership-aware plan and explicit approval.
