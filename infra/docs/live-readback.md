# Read-only live qualification

[`verify_live_readback.py`](../scripts/verify_live_readback.py) compares the
managed AzAPI resources in an explicitly supplied Terraform state export with
fresh ARM GETs. It checks resource identity, requested body subsets, placement,
tags and available identity metadata, including role-assignment properties.
It is **not** an apply, drift plan, policy/runtime test or acceptance of omitted
properties.

## Protected inputs and explicit context

State exports can contain connection strings even though deployment outputs are
nonsecret. Keep both input and receipt in an existing access-controlled directory
outside the repository; never upload or commit them. The runner does not print
state values, response bodies, credentials or Azure CLI failure payloads.

Use Python 3 and an already authenticated Azure CLI for Azure public cloud.
The current CLI subscription **and tenant** must match the explicitly supplied
UUIDs; the runner never changes CLI context or installs a dependency. An
already selected process-local `AZURE_CONFIG_DIR` is inherited unchanged.

Example in PowerShell 7, after selecting the authorized target and the correct
environment's Terraform state:

```powershell
$TerraformRoot = 'infra'
$ProtectedDirectory = '<existing-protected-directory>'
$SubscriptionId = '<authorized-subscription-id>'
$TenantId = '<authorized-tenant-id>'
$StatePath = Join-Path $ProtectedDirectory 'state-readback.json'
$ReportPath = Join-Path $ProtectedDirectory 'field-qualification.json'
if (Test-Path $StatePath) { throw 'Choose a new protected state-export filename.' }

$StateJson = & terraform "-chdir=$TerraformRoot" show -json
if ($LASTEXITCODE -ne 0) { throw 'State export failed.' }
$StateJson | Set-Content -LiteralPath $StatePath -Encoding utf8
$StateJson = $null

python -B infra\scripts\verify_live_readback.py `
  --state-json $StatePath --subscription-id $SubscriptionId `
  --tenant-id $TenantId --report $ReportPath
```

The runner accepts state with this contribution's version-1
`deployment_contract`. Unsupported managed resource kinds, cross-subscription
resources, invalid API versions and empty managed state fail closed. Data-source
entries are not managed-resource acceptance. A receipt must be a **new file**;
existing receipts and input state are never overwritten.

No inferred permission propagation, secret action, model request, GitHub
credential access, Toolbox operation or Azure write is performed. ARM requests
use only `GET`, reject redirects and target the public ARM origin.

## Results

| Exit | Result | Meaning |
|---|---|---|
| 0 | `PASS` | All selected resources were read and their compared requested fields/metadata agreed. This remains a requested-subset check, not full service/runtime acceptance. |
| 1 | `FAIL` | A GET/envelope failed, resource identity differed, or a returned value disagreed. Inspect only the safe field paths/statuses in the receipt. |
| 2 | Input/context error | Input, target, tool/authentication or output-path requirements failed. No acceptance is claimed. |
| 3 | `INCOMPLETE` | Observable values agree, but GET omitted requested fields. Do not relabel this a full configuration pass. |

ARM resource IDs, location formatting and identity-type case are normalized.
Equivalent JSON integer/fractional number representations compare equally;
booleans are not numbers. Array ordering and substantive field changes are
not ignored. Expected null fields add no proof of a configured nonnull value.

Keep receipts alongside, not instead of, a separately reviewed ordinary plan.
Neither successful inference nor Terraform no-change planning establishes an
omitted field, credential erasure or permission propagation. The
[acceptance matrix](evidence-map.md#acceptance-matrix) records the evidence and
remaining gaps once, without duplicating historical execution journals here.
