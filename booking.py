

from flask import Blueprint, jsonify, request
from db import get_db
from wal import wal_write, wal_commit, wal_rollback
from validation import validate

# ── B+ Tree injected from app.py ──
bptree = None

booking_bp = Blueprint('booking_bp', __name__)


@booking_bp.route('/insert', methods=['POST'])
def insert_item():
    """
    Expected JSON body:
    {
        "item_id"       : 101,
        "item_name"     : "Burger",
        "price"         : 120.00,
        "restaurant_id" : 1,
        "category_id"   : 2,
        "availability"  : 1
    }
    """
    conn = None
    item_id = None
    tree_inserted = False

    try:
        data = request.get_json()

        item_id       = data.get('item_id')
        item_name     = data.get('item_name')
        price         = data.get('price')
        restaurant_id = data.get('restaurant_id')
        category_id   = data.get('category_id', 1)
        availability  = data.get('availability', 1)

        # ── Basic validation ──
        if not all([item_id, item_name, price, restaurant_id]):
            return jsonify({
                "status" : "error",
                "message": "item_id, item_name, price, and restaurant_id are required"
            }), 400

        # ── DURABILITY: log intent before doing anything ──
        wal_write("INSERT", {"item_id": item_id})

        conn   = get_db()
        cursor = conn.cursor()

        # ── DB insert ──
        sql = """
            INSERT INTO menuitem
              (item_id, item_name, price, restaurant_id, category_id, availability)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (item_id, item_name, float(price),
                             restaurant_id, category_id, availability))

        # ── B+ Tree sync ──
        bptree.insert(item_id, None)
        tree_inserted = True

        # ── Commit DB transaction ──
        conn.commit()

        # ── Mark WAL entry as committed ──
        wal_commit("INSERT", {"item_id": item_id})

        # ── CONSISTENCY: DB and Tree must match ──
        is_valid = validate(cursor, bptree, "menuitem", "item_id")

        cursor.close()
        conn.close()

        return jsonify({
            "status"     : "success",
            "message"    : f"Item '{item_name}' inserted successfully (item_id={item_id})",
            "consistent" : is_valid
        }), 201

    except Exception as e:
        # ── ATOMICITY: rollback everything on failure ──
        if conn:
            conn.rollback()
        if tree_inserted and item_id is not None:
            try:
                bptree.delete(item_id)
            except Exception:
                pass
        if item_id is not None:
            wal_rollback("INSERT", {"item_id": item_id})

        print(f"❌ /insert rolled back for item_id={item_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500




@booking_bp.route('/delete', methods=['POST'])
def delete_item():
    """
    Expected JSON body:
    {
        "item_id": 101
    }
    """
    conn = None
    item_id = None
    tree_deleted = False

    try:
        data    = request.get_json()
        item_id = data.get('item_id')

        if not item_id:
            return jsonify({"status": "error", "message": "item_id is required"}), 400

        # ── DURABILITY: log intent ──
        wal_write("DELETE", {"item_id": item_id})

        conn   = get_db()
        cursor = conn.cursor()

        # ── Verify item exists before deleting ──
        cursor.execute("SELECT item_id FROM menuitem WHERE item_id = %s", (item_id,))
        if not cursor.fetchone():
            wal_rollback("DELETE", {"item_id": item_id})
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": f"item_id={item_id} not found"}), 404

        # ── DB delete ──
        cursor.execute("DELETE FROM menuitem WHERE item_id = %s", (item_id,))

        # ── B+ Tree sync ──
        bptree.delete(item_id)
        tree_deleted = True

        # ── Commit DB transaction ──
        conn.commit()

        # ── Mark WAL entry as committed ──
        wal_commit("DELETE", {"item_id": item_id})

        # ── CONSISTENCY check ──
        is_valid = validate(cursor, bptree, "menuitem", "item_id")

        cursor.close()
        conn.close()

        return jsonify({
            "status"     : "success",
            "message"    : f"Item {item_id} deleted successfully",
            "consistent" : is_valid
        })

    except Exception as e:
        # ── ATOMICITY: rollback on failure ──
        if conn:
            conn.rollback()
        # Re-insert into tree if it was deleted but DB rolled back
        if tree_deleted and item_id is not None:
            try:
                bptree.insert(item_id, None)
            except Exception:
                pass
        if item_id is not None:
            wal_rollback("DELETE", {"item_id": item_id})

        print(f"❌ /delete rolled back for item_id={item_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



@booking_bp.route('/book', methods=['POST'])
def book_order():
    """
    Expected JSON body:
    {
        "member_id"    : 5,
        "cart"         : {
            "101": { "item_name": "Burger", "price": 120, "qty": 2, "restaurant_id": 1 },
            "102": { "item_name": "Pizza",  "price": 200, "qty": 1, "restaurant_id": 1 }
        },
        "payment_mode" : "CASH",    // or "CARD", "UPI"
        "lat"          : 17.3850,
        "lng"          : 78.4867,
        "total"        : 440.00
    }
    """
    conn    = None
    order_id = None

    try:
        data         = request.get_json()
        member_id    = data.get('member_id')
        cart         = data.get('cart', {})
        payment_mode = data.get('payment_mode', 'CASH')
        lat          = data.get('lat', 0.0)
        lng          = data.get('lng', 0.0)
        total        = data.get('total', 0.0)

        if not member_id or not cart:
            return jsonify({"status": "error", "message": "member_id and cart are required"}), 400

        # ── DURABILITY: log booking intent ──
        wal_write("BOOK", {"member_id": member_id, "total": total})

        conn   = get_db()
        cursor = conn.cursor()

        # ── Step 1: Resolve customer_id ──
        cursor.execute("SELECT customer_id FROM customer WHERE member_id = %s", (member_id,))
        row = cursor.fetchone()
        if not row:
            wal_rollback("BOOK", {"member_id": member_id, "total": total})
            return jsonify({"status": "error", "message": "Customer not found"}), 404
        customer_id = row[0]

        # ── Step 2: Get address_id ──
        cursor.execute("SELECT address_id FROM address WHERE customer_id = %s LIMIT 1", (customer_id,))
        addr_row = cursor.fetchone()
        address_id = addr_row[0] if addr_row else None

        # ── Step 3: Determine restaurant_id from first cart item ──
        restaurant_id = list(cart.values())[0]['restaurant_id']

        # ── Step 4: Insert into ORDERS ──
        cursor.execute("""
            INSERT INTO orders
              (customer_id, restaurant_id, address_id, order_time, order_status, total_amount)
            VALUES (%s, %s, %s, NOW(), 'PLACED', %s)
        """, (customer_id, restaurant_id, address_id, float(total)))
        order_id = cursor.lastrowid

        # ── Step 5: Insert all ORDER ITEMS ──
        for item_id_str, item in cart.items():
            cursor.execute("""
                INSERT INTO orderitem (order_id, item_id, quantity, item_price)
                VALUES (%s, %s, %s, %s)
            """, (order_id, int(item_id_str), item['qty'], float(item['price'])))

        # ── Step 6: Insert PAYMENT record ──
        cursor.execute("""
            INSERT INTO payment (order_id, payment_mode, payment_status, amount)
            VALUES (%s, %s, 'PENDING', %s)
        """, (order_id, payment_mode, float(total)))

        # ── Step 7: Insert DELIVERY record ──
        cursor.execute("""
            INSERT INTO delivery (order_id, delivery_status)
            VALUES (%s, 'PREPARING')
        """, (order_id,))
        delivery_id = cursor.lastrowid

        # ── Step 8: Insert DELIVERY LOCATION ──
        cursor.execute("""
            INSERT INTO deliverylocation (delivery_id, latitude, longitude, recorded_at)
            VALUES (%s, %s, %s, NOW())
        """, (delivery_id, float(lat), float(lng)))

        # ── ATOMICITY: all-or-nothing commit ──
        conn.commit()

        # ── Mark WAL as committed ──
        wal_commit("BOOK", {"member_id": member_id, "total": total})

        cursor.close()
        conn.close()

        return jsonify({
            "status"      : "success",
            "message"     : f"Order placed successfully!",
            "order_id"    : order_id,
            "delivery_id" : delivery_id,
            "total"       : total
        }), 201

    except Exception as e:
        # ── ATOMICITY: rollback all inserts on any failure ──
        if conn:
            conn.rollback()
        if order_id is not None:
            wal_rollback("BOOK", {"member_id": data.get('member_id'), "total": data.get('total')})

        print(f"❌ /book rolled back for member_id={data.get('member_id')}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
