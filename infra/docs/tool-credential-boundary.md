# ToolServer and credential boundary

An explicit-credential [tool lifecycle runner](toolchain.md) now implements
ToolServer creation/rotation, GET-only inspection and Foundry Toolbox creation.
**Real GitHub-tool execution is accepted for the on-demand digest and one
routine dispatch; broader credential lifecycle guarantees are not.** See the
dated [acceptance matrix](evidence-map.md).
Terraform itself still
owns only the RemoteTool connection and selected grants; an explicitly
configured connection does not create its remote server or prove invocation.
The separate project Tools User grant, enabled by default in the application
root, is authorization
configuration only, not an exception to this boundary.

## Selected 2025 contract

The [official CLI installer pinned at b2204cf4](https://github.com/Azure/aigateway/blob/b2204cf4a32f2d69e07fc475cee7c6056a28e711/cli/install.ps1#L32-L35)
pins release `1.0.0b22` and its wheel SHA-256. Implementation references below
are members of that checksum-verified wheel, not code in the installer:

| Wheel member under `azext_aigateway/` | Inspected locator and evidence |
|---|---|
| `aaz/latest/aigateway/mcp/_create.py` | `Create.AIGatewayToolServerCreateOrUpdate.content`, lines 366-409: `displayName` and dictionary-of-list credential headers, matching the [upstream Bicep request](https://github.com/Azure-Samples/simple-foundry-hosted-agent-python-aigateway/blob/4ac828155315607141ed4e1ea692c766fff4c123/infra/main.bicep). |
| `aaz/latest/aigateway/mcp/_show.py` | `Show.AIGatewayToolServerGet._build_schema_on_200`, lines 184-223: **`properties.mcpEndpointUrl`**. |
| `custom.py` | `_execute_operations`, lines 3140-3148: best-effort existence check and the `If-None-Match` warning discussed below. |

These generated serializers describe the older `service/.../workspaces` route,
not authoritative wire-response evidence for standalone `aigateways`. The
runner also supports the service-returned `gatewayEndpoints[]` collection
observed on `2025-09-01-preview`.

The runner's version-2 request keeps `2025-09-01-preview`, `displayName` and the
dictionary-of-list request headers. It requests endpoint `required=true` and
explicit policy `scope=resource`. The pinned
[ToolServer definition](https://github.com/Azure/azure-rest-api-specs/blob/54b97a29d524bae3b69778303813f90a27c7edd5/specification/apimanagement/resource-manager/Microsoft.ApiManagement/AIGateway/AIGatewayToolServer.tsp)
documents `required` as making an endpoint failure fail the federation;
the [policy definition](https://github.com/Azure/azure-rest-api-specs/blob/54b97a29d524bae3b69778303813f90a27c7edd5/specification/apimanagement/resource-manager/Microsoft.ApiManagement/AIGateway/AIGatewayModel.tsp)
defines resource scope for non-counter policies. These definitions are
published for `2026-11-01`. Their correlation with observed 2025 fields
supports this compatibility choice, **not by itself proof of service
acceptance or enforcement**. No newer API or header
array format is substituted; both IaC choices retain the shared tool path.

An isolated November 7 selected-2025-API check created, updated, read and
deleted a ToolServer using public Learn MCP and synthetic nonsecret headers.
It returned `required=true`, all four Medium resource-scoped safety fields, stable endpoint
identity and known null header placeholders, then confirmed owned deletion and
absence. This establishes bounded control-plane acceptance, not real credential
storage/delivery, substantive tool execution or enforcement.
The successful hosted GitHub digest is separate runtime evidence, not a
credential-rotation test.

The runner accepts only known null header placeholders, still rejecting
non-null/masked values and unknown names. It selects one qualified MCP entry
from the service-returned collection or the legacy URL, rejecting conflicting
URLs and invalid origin/base-path metadata. The
[endpoint definition](https://github.com/Azure/azure-rest-api-specs/blob/54b97a29d524bae3b69778303813f90a27c7edd5/specification/apimanagement/resource-manager/Microsoft.ApiManagement/AIGateway/AIGatewayResponses.tsp)
describes the invocation URL and optional SDK base URL/API metadata. Neither
route construction nor arbitrary metadata stripping is used.

Version-1 request hashes remain verifiable without rewriting their receipts
or Toolbox metadata. Such receipts are inspection-only; no rotation, new
Toolbox or automatic version migration is authorized from them. A live
`required=false` or missing safety evidence remains a blocker for that specific
readback. Implementing the local compatibility change was not itself a live
write or credential qualification.

The explicit `repair-toolserver` path is a separately approved transition
for an original unconfirmed v1 creation only. It changes the exact known
`required=false` defect, preserves the endpoint ID, and submits the complete
configuration with a specifically selected credential and fresh ETag. It never
assumes missing/null headers retain secrets. A new v2 receipt binds the original
receipt's SHA-256; the legacy file remains unchanged. Ordinary v1 inspection,
rotation rejection and Toolbox-write rejection are not relaxed.

The wheel's `custom.py` warning says ToolServer PUT does not enforce
`If-None-Match`; this is CLI implementation commentary, not independent
qualification of the standalone service. This runner therefore requires
explicit exclusive ownership, checks the exact missing-resource response and
refuses existing names. This is not atomic creation. Rotation sends a fresh
specific ETag only after matching the receipt and complete nonsecret
configuration. Neither source inspection nor mocks prove service-side
conditional enforcement.

The Foundry path follows the pinned
[Toolbox v1 client](https://github.com/Azure/azure-dev/blob/1273b0ddd9a04b09352f67632a6f1e3952fc5df0/cli/azd/extensions/azure.ai.toolboxes/internal/pkg/azure/foundry_toolsets_client.go)
and [versioned endpoint construction](https://github.com/Azure/azure-dev/blob/1273b0ddd9a04b09352f67632a6f1e3952fc5df0/cli/azd/extensions/azure.ai.toolboxes/internal/cmd/toolbox_show.go).
It uses direct requests rather than `azd ai toolbox create`, avoiding the latter's
automatic role-assignment and environment-write behavior. It never writes the
Terraform-owned RemoteTool connection.

## Earlier contract findings and limits

Published standalone gateway contracts differ from the selected preview body.
Check the API and wire format before porting a resource body or reusing a hook:

| Source or check | Finding and limit |
|---|---|
| [Pinned September OpenAPI](https://github.com/Azure/azure-rest-api-specs/blob/28237674e0ed814213f8e2b85ebcb4cc46d3e0fb/specification/apimanagement/resource-manager/Microsoft.ApiManagement/AIGateway/preview/2026-09-01-preview/openapi.json) | The `2026-09-01-preview` document does not define a ToolServer schema. Its omission is not proof that the service lacks child routes. |
| [Pinned ToolServer TypeSpec](https://github.com/Azure/azure-rest-api-specs/blob/28237674e0ed814213f8e2b85ebcb4cc46d3e0fb/specification/apimanagement/resource-manager/Microsoft.ApiManagement/AIGateway/AIGatewayToolServer.tsp) and [November OpenAPI](https://github.com/Azure/azure-rest-api-specs/blob/28237674e0ed814213f8e2b85ebcb4cc46d3e0fb/specification/apimanagement/resource-manager/Microsoft.ApiManagement/AIGateway/stable/2026-11-01/openapi.json) | The published ToolServer resource is introduced at `2026-11-01`. It uses a `name` wire property and header objects with `name`/`values`; secret values are create/update-only. This is not the same body contract as the older hook. |
| [Upstream PowerShell hook](https://github.com/Azure-Samples/simple-foundry-hosted-agent-python-aigateway/blob/4ac828155315607141ed4e1ea692c766fff4c123/infra/scripts/configure-ai-gateway.ps1) | It obtains the active local GitHub CLI credential and writes a complete older-format ToolServer body, then configures azd/Toolbox and saves a runtime key. It is not a Terraform adapter and is not included or run here. |

The published November contract also exposes a read-only
`gatewayEndpoints[]` collection with the invocation `url` and API kind. Select
the qualified MCP endpoint from the service response; do not copy a sample path
or assume its case. Header values are create/update-only in that schema and
are retrieved separately with `listSecrets`; ordinary GET is not sufficient
to establish header drift or credential preservation. Whether a write omitting
values preserves them remains unaccepted. A schema alone is not approval to
retrieve or upload any real credential.

Do not silently substitute the newer published schema into the tested preview
deployment, or infer a usable MCP URL from an empty collection response.

## Tool role qualification

In the qualified target, a subscription-scoped, read-only role-definition GET
confirmed **AI Gateway Tools User**
`dce03f8d-857f-4e40-a90d-67770fa6ecd2` as a built-in role. It returned no management
actions and these data actions:

- `Microsoft.ApiManagement/service/workspaces/toolServers/*`
- `Microsoft.ApiManagement/aigateways/tools/*`

This confirms definition availability in that qualified target, not all
subscriptions, a role assignment, propagation or an intended-identity tool call.

`enable_foundry_gateway_tool_access` grants this role only to the existing
Foundry project identity, at this gateway's exact scope. It defaults to true in
the application root and can be disabled independently. The root owns it;
standalone modules/examples do not add it. The gateway module's caller map still
grants Models User only. The broader AI Gateway User role is not substituted.
Narrower ToolServer-level scope requires a separately established resource
identity; a runtime URL alone is not that identity.

## Implemented ownership and remaining acceptance

The whole-resource runner is the ownership boundary. Terraform must not create
a ToolServer stub that a hook subsequently overwrites. Owner markers, durable
nonsecret receipts and strict readback prevent implicit adoption; they do not
replace Azure authorization or guarantee protection against a competing writer.

The runner must receive an explicitly selected credential; deployment approval
does not select a personal GitHub login for cloud storage. Never infer consent
from an existing `gh` login, read its token automatically, put a token in tfvars,
or save a secret-bearing request in logs, output artifacts, state or plans.
Use repository-restricted, read-only permissions; an `X-MCP-Readonly` header is
not a substitute for credential least privilege.

For broader lifecycle or credential guarantees, retain separate evidence:

- Establish the exact API, whole request body and service-returned runtime URL.
- Preserve the entire intended ToolServer policy and endpoint configuration
  during creation and credential rotation, with conditional concurrency checks.
- Verify that ordinary reads and all persisted local/cloud diagnostics omit
  credentials; an offline redaction test alone is insufficient.
- Prove intended-identity allow/deny separately from role/connection creation.
  The accepted on-demand run establishes actual Toolbox/read-only tool use,
  not negative authorization or every later credential/version state.

Offline tests cover request bodies, failure/rotation/inspection behavior,
redaction and handoffs, not those broader guarantees. Ordinary-GET omission and
one working digest do not certify every local/cloud diagnostic or future
rotation. See the [evidence map](evidence-map.md).
