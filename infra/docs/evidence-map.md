# Validation and acceptance

These are historical results inherited from the tested Terraform baseline.
The standalone repository preserves its resource contracts and runtime code;
its layout change is not a new cloud deployment or additional live acceptance.

**Historical runtime status: November 9, 2026. The model-only backend cutover, one attributed
cost-limit rejection and one creator-readable scheduled digest are now
demonstrated. Overall end-to-end acceptance remains incomplete:** native
model/MCP safety denial, the historical agent-owned stored-response 403 and
the recurring MCP 499/`AuthorizationServiceError` remain unresolved.

The shared/default registry, normal container source build and version 5
digest remain accepted. The Terraform path demonstrated
infrastructure, integrated ACR build, hosted deployment, gateway/model routing,
all three real GitHub tools and correlated native telemetry. The normal build
uses a tag independently bound to its digest, not a digest-pinned reference.
The earlier immutable-image version 3 and manual daily-routine dispatch remain
accepted separately. The original daily routine remains disabled; the temporary
creator-identity comparison routine was disabled and deleted after observation.

The goal is the same technical demonstration as Bicep, not identical deployment
commands or lifecycle ownership. Both paths use the shared application and
gateway contracts. The results below distinguish source support, configuration
readback and observed runtime behavior; successful inference alone does not
prove every policy's rejection threshold.

## Standalone repository status

**November 10, 2026: hosted build/offline CI passed; still not a release.**
Both workflows passed for the exact initial commit
`08ae50f7dda6ed2e8fac4cda6468a78ed1e2b948`:

