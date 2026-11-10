# Offline checks

[`Test-Offline.ps1`](Test-Offline.ps1) is the single credential-free structural
verification entry. Use the
[canonical preparation route](../docs/architecture.md#offline-and-deployment-preparation)
for prerequisites, invocation and the separate Azure-enabled planning boundary.

The runner uses locked, backend-disabled initialization, formatting/validation,
provider-mocked tests and Python contract inspection. Provider downloads may
need registry access. It does not retrieve credentials, deploy resources,
invoke models, repair exporters, configure azd, deploy an agent or certify
runtime/telemetry/lifecycle acceptance. Existing Bicep mutation/recovery hooks
must not be reused against Terraform-owned resources.

[`wait_for_telemetry.py`](wait_for_telemetry.py) is **not an offline check**.
It is the separate, bounded Azure GET-only helper for the
[two-stage native telemetry path](../docs/native-telemetry.md). It requires an
existing matching public-cloud CLI login and writes a new explicit nonsecret
handoff, never a resource, grant, credential or automatic variable file.

[`configure_tools.py`](configure_tools.py) is also **not an offline check**.
Its explicit create/rotate commands write Azure resources and can upload the
selected GitHub credential; its inspect commands are GET-only. Read the
[tool lifecycle guide](../docs/toolchain.md) for authorization, exclusive-owner
limits, receipt recovery and staged Terraform/Foundry handoffs. It never runs
automatically, retrieves a GitHub login, grants roles, changes azd or deploys
the application. Tests use synthetic credentials and mocked transports only.

[`application_flow.py`](application_flow.py) provides the opt-in
[guided application path](../docs/application-flow.md). Its `prepare` operation
is offline and creates an isolated, nonsecret build/deployment workspace from
matching applied handoffs. `deploy-agent` and `enable-schedule` are separate
**Azure-writing operations**, each requiring explicit confirmation. They check
the installed tooling, use a single-attempt journal and never invoke Terraform,
Bicep hooks or automatic role repair. A runtime key is selected by environment
variable name only; no key lookup is automatic. The offline suite tests this
helper with fake azd processes, never real application deployment.
