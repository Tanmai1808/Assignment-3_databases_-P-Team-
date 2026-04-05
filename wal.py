import json
import os
from datetime import datetime

WAL_FILE = "wal.log"

def wal_write(operation, data):
    """Log an operation BEFORE executing it."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation,   # "INSERT", "DELETE", "UPDATE"
        "data": data,
        "status": "PENDING"
    }
    with open(WAL_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"📝 WAL: Logged {operation} → {data}")


def wal_commit(operation, data):
    """Mark the last matching entry as COMMITTED."""
    lines = []
    if os.path.exists(WAL_FILE):
        with open(WAL_FILE, "r") as f:
            lines = f.readlines()

    updated = []
    committed = False
    for line in reversed(lines):
        entry = json.loads(line)
        if not committed and entry["operation"] == operation and entry["data"] == data and entry["status"] == "PENDING":
            entry["status"] = "COMMITTED"
            committed = True
        updated.insert(0, json.dumps(entry) + "\n")

    with open(WAL_FILE, "w") as f:
        f.writelines(updated)
    print(f"✅ WAL: Committed {operation} → {data}")


def wal_replay(bptree, cursor):
    if not os.path.exists(WAL_FILE):
        print("📂 No WAL file found. Fresh start.")
        return

    with open(WAL_FILE, "r") as f:
        lines = f.readlines()

    recovered = 0
    for line in lines:
        entry = json.loads(line)
        if entry["status"] == "PENDING":   # only replay truly incomplete ops
            print(f"🔄 WAL RECOVERY: Replaying {entry['operation']} → {entry['data']}")
            if entry["operation"] == "INSERT":
                bptree.insert(entry["data"]["item_id"], None)
            elif entry["operation"] == "DELETE":
                bptree.delete(entry["data"]["item_id"])
            recovered += 1

    if recovered:
        print(f"🔄 Recovered {recovered} operation(s) from WAL")
    else:
        print(f"✅ WAL clean — no recovery needed")


def wal_get_log():
    """Return all WAL entries (for the /api/wal/log endpoint)."""
    if not os.path.exists(WAL_FILE):
        return []
    with open(WAL_FILE, "r") as f:
        return [json.loads(line) for line in f.readlines()]


def wal_rollback(operation, data):
    """Mark a PENDING entry as ROLLED_BACK so it won't be replayed."""
    lines = []
    if os.path.exists(WAL_FILE):
        with open(WAL_FILE, "r") as f:
            lines = f.readlines()

    updated = []
    marked = False
    for line in reversed(lines):
        entry = json.loads(line)
        if not marked and entry["operation"] == operation and entry["data"] == data and entry["status"] == "PENDING":
            entry["status"] = "ROLLED_BACK"
            marked = True
        updated.insert(0, json.dumps(entry) + "\n")

    with open(WAL_FILE, "w") as f:
        f.writelines(updated)
    print(f"↩️  WAL: Marked {operation} → {data} as ROLLED_BACK")