| Workflow | Qualified scope |
|---|---|
| [Application CI, run 42878270290](https://github.com/annawiewer/simple-foundry-hosted-agent-python-aigateway-terraform/actions/runs/42878270290) | Frozen dependency restore, 21 application tests, fresh root and actual seven-file prepared-context Linux AMD64 builds, and both container smoke tests with the unchanged readiness timeout. |
| [Terraform offline contracts, run 42878270225](https://github.com/annawiewer/simple-foundry-hosted-agent-python-aigateway-terraform/actions/runs/42878270225) | Windows and Ubuntu jobs: 147 Python contracts per OS, locked Terraform validations, mocked plans/applies, formatting and PowerShell syntax through the canonical offline script. |

These are new standalone-repository results, distinct from inherited baseline
evidence. Local layout, documentation links and source provenance were also
checked. The earlier local package-download TLS failures and reused AMD64
image's 90-second readiness timeout remain failed local observations, not
reclassified passes. Hosted CI used fresh builds without relaxing TLS
verification or the smoke timeout.

Neither workflow deploys to Azure. These results do not close backend/native
safety, stored-response 403, MCP 499 or lifecycle acceptance gaps below, and
do not certify another commit without its own workflow result.

## Backend safety recovery

**November 10, 2026: P2 remains open.** The separate acceptance runner's
parser was corrected for the observed list-shaped `custom_blocklists`
response and qualified in an archived 203-test offline run. These are
session-scoped recovery tests, not additional tests shipped in this repository.
The failed live attempt was not reclassified as successful.

One temporary test blocklist still needs exact-generation cleanup. The new
cleanup-only integration is being qualified before a separately bounded live
attempt. P2 still requires the complete neutral/canary/neutral runtime sequence,
attributable telemetry, cleanup and preservation evidence. Even successful
backend filtering would not establish P3 native gateway safety.

## Native content-safety support boundary

**Source review: November 10, 2026; no new runtime acceptance.** The
[official native capability inventory](https://github.com/Azure/aigateway/blob/3a76a191804036c24add09db33d64d72060c9855/skills/manage-ai-gateway/references/activities-and-cli-coverage.md#resource-and-control-surface)
explicitly classifies content safety as unsupported on
`Microsoft.ApiManagement/aigateways`. Its stated baseline is CLI `1.0.0b22`
and the selected `2025-09-01-preview` API. Visible flags and retained Medium
values do not establish supported model or MCP protection.

The earlier mocked bodies and selected-API readbacks remain configuration
evidence only. This newer support classification conflicts with the older
lab's native-safety guidance; neither that lab nor a saved policy establishes
enforcement. Backend RAI filtering is a separate layer and cannot close the
native-safety evidence gap.

The [native policy reference](https://github.com/Azure/aigateway/blob/3a76a191804036c24add09db33d64d72060c9855/skills/manage-ai-gateway/references/policies.md#tool-threat-protection)
describes tool threat protection and agent hooks as different controls with
their own prerequisites. They are not substitutes for a `contentSafety`
denial test. Native safety acceptance remains blocked on a supported control
and applicable test contract. No policy, threshold or infrastructure default
was changed by this documentation review.

## Acceptance matrix

| Area | Established evidence | Boundary / not established by this check |
|---|---|---|
| Terraform offline suite | November 8 canonical run, including model-account naming: 92 native mocked plans with semantic checks, nine isolated mocked applies (four registry and five model-account readback cases), 147 Python contracts, five locked root validations, formatting and PowerShell syntax. Adapter handoff assertions are checks within plans, not additional runs. | Not Azure availability or runtime behavior. Default ownership remains 37 Azure resources, including 11 scoped role assignments, plus one non-owning registry PATCH action; opt-in runtime bindings do not change empty-map behavior. |
| Application/container CI | The [standalone initial commit's hosted CI](#standalone-repository-status) passed frozen restore, 21 unit tests, fresh root/prepared Linux AMD64 builds and both normal-timeout smokes. The [CI steps](../../.github/workflows/ci.yml) build the actual prepared Terraform context, not a second hand-written Dockerfile. | Exact-commit offline/mock evidence, not Azure deployment or runtime acceptance. Earlier baseline and local emulation observations remain separate; no smoke timeout was extended for the standalone hosted result. |
| Normal source-build deployment | With registry sharing/default true, integrated ACR run `dt4` built the seven shared files for Linux AMD64 and deployed version 5. The helper produced a genuine `cli-completed` receipt. Independent reads matched the configured tag to the run's digest before and after the successful digest. See the [normal route](application-flow.md#default-build-and-deploy-the-source). | Tagged reference, not image immutability. Existing-environment qualification with existing permissions; no fresh-from-empty certification or claim about other build/registry modes. |
| Digest-pinned existing-image route | Earlier ACR run `dt2` built the same seven shared application files for Linux AMD64. Unique run/tag readback and independent registry-manifest lookup agreed on the immutable digest deployed as version 3. See the [optional build recipe](application-flow.md#build-the-selected-source-in-the-existing-registry). | An independently built, source-bound image, not an unexplained prebuilt prerequisite. This earlier run used project-local registry sharing and does not replace the later shared-mode proof. |
| Integrated application infrastructure | The separately managed November 8 side-by-side cutover was accepted at 11:34 UTC: the serving account returned boolean `allowProjectManagement=false`, with three deployments and no projects. Version 5 runtime and a fresh ordinary no-change plan passed. The accepted migration state has 47 Azure resource owners, including 15 scoped roles, one non-owning registry PATCH action and two GET data entries. November 9 preflight again found no changes; post-run preservation passed. | Deployment-specific migration inventory, not the default-root count or automatic migration behavior. The retained old account was not silently replaced or forgotten. Selected `2025-09-01-preview` gateway only; other regions/modes and omitted catalog `apiFormat` remain unqualified. |
| Model-account fail-closed readback | Five isolated mocked applies accept only boolean false and reject true, missing, null and string responses. Rejected states contain the account but no dependent model deployments or developer grants. The native root graph orders all four outputs and downstream gateway grant/provider/catalog after the independent GET. At 01:17:44 UTC on November 8, a data-only plan using the source postcondition rejected the actual live true value. | Focused negative qualification, not a successful migration or full deployment. No Azure resource writes or inference were made by the probe; the account, authoritative state and accepted runtime receipt were unchanged. Known outputs can remain in failed partial state and are not an acceptance signal. |
| Shared/default registry repair | At 21:17:22 UTC on November 7, the sole owner followed by native non-owning PATCH and independent GET retained both flags true at project/account endpoints. An ordinary plan exited 0 with no pending resource/output changes. After the new source-build digest, both flags, the existing versions/principal, all 14 roles, tools, exact-agent tenant authorization and disabled routine were preserved. | Target-specific repair and runtime qualification, not proof of a universal service defect or fresh-from-empty lifecycle. The earlier version 3 digest used project-local sharing; its evidence was not relabeled. |
| Agent and gateway telemetry | The November 9 creator comparison correlated 28 agent and 147 gateway spans with the completed response, session and version 5. All three tools succeeded; two model and five GitHub backend calls returned HTTP 200. The November 7 source-build digest separately correlated 28 agent and 149 gateway spans. | Not a zero-error trace: the November 9 run again contains an MCP 499 and failed inbound `AuthorizationServiceError`, followed by successful MCP traffic. Missing parent spans prevent establishing retry or root cause. Policy execution is not rejection proof; Portal-dashboard behavior, all-signal completeness and exporter migration remain unqualified. |
| Native telemetry source | Two-stage managed ingestion, OTLP endpoints, gateway-identity DCR publishing, a bounded GET-only helper and native/legacy/pending mock plans. See the [usage and migration boundary](native-telemetry.md). | Configuration alone remains insufficient; the preceding row provides separate delivery evidence for this deployment. Exporter migration and other target/endpoint combinations remain unqualified. |
| Model content-safety source | Same-run mock assertions cover the exact four-category body, omission and coexistence with other policies. The bundled root selects Medium; explicit profiles allow Low/Medium/High or null. Standalone defaults and backend Microsoft.DefaultV2 are unchanged. See [configuration and opt-outs](../README.md#model-content-safety). | Mocks do not prove service acceptance or enforcement; the selected-API readback below is narrower than complete policy/runtime qualification. |
| Selected-2025 model readback | A November 7 disposable-model check returned all four requested Medium safety severities. Model creation, removal and absence were verified. | Requested-body qualification remains incomplete, including omitted `apiFormat`. This was not a runtime safety-enforcement or MCP-safety test. |
| Selected-2025 ToolServer control plane | An isolated November 7 check created, updated, read and deleted a ToolServer using public Learn MCP and synthetic nonsecret headers. Nonsecret configuration, stable endpoint identity, known null header placeholders on ordinary GET and deletion were verified. | Not real credential rotation, secret-value storage/delivery, server-side atomic conditional semantics or runtime safety enforcement. This isolated check did not invoke substantive tools or certify the production runner's full lifecycle. |
| GitHub toolchain source | Explicit-credential runner, Terraform-owned RemoteTool handoff and direct Foundry Toolbox creation/inspection. Forty-six mocked tests cover lifecycle guards, uncertain writes, redaction and Windows/POSIX selected-credential exclusion. See [ownership limits](toolchain.md). | Hosted execution separately proves real tool consumption, not live rotation/revocation, diagnostics-wide secret handling or competing-writer semantics. Creation is not atomic. |
| Application-flow source | The [app-only path](application-flow.md) binds applied handoffs, copies only shared runtime/build files, disables automatic role repair and gates agent/schedule operations independently. Fifty-seven focused tests passed after the process-local user-agent regression. Normal integrated remote build and the optional digest-pinned route both have separate live evidence on azd 1.37.2 / extensions 1.0.0. | No claim for every stable 1.37.x release. The helper's local deadline does not enforce an ACR cloud-build ceiling. Actual generic `azd show` returned mappings only; deployed endpoint evidence came from `azd ai agent show`. |
| Actual-agent runtime grants | Exact-principal live readback confirmed gateway Models User and agent-Insights Monitoring Metrics Publisher. Both are now Terraform-owned through [`hosted_agent_principals`](application-flow.md#3-bind-the-deployed-agent-identity), preserving the existing agent principal. | No direct agent Tools User or broad Contributor grant was added. Tenant authorization remains separate; the existing exact-agent exclusion was verified, not modified. |
| Current-source hosted digest | Version 5 completed all three read-only tools in a version-bound session. Scanned counts were 0 PRs, 0 issues and 20 workflow runs, with no failed workflows observed. The 100-word digest explicitly qualified bounded observations and truncation metadata. Version 3's earlier acceptance remains preserved. | Not an exhaustive repository census or populated-result live UX coverage. Truncation and unavailable-versus-empty behavior have focused regression coverage, not exhaustive service qualification. |
| Daily routine | Configured `0 9 * * *`, `America/Los_Angeles`; one explicit dispatch completed against the same version/image/principal. Exact dispatch, session and response IDs matched successful agent/model/tool telemetry. Independent readback confirmed the routine disabled afterward. | Manual dispatch is not an observed 09:00 wall-clock firing. The pinned CLI expects `value` while live history returned `data`; the [bounded GET fallback](application-flow.md#verify-the-routine-and-pause-a-demonstration) recovered the run without redispatch. |
| Scheduled creator comparison | A separately approved timer due November 9 at 08:06:49 UTC invoked version 5 at 08:06:51 UTC without manual dispatch. Creator-scoped response GET returned HTTP 200 with a completed 78-word digest, matching session and telemetry. Its bounded tool results were 0 PRs, 0 issues and 24 completed successful workflow runs. Exact owned cleanup and preservation passed. | A new creator-identity routine, not repair of the historical agent-owned response 403, a change to the application's scheduling default, or proof of repeated daily delivery. The original routine remained disabled. The correlated 499 remains unexplained. See [response and error qualification](#scheduled-response-and-error-qualification). |
| Routine authoring compatibility | The Terraform [manifest generator](../scripts/application_flow.py#L146-L193) uses `agentName`, `cronExpression` and `timeZone`. Existing application-flow tests check the generated agent binding, schedule keys and selected repository prompt. | The original Bicep manifest's spelling repair belongs to the source baseline, not this Terraform-only repository. Neither authoring test proves runtime scheduling or a fresh full deployment. |
| Model routing | The accepted on-demand and manual-routine digests resolved `gpt-latest` to `gpt-6.1-sol-2026-09-29`, including the new version 5 run; benign direct mini calls resolved to `gpt-5.4-mini-2026-03-17`. Both IaC choices retain the configured priority tiers. | Priority is preference, not guaranteed error-triggered failover. The [official routing lab](https://github.com/Azure/aigateway/blob/6204dd56a94d4b54bfb4493974d70b39de93c18f/labs/22-model-routing/README.md#how-it-works) documents preferred-backend errors returning without retrying lower tiers. |
| Earlier token-limit probe | With a temporary mini token limit of 1, one request succeeded and the next returned 429. Its trace identifies `policy tokenLimit` / `OpenAITokenLimitExceeded`, with no backend call. Exact original model properties and unchanged Terraform state were independently verified after restoration. | API-key caller only, not agent-MI rejection. Token throttling contaminated this earlier cost phase, so it did not establish cost rejection and rate testing stopped. The benign safety prompt passed, not blocked. |
| Isolated cost enforcement | A separate November 8 experiment used temporary catalog/alias controls and a scoped caller grant. After HTTP 200 spend, the next request returned HTTP 403 with the uniquely named failed `costLimit` policy and no backend activity in the complete correlated capture. Neutral controls succeeded before and after. All temporary children and the grant were removed; accepted state and resources were preserved. | One bounded direct-model cost rejection, not a billing ceiling, pricing/SKU equivalence, agent-MI or MCP enforcement claim. The harmless Medium-safety probe returned HTTP 200; model safety denial and MCP safety remain unproven. See [governance qualification](#isolated-governance-qualification). |
| Governance probe recovery | One request after Retry-After returned HTTP 200 at 16:34:53 UTC. Its 12 correlated gateway spans show the intended mini backend and all four original policy configurations. Independent checks confirmed restored properties, unchanged state, active current-source version 3, exact runtime grants and the paused routine. | Seven total probe/recovery requests; recovery made no policy changes, key rotation or counter reset. Successful recovery does not establish cost/rate rejection, safety blocking or the service's internal throttle-reset mechanism. |
| Application demonstration vs. lifecycle | Infrastructure, source-built hosted digest, routine configuration/dispatch, one creator-readable scheduled delivery and native observability are demonstrated with separate infrastructure, tool and application owners. | No unattended Terraform `azd up` wrapper, repeated-daily-delivery guarantee, full credential lifecycle, recovery/teardown certification or blanket enforcement claim is supplied. |

Storage public access `Disabled` does not provide private connectivity or
establish hosted-agent readiness.

The prepared Linux AMD64 context built locally with normal TLS verification
and a build-scoped CDN mapping; no shared-host DNS, trust or proxy change was
made. A separate native ARM64 attempt encountered TLS `HandshakeFailure` and
remains unqualified. The accepted hosted release used the independently
verified ACR-built Linux AMD64 image.

## Model-account alignment and readback

The initial November 8 in-place alignment was **partially applied, not
accepted**. The later side-by-side cutover below is separate evidence, not a
reinterpretation of that failure. At 00:44:44
UTC, Terraform exited successfully after four updates: the model-account
request and removal of the extra request-rate policy from three catalog
models. The planned provider-endpoint recomputation resolved unchanged.
Independent GET still returned `allowProjectManagement=true`, although state
recorded the requested false value. The account also returned a new
`armFeatures` entry, `Microsoft.CognitiveServices/CostControls`; its cause
was not established. The 00:49:14 ordinary plan reported account drift and
dependent provider recomputation, not convergence.

The 00:58:28 reconciliation preserved every resource ID, all 14 roles, the
accepted agent versions/builds, shared/default registry, tools, exact-agent
authorization and disabled routine. It separately recorded the three intended
policy removals and retained model-account mismatch. No successful alignment
receipt, state edit, repeated apply, replacement or account-kind conversion
was used to hide the failure.

The source now orders an independent
[`models_readback` GET](../modules/foundry-models/main.tf#L25-L39) after account
writes. Its exact-false postcondition gates model deployments,
[developer grants](../modules/foundry-models/access.tf#L20-L33) and
[output consumers](../modules/foundry-models/outputs.tf#L1-L21).
The [mocked apply cases](../tests/models.tftest.hcl#L48-L109) and
[native-state checker](../tests/check_contracts.py#L529-L545) exercise that
boundary without Azure credentials. At 01:17:44 UTC, a separate data-only
ordinary plan bound the same source condition to the real account and failed
specifically because the returned flag was true. Before/after account reads
and authoritative state hashes were unchanged. This check had no managed
resources, provider registration, apply or inference.

Postcondition failure stops dependent work; it does not undo prior writes
or erase already-known outputs from partial state. Require a successful apply
and independent readback before publishing a deployment handoff.
HashiCorp's pinned
[account documentation](https://github.com/hashicorp/terraform-provider-azurerm/blob/59eca87035cef81d9c75070b024f2e29e6de2b6d/website/docs/r/cognitive_account.html.markdown)
and [transition implementation](https://github.com/hashicorp/terraform-provider-azurerm/blob/59eca87035cef81d9c75070b024f2e29e6de2b6d/internal/services/cognitive/resources/cognitive_account/resource.go)
require replacement when disabling project management while retaining
AIServices. That guidance supports an explicit migration review, not another
blind update or a universal claim about every Azure API transition.

### Accepted side-by-side cutover

At 11:34 UTC on November 8, a separately authorized, operator-managed cutover
was accepted. A new model-only account returned boolean
`allowProjectManagement=false`, contained the three intended deployments and
no projects, and retained the expected backend default policies. Gateway
provider/catalog bindings targeted that account; version 5 completed its
runtime qualification and a fresh ordinary plan reported no changes.
The old account remained explicitly owned rather than being deleted or
removed from state to hide drift.

This closes strict alignment for the serving backend in that existing
environment. It is not a fresh-from-empty certification, an in-place conversion,
or migration automation supplied by
[`model_account_name`](../README.md#model-account-naming).
Changing that input alone does not retain an old account or perform a cutover.
Protected captures and separate hash-bound failed/accepted receipts remain
private; the negative guard proof and earlier runtime acceptance were not
rewritten.

## Shared-registry source-build qualification

This closes the earlier registry/source-build evidence gap for the existing
deployment. The implementation retains the sole
[`registry_connection` owner](../modules/foundry-agents/main.tf#L111-L137),
orders a non-owning PATCH with both flags true, then requires an
[independent GET postcondition](../modules/foundry-agents/main.tf#L139-L172).
The [sharing output](../modules/foundry-agents/outputs.tf#L10-L14) waits for that
readback but remains a configured value, not image-pull proof. The separate
[`manifest`](../scripts/application_flow.py#L146-L193) and
[`deploy`](../scripts/application_flow.py#L539-L615) path
supplied the runtime evidence below without provisioning again.

| Time on November 7, 2026 (UTC) | Observation |
|---|---|
| 21:17:22 | Shared/default connection readback and ordinary no-change plan accepted. |
| 22:56:56-22:58:45 | Approved integrated source deployment completed; exact run `dt4` succeeded and version 5 was independently identified. |
| 23:06:34-23:07:15 | Version-bound digest completed all three tools; console, agent and gateway evidence correlated. |
| 23:19:41 | Independent post-inference readback preserved versions 3/4/5, principal, scoped roles, tenant authorization, tools, disabled routine, shared/default registry and exact Terraform state bytes. The tag still matched the build digest. |

This was not a fresh environment: existing deployment/build permissions,
project registry access, the two adopted runtime grants and exact-agent tenant
authorization were prerequisites. No permission, capacity or schedule change
was made for the source qualification.

The first instrumented launch built successfully but remained **unconfirmed**
locally because added `--debug` logging created an unexpected extension file.
Its receipt was preserved. A separately approved corrective launch archived and
byte-verified only its own generated diagnostic before retiring it; workspace
and receipt guards stayed unchanged. The ordinary
[`deploy` helper](../scripts/application_flow.py#L539-L615) does not add `--debug`;
this diagnostic handling is not an extra product deployment step.

The accepted trace retains the early MCP 499/`AuthorizationServiceError`.
Completed SSE call items also repeated argument JSON; actual execution was
verified independently from protected tool telemetry with matching call IDs,
session, version and bounded repository arguments. Neither observation was
silently normalized into an error-free claim. All four policy types executed,
but this successful digest proves no new rejection threshold.

Raw captures, prior stopped outcomes and the hash-bound
`final-acceptance.safe.json` receipt remain private. Final acceptance is a new
record; it does not rewrite the original response receipt or earlier failures.
Later timer and cost-limit results are separate qualifications below; they do
not rewrite this source-build acceptance. Medium safety denial remains unproven.

## Isolated governance qualification

On November 8, 21:00-21:04 UTC, a separately authorized attempt made five direct
model requests using two temporary catalog entries, two aliases and one
gateway-scoped caller grant. It added no backend model capacity and made no
application, SKU or MCP change.

The cost sequence returned HTTP 200, then HTTP 403. Correlated telemetry
attributed the denial to the uniquely named failed `costLimit` policy after
the successful isolated spend. No backend activity appeared in that denied
request's complete correlated capture; this is not proof about invisible
attempts or Azure billing. Neutral safety controls before and after succeeded.
The harmless safety prompt also returned HTTP 200: native safety denial was
not demonstrated, which does not by itself establish that safety is broken.
No MCP safety test was performed.

Exact ownership checks, removal of the four temporary children and grant,
five independent absence readbacks and accepted-deployment preservation
completed at 21:10 UTC. Cost rejection is accepted; combined cost-and-safety
acceptance remains false. The earlier token-throttled experiment retains its
original, narrower result.

## Scheduled-response and error qualification

The original November 8 scheduled invocation completed its computation:
three real tools, a complete 81-word digest and successful model/GitHub backend
calls are bound to its run, session and version 5. The operator's stored-response
GET nevertheless returned `403 session_not_accessible`. Successful computation
does not repair that access failure.

The separately authorized November 9 comparison used a new creator-identity
routine and no new permissions, capacity, policy changes or application release.
Its timer was due at 08:06:49 UTC; the agent invocation began at 08:06:51 UTC.
Response GET first returned in-progress, then completed output with HTTP 200.
The 78-word digest matched the final model output and all three tool payloads,
including the explicit bounded-scan qualification.

The comparison nevertheless repeated the MCP 499/`AuthorizationServiceError`.
Subsequent successful calls do not establish a retry mechanism, a harmless
handshake or a repaired authorization defect. The failed request's upstream
parent was absent from the capture; root cause remains unresolved.

The sole temporary routine was disabled and deleted, with absence verified at
08:08 UTC. Original resources, policies, runtime grants, the disabled original
routine and accepted migration state were preserved. Independent offline
verification checked all 59 protected request envelopes and their hash-linked
intents, recomputed response/telemetry correspondence and reviewed the actual
tool results. These private captures are not committed.

This proves creator-scoped access to one new scheduled response, not access to
the old agent-owned response. It changes neither the public helper's schedule
identity behavior nor the original routine. Full end-to-end acceptance and
error-free execution are not claimed.

## Run the checks

Use the [canonical offline/preparation route](architecture.md#offline-and-deployment-preparation).
[`Test-Offline.ps1`](../scripts/Test-Offline.ps1) initializes with backend disabled
and read-only locks, then checks formatting, validation, structure, native plans,
semantic resource relationships, Python contracts and PowerShell syntax.
It does not deploy or require Azure credentials; uncached providers need network
access. Passing tests describe their assertions, not missing parity features.

| Test owner | Responsibility |
|---|---|
| [`root.tftest.hcl`](../tests/root.tftest.hcl) | Composition, aliases, input guards, full-root defaults, safety settings and opt-in hosted-identity roles with independent switches and exclusive ownership |
| [`gateway.tftest.hcl`](../tests/gateway.tftest.hcl) | Standalone gateway, frontend, exporter destination, callers and safety enum rejection |
| [`telemetry.tftest.hcl`](../tests/telemetry.tftest.hcl) | Native readiness, scoped publisher/exporter and rejection of stale or mismatched handoffs |
| [`models.tftest.hcl`](../tests/models.tftest.hcl) | Model profile, exact-false independent account readback, rejected-response downstream blocking and gateway-only safety metadata without changing the backend filter |
| [`agents.tftest.hcl`](../tests/agents.tftest.hcl) | Independent support resources, network inputs and monitoring connection |
| [`examples.tftest.hcl`](../tests/examples.tftest.hcl) | Four standalone roots, external-pregrant configuration and existing-model safety opt-in |
| [`examples-telemetry.tftest.hcl`](../tests/examples-telemetry.tftest.hcl) | Native handoff forwarding through both gateway-bearing examples |
| [`check_contracts.py`](../tests/check_contracts.py) | API bodies, exact grants, routes, sole ownership and dependency edges |
| [`test_environment_adapter.py`](../tests/test_environment_adapter.py) | Nonsecret allow-list, Responses compatibility and resource/endpoint relationships |
| [`test_live_readback.py`](../tests/test_live_readback.py) | GET-only scope, omissions, safe receipts and no overwrite |
| [`test_telemetry_readiness.py`](../tests/test_telemetry_readiness.py) | Readiness polling, CLI/ARM context, endpoint validation, bounds, redaction and explicit no-overwrite handoffs |
| [`test_toolchain.py`](../tests/test_toolchain.py) | Explicit ownership/credentials, complete request bodies, conditional rotation, uncertain outcomes, Toolbox versions, redaction and isolated handoffs |
| [`test_application_flow.py`](../tests/test_application_flow.py) | Offline snapshot generation, context-bound handoffs, app-only manifests, independent deployment gates, installed versions, isolated credentials, drift detection and single-attempt receipts |
| [`prepare_application_ci.py`](../tests/prepare_application_ci.py) | Synthetic offline handoffs through the real application `prepare` entry point; CI builds and smokes the resulting isolated context |
| [`test_github_mcp_middleware.py`](../../tests/test_github_mcp_middleware.py) | Bounded scan metadata, saturation/continuation handling and coverage captured before filtering |
| [`test_agent_runtime.py`](../../tests/test_agent_runtime.py) | Shared runtime/client behavior; generated routine authoring is covered by the application-flow tests above |

## Remaining qualification boundaries

The accepted demonstrations close the selected backend-alignment, bounded cost
rejection and creator-readable scheduled-delivery gaps, not the broader
guarantees below.
Each requires separate, explicitly scoped authorization and validation:

- Native model and MCP safety denial, access to the historical agent-owned
  response, and the cause of the recurring MCP 499/authorization error.
- Fresh-from-empty reproduction, repeated daily delivery, subsequent releases,
  recovery and teardown.
- Real credential rotation/revocation, diagnostics-wide secret handling,
  negative authorization and policy rejection scenarios not established above.
- Other regions, build/registry modes and exporter migration.

Use [read-only field qualification](live-readback.md) alongside a current
ordinary plan, not as a substitute for runtime tests. Omitted properties remain
unknown; successful inference does not make them independently verified.
See [ownership and differences](architecture.md#preserved-contracts-and-deliberate-differences)
and the [tool/credential boundary](tool-credential-boundary.md) before deployment.
