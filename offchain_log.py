"""
Off-chain Log
Stores project metadata (name, handler, date) that is not recorded
on-chain, indexed by category and transaction ID, in a local JSON file.
"""

import json
import os
from datetime import datetime, timezone

LOG_PATH = os.path.join(os.path.dirname(__file__), "transactions_log.json")


def _load_raw():
    if not os.path.exists(LOG_PATH):
        return {"projects": {}}
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_raw(data):
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def log_transaction(
    category: str,
    tx_id: int,
    amount: int,
    receipt_hash: str,
    project_name: str = "",
    handler: str = "",
    date: str = None,
    is_fraud: bool = False,
):
    data = _load_raw()
    projects = data.setdefault("projects", {})

    project = projects.setdefault(category, {
        "category": category,
        "project_name": project_name,
        "handler": handler,
        "transactions": {},
    })

    if project_name:
        project["project_name"] = project_name
    if handler:
        project["handler"] = handler

    project["transactions"][str(tx_id)] = {
        "tx_id": tx_id,
        "amount": amount,
        "receipt_hash": receipt_hash,
        "date": date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "is_fraud_reported": is_fraud,
    }

    _save_raw(data)


def load_all_projects():
    return _load_raw().get("projects", {})


def load_project(category: str):
    return load_all_projects().get(category)
