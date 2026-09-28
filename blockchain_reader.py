"""
Blockchain Reader
Read-only access to the Financial Record smart contract's storage.
Reads contract state directly (no admin key required), mirroring the
DataKey enum defined in the contract's lib.rs.

A Soroban contract can keep each piece of state in one of three
storage areas (instance, persistent, or temporary). This reader does
not assume which one the contract uses for a given key - it checks
all three, in order, and returns whichever one actually has the
value.
"""

from stellar_sdk import scval
from stellar_sdk import xdr as stellar_xdr

CONTRACT_ID = "CDF3GYM6H56PDTFW6XNEDTGICGSMOMN5FLZHPKTURJHOH5WJTNW3NQ42"

PERSISTENT = stellar_xdr.ContractDataDurability.PERSISTENT
TEMPORARY = stellar_xdr.ContractDataDurability.TEMPORARY

_INSTANCE_STORAGE_KEY = stellar_xdr.SCVal(
    type=stellar_xdr.SCValType.SCV_LEDGER_KEY_CONTRACT_INSTANCE
)


def _variant_key(name, value=None):
    if value is None:
        return scval.to_symbol(name)
    return scval.to_vec([scval.to_symbol(name), value])


def _fetch_entry(server, key_scval, durability):
    try:
        return server.get_contract_data(
            contract_id=CONTRACT_ID,
            key=key_scval,
            durability=durability,
        )
    except Exception as e:
        if "not found" in str(e).lower() or "404" in str(e):
            return None
        raise


def _read_direct(server, key_scval, durability):
    entry = _fetch_entry(server, key_scval, durability)
    if entry is None or entry.val is None:
        return None
    return scval.to_native(entry.val)


def _read_instance(server, key_scval):
    entry = _fetch_entry(server, _INSTANCE_STORAGE_KEY, PERSISTENT)
    if entry is None or entry.val is None:
        return None

    instance = getattr(entry.val, "instance", None)
    storage = getattr(instance, "storage", None) if instance else None
    if not storage:
        return None

    target = scval.to_native(key_scval)
    for map_entry in storage:
        try:
            if scval.to_native(map_entry.key) == target:
                return scval.to_native(map_entry.val)
        except Exception:
            continue
    return None


def _read(server, key_scval):
    value = _read_direct(server, key_scval, PERSISTENT)
    if value is not None:
        return value

    value = _read_direct(server, key_scval, TEMPORARY)
    if value is not None:
        return value

    return _read_instance(server, key_scval)


def get_budget(server, category: str):
    key = _variant_key("Budget", scval.to_symbol(category))
    return _read(server, key)


def get_spent(server, category: str):
    key = _variant_key("Spent", scval.to_symbol(category))
    return _read(server, key)


def get_flagged(server, tx_id: int) -> bool:
    key = _variant_key("Flagged", scval.to_uint32(tx_id))
    result = _read(server, key)
    return bool(result)


def get_hash(server, tx_id: int):
    key = _variant_key("Hash", scval.to_uint32(tx_id))
    return _read(server, key)


def get_tx_count(server):
    key = _variant_key("TxCount")
    return _read(server, key) or 0


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
