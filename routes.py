import json
import os
from datetime import datetime
from flask import Blueprint, jsonify, request
from db import get_db
from validation import validate
from wal import wal_write, wal_commit, wal_get_log, wal_rollback

# 🔥 B+ Tree will be injected from app.py
bptree = None

# Create a Blueprint named 'menu_bp'
menu_bp = Blueprint('menu_bp', __name__)


# ============================================================
# 1. READ: Check status
# ============================================================
@menu_bp.route('/api/status', methods=['GET'])
def check_status():
    return jsonify({"status": "success", "message": "The Food Delivery API is running!"})


# ============================================================
# 2. READ: Get menu
# ============================================================
@menu_bp.route('/api/menu', methods=['GET'])
def get_menu():
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM menuitem")
        food_items = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({"status": "success", "data": food_items})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================
# 3. CREATE: Add menu item
# ACID: WAL write → DB insert → Tree insert → commit → WAL commit → validate
# ============================================================
@menu_bp.route('/api/menu', methods=['POST'])
def add_menu_item():
    conn = None
    item_id = None
    try:
        data = request.get_json()

        item_id       = data.get('item_id')
        item_name     = data.get('item_name')
        price         = data.get('price')
        restaurant_id = data.get('restaurant_id')
        category_id   = data.get('category_id')
        availability  = data.get('availability')

        # ── DURABILITY: log intent before doing anything ──
        wal_write("INSERT", {"item_id": item_id})

        conn   = get_db()
        cursor = conn.cursor()

        sql = """INSERT INTO menuitem
                 (item_id, item_name, price, restaurant_id, category_id, availability)
                 VALUES (%s, %s, %s, %s, %s, %s)"""
        cursor.execute(sql, (item_id, item_name, price, restaurant_id, category_id, availability))

        # ── sync B+ Tree ──
        bptree.insert(item_id, None)

        conn.commit()

        # ── mark WAL entry as committed ──
        wal_commit("INSERT", {"item_id": item_id})

        # ── CONSISTENCY: DB and Tree must match ──
        is_valid = validate(cursor, bptree, "menuitem", "item_id")

        cursor.close()
        conn.close()

        return jsonify({
            "status"     : "success",
            "message"    : f"Successfully added {item_name} to the menu!",
            "consistent" : is_valid
        }), 201

    except Exception as e:
        # ── ATOMICITY: undo everything on failure ──
        if conn:
            conn.rollback()
        if item_id is not None:
            try:
                bptree.delete(item_id)
            except Exception:
                pass
        print(f"❌ INSERT rolled back for item_id={item_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================
# 4. DELETE: Remove menu item
# ACID: WAL write → DB delete → Tree delete → commit → WAL commit → validate
# ============================================================
@menu_bp.route('/api/menu/<int:item_id>', methods=['DELETE'])
def delete_menu_item(item_id):
    conn = None
    try:
        # ── DURABILITY: log intent ──
        wal_write("DELETE", {"item_id": item_id})

        conn   = get_db()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM menuitem WHERE item_id = %s", (item_id,))

        # ── sync B+ Tree ──
        bptree.delete(item_id)

        conn.commit()

        # ── mark WAL entry as committed ──
        wal_commit("DELETE", {"item_id": item_id})

        # ── CONSISTENCY: DB and Tree must match ──
        is_valid = validate(cursor, bptree, "menuitem", "item_id")

        cursor.close()
        conn.close()

        return jsonify({
            "status"     : "success",
            "message"    : f"Successfully deleted item {item_id}!",
            "consistent" : is_valid
        })

    except Exception as e:
        # ── ATOMICITY: undo on failure ──
        if conn:
            conn.rollback()
        # re-insert into tree if delete was already applied
        try:
            bptree.insert(item_id, None)
        except Exception:
            pass
        print(f"❌ DELETE rolled back for item_id={item_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================
# 5. UPDATE: Modify menu item (price / availability)
# Key: UPDATE does NOT change item_id, so Tree stays the same.
# WAL write → DB update → commit → WAL commit → validate
# ============================================================
@menu_bp.route('/api/menu/<int:item_id>', methods=['PUT'])
def update_menu_item(item_id):
    conn = None
    try:
        data             = request.get_json()
        new_price        = data.get('price')
        new_availability = data.get('availability')

        # ── DURABILITY: log intent ──
        wal_write("UPDATE", {"item_id": item_id, "price": new_price, "availability": new_availability})

        conn   = get_db()
        cursor = conn.cursor()

        sql = "UPDATE menuitem SET price = %s, availability = %s WHERE item_id = %s"
        cursor.execute(sql, (new_price, new_availability, item_id))

        # B+ Tree indexes item_id which hasn't changed — no tree modification needed.
        # (The key already exists; we just confirm it's still there.)
        if bptree.search(item_id) is None:
            bptree.insert(item_id, None)

        conn.commit()

        # ── mark WAL entry as committed ──
        wal_commit("UPDATE", {"item_id": item_id, "price": new_price, "availability": new_availability})

        # ── CONSISTENCY check ──
        is_valid = validate(cursor, bptree, "menuitem", "item_id")

        cursor.close()
        conn.close()

        return jsonify({
            "status"     : "success",
            "message"    : f"Successfully updated item {item_id}!",
            "consistent" : is_valid
        })

    except Exception as e:
        # ── ATOMICITY: rollback DB, Tree already unchanged ──
        if conn:
            conn.rollback()
        print(f"❌ UPDATE rolled back for item_id={item_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================
# 6. CRASH TEST — demonstrates Atomicity
# Inserts into DB + Tree, then crashes before commit.
# Rollback must leave BOTH DB and Tree unchanged.
# ============================================================
@menu_bp.route('/api/menu/crash', methods=['POST'])
def crash_test():
    CRASH_ID = 9999
    conn     = None
    tree_inserted = False

    try:
        wal_write("INSERT", {"item_id": CRASH_ID})

        conn   = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO menuitem
            (item_id, item_name, price, restaurant_id, category_id, availability)
            VALUES (9999, 'CrashItem', 100, 401, 601, 1)
        """)

        bptree.insert(CRASH_ID, None)
        tree_inserted = True

        # 🔥 Simulated crash — commit never reached
        raise Exception("Simulated crash before commit!")

        conn.commit()   # never executed
        wal_commit("INSERT", {"item_id": CRASH_ID})   # never executed

    except Exception as crash_err:
        if conn:
            conn.rollback()
        if tree_inserted:
            bptree.delete(CRASH_ID)
        wal_rollback("INSERT", {"item_id": CRASH_ID})   # 🔥 add this line
        print(f"🔥 CRASH caught → rolled back: {crash_err}")
    # validate after rollback — both sides must be clean
    conn2   = get_db()
    cursor2 = conn2.cursor()
    is_valid = validate(cursor2, bptree, "menuitem", "item_id")
    tree_has_crash_id = CRASH_ID in bptree.get_all_keys()
    cursor2.close()
    conn2.close()

    return jsonify({
        "status"           : "success",
        "message"          : "Crash simulated. Rollback applied to DB and B+ Tree.",
        "consistent"       : is_valid,
        "crash_id_in_tree" : tree_has_crash_id      # must be False
    })


# ============================================================
# 7. VALIDATE — manual consistency check (Consistency demo)
# ============================================================
@menu_bp.route('/api/validate', methods=['GET'])
def manual_validate():
    try:
        conn   = get_db()
        cursor = conn.cursor()

        is_valid  = validate(cursor, bptree, "menuitem", "item_id")
        tree_keys = bptree.get_all_keys()

        cursor.close()
        conn.close()

        return jsonify({
            "status"     : "success",
            "consistent" : is_valid,
            "tree_keys"  : tree_keys
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================
# 8. WAL LOG — show all WAL entries (Durability demo)
# ============================================================
@menu_bp.route('/api/wal/log', methods=['GET'])
def get_wal_log():
    try:
        log = wal_get_log()
        return jsonify({
            "status"      : "success",
            "total"       : len(log),
            "log"         : log
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500