"""
Dashboard API Server
Read-only REST API that merges on-chain data from the Stellar smart
contract with off-chain project metadata, for consumption by the
public transparency dashboard.
"""

import os
from flask import Flask, jsonify
from stellar_sdk import SorobanServer

import blockchain_reader as chain
import offchain_log as log

app = Flask(__name__)

RPC_URL = "https://soroban-testnet.stellar.org"
server = SorobanServer(RPC_URL)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


def _merge_project(category: str, offchain: dict):
    snapshot = chain.get_project_snapshot(server, category)

    transactions = []
    for tx in offchain.get("transactions", {}).values():
        tx_id = tx["tx_id"]
        transactions.append({
            **tx,
            "flagged_on_chain": chain.get_flagged(server, tx_id),
            "hash_on_chain": chain.get_hash(server, tx_id),
        })
    transactions.sort(key=lambda t: t["tx_id"])

    return {
        "category": category,
        "project_name": offchain.get("project_name", ""),
        "handler": offchain.get("handler", ""),
        "budget": snapshot["budget"],
        "spent": snapshot["spent"],
        "remaining": snapshot["remaining"],
        "over_budget": snapshot["over_budget"],
        "has_risk_alert": any(t["flagged_on_chain"] for t in transactions),
        "transactions": transactions,
    }


@app.route("/")
def health_check():
    return jsonify({"status": "ok", "message": "Dashboard API is running. See /api/projects for data."})


@app.route("/api/debug/<category>")
def debug_read(category):
    """
    Temporary troubleshooting route. Shows exactly which storage area
    (persistent / temporary / instance) a value was found in, or the
    raw error if the call itself fails. Remove this route once
    budgets/spent are showing correctly on /api/projects.
    """
    import traceback
    import stellar_sdk
    from stellar_sdk import scval

    result = {
        "category": category,
        "contract_id": chain.CONTRACT_ID,
        "stellar_sdk_version": getattr(stellar_sdk, "__version__", "unknown"),
    }

    key = chain._variant_key("Budget", scval.to_symbol(category))

    for label, fn in [
        ("persistent", lambda: chain._read_direct(server, key, chain.PERSISTENT)),
        ("temporary", lambda: chain._read_direct(server, key, chain.TEMPORARY)),
        ("instance", lambda: chain._read_instance(server, key)),
    ]:
        try:
            result[label] = fn()
        except Exception as e:
            result[label] = f"ERROR: {type(e).__name__}: {e}"

    try:
        instance_entry = server.get_contract_data(
            contract_id=chain.CONTRACT_ID,
            key=chain._INSTANCE_STORAGE_KEY,
            durability=chain.PERSISTENT,
        )
        result["contract_instance_found"] = instance_entry is not None
        if instance_entry is not None and instance_entry.val is not None:
            instance = getattr(instance_entry.val, "instance", None)
            storage = getattr(instance, "storage", None) if instance else None
            result["instance_storage_entry_count"] = len(storage) if storage else 0
            if storage:
                result["instance_storage_keys_sample"] = [
                    repr(scval.to_native(e.key)) for e in list(storage)[:10]
                ]
    except Exception as e:
        result["contract_instance_error"] = f"{type(e).__name__}: {e}"
        result["contract_instance_traceback"] = traceback.format_exc()

    return jsonify(result)


@app.route("/api/projects")
def all_projects():
    offchain_projects = log.load_all_projects()
    merged = [
        _merge_project(category, data)
        for category, data in offchain_projects.items()
    ]
    merged.sort(key=lambda p: p["category"])
    return jsonify(merged)


@app.route("/api/projects/<category>")
def one_project(category):
    offchain = log.load_project(category)
    if offchain is None:
        return jsonify({"error": f"No project found for category '{category}'"}), 404
    return jsonify(_merge_project(category, offchain))


@app.route("/api/summary")
def summary():
    projects = all_projects().json

    total_budget = sum(p["budget"] or 0 for p in projects)
    total_spent = sum(p["spent"] or 0 for p in projects)
    flagged_count = sum(
        1 for p in projects for t in p["transactions"] if t["flagged_on_chain"]
    )
    over_budget_count = sum(1 for p in projects if p["over_budget"])

    return jsonify({
        "project_count": len(projects),
        "total_budget": total_budget,
        "total_spent": total_spent,
        "total_remaining": total_budget - total_spent,
        "flagged_transaction_count": flagged_count,
        "over_budget_project_count": over_budget_count,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = "0.0.0.0" if "PORT" in os.environ else "127.0.0.1"
    debug = "PORT" not in os.environ

    print(f"Starting dashboard API on http://{host}:{port} ...")
    app.run(host=host, port=port, debug=debug)
