"""Prepare the real Terraform application build context with synthetic CI inputs."""

import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile

from test_environment_adapter import CONTRACT
from test_toolchain import SUBSCRIPTION, TENANT, bootstrap, receipt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import application_flow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    connected = bootstrap(connected=True)
    contract = copy.deepcopy(CONTRACT)
    contract["agents"]["registry_connection_id"] = (
        contract["agents"]["project_id"] + "/connections/"
        + contract["agents"]["registry_connection_name"]
    )
    contract["gateway"].update(
        id=connected["gateway_id"], endpoint=connected["gateway_endpoint"],
        monitoring={"configuration_status": "configured"},
    )
    contract["integration"] = {
        "gateway_model_access_enabled": True, "gateway_tool_access_enabled": True,
        "registry_connection_shared": False,
        "remote_tool_connection_id": connected["remote_tool_connection_id"],
        "remote_tool_endpoint": connected["remote_tool_endpoint"],
    }
    configured = receipt(connected=True)
    configured["operation"] = "create-toolbox"
    configured["toolbox"] = application_flow.tools.toolbox_metadata(connected, "digest", "7")
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for name, value in (("contract.json", contract), ("bootstrap.json", connected),
                            ("tool.receipt.jsonl", configured)):
            (root / name).write_text(json.dumps(value) + "\n", encoding="utf-8")
        return application_flow.main([
            "prepare", "--workspace", str(args.workspace),
            "--contract", str(root / "contract.json"), "--bootstrap", str(root / "bootstrap.json"),
            "--tool-receipt", str(root / "tool.receipt.jsonl"),
            "--subscription-id", SUBSCRIPTION, "--tenant-id", TENANT,
            "--repository", "example/repository", "--agent-name", "fixture-digest",
        ])


if __name__ == "__main__":
    sys.exit(main())
