"""
Blockchain Reader
Read-only access to the Financial Record smart contract's storage.
Reads contract state directly (no admin key required), mirroring the
DataKey enum defined in the contract's lib.rs.
"""

from stellar_sdk import scval
from stellar_sdk import xdr as stellar_xdr

CONTRACT_ID = "CDF3GYM6H56PDTFW6XNEDTGICGSMOMN5FLZHPKTURJHOH5WJTNW3NQ42"

INSTANCE = stellar_xdr.ContractDataDurability.PERSISTENT
PERSISTENT = stellar_xdr.ContractDataDurability.PERSISTENT


def _variant_key(name, value=None):
    if value is None:
        return scval.to_symbol(name)
    return scval.to_vec([scval.to_symbol(name), value])


def _read(server, key_scval, durability):
    try:
        entry = server.get_contract_data(
            contract_id=CONTRACT_ID,
            key=key_scval,
            durability=durability,
        )
    except Exception as e:
        if "not found" in str(e).lower() or "404" in str(e):
            return None
        raise

    if entry is None or entry.val is None:
        return None
    return scval.to_native(entry.val)


def get_budget(server, category: str):
    key = _variant_key("Budget", scval.to_symbol(category))
    return _read(server, key, PERSISTENT)


def get_spent(server, category: str):
    key = _variant_key("Spent", scval.to_symbol(category))
    return _read(server, key, PERSISTENT)


def get_flagged(server, tx_id: int) -> bool:
    key = _variant_key("Flagged", scval.to_uint32(tx_id))
    result = _read(server, key, PERSISTENT)
    return bool(result)


def get_hash(server, tx_id: int):
    key = _variant_key("Hash", scval.to_uint32(tx_id))
    return _read(server, key, PERSISTENT)


def get_tx_count(server):
    key = _variant_key("TxCount")
    return _read(server, key, INSTANCE) or 0


def get_project_snapshot(server, category: str):
    budget = get_budget(server, category)
    spent = get_spent(server, category)
    return {
        "category": category,
        "budget": budget,
        "spent": spent,
        "remaining": None if budget is None else budget - (spent or 0),
        "over_budget": False if budget is None else (spent or 0) > budget,
    }
