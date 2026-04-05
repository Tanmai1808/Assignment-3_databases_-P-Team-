from flask import Blueprint, jsonify, request
from db import get_db
from decimal import Decimal
import datetime

# Create the Blueprint
restaurant_bp = Blueprint('restaurant', __name__)

def serialize(obj):
    """Deep serialization for JSON compatibility."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    return obj

def clean(row):
    """Ensures every dictionary row is JSON safe."""
    if not row:
        return None
    return {k: serialize(v) for k, v in row.items()}

# --- DASHBOARD DATA ---
@restaurant_bp.route('/dashboard/<int:m_id>', methods=['GET'])
def get_dashboard(m_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Fetch Restaurant Info
        cursor.execute("""
            SELECT r.*, m.name as owner_name, m.email 
            FROM restaurant r
            JOIN restaurantowner ro ON r.owner_id = ro.owner_id
            JOIN Member m ON ro.member_id = m.member_id
            WHERE ro.member_id = %s AND r.isDeleted = 0
        """, (m_id,))
        restaurant = cursor.fetchone()

        if not restaurant:
            return jsonify({"status": "error", "message": "No restaurant found"}), 404

        res_id = restaurant['restaurant_id']

        # 2. Stats
        cursor.execute("""
            SELECT COUNT(*) as total_orders, COALESCE(SUM(total_amount), 0) as revenue 
            FROM orders 
            WHERE restaurant_id = %s AND order_status != 'CANCELLED'
        """, (res_id,))
        stats = cursor.fetchone()

        # 3. Menu
        cursor.execute("""
            SELECT mi.*, c.category_name 
            FROM menuitem mi 
            LEFT JOIN category c ON mi.category_id = c.category_id 
            WHERE mi.restaurant_id = %s
        """, (res_id,))
        menu = cursor.fetchall()

        # 4. Orders with Summary
        cursor.execute("""
            SELECT o.*, COALESCE(d.delivery_status, 'Not Assigned') as delivery_status,
            (SELECT GROUP_CONCAT(CONCAT(mi.item_name, ' x', oi.quantity) SEPARATOR ', ')
             FROM orderitem oi 
             JOIN menuitem mi ON oi.item_id = mi.item_id
             WHERE oi.order_id = o.order_id) AS items_summary
            FROM orders o 
            LEFT JOIN delivery d ON o.order_id = d.order_id
            WHERE o.restaurant_id = %s 
            ORDER BY o.order_time DESC
        """, (res_id,))
        orders = cursor.fetchall()

        # 5. Reviews
        cursor.execute("SELECT * FROM foodreview WHERE restaurant_id = %s", (res_id,))
        reviews = cursor.fetchall() or []

        return jsonify({
            "status": "success",
            "restaurant": clean(restaurant),
            "stats": clean(stats),
            "menu": [clean(i) for i in menu],
            "orders": [clean(o) for o in orders],
            "reviews": [clean(r) for r in reviews]
        })
    except Exception as e:
        print(f"Error in Dashboard: {str(e)}") # Critical for debugging in terminal
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# --- MENU MANAGEMENT ---

@restaurant_bp.route('/menu/add', methods=['POST', 'OPTIONS'])
def add_item():
    if request.method == 'OPTIONS': 
        return jsonify({}), 200
        
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Extract data from the React request
        res_id = data.get('restaurant_id')
        name = data.get('item_name')
        raw_price = data.get('price')
        # Default to category 1 if none provided; matches your 'YES' for NULL in DB
        cat_id = data.get('category_id') or 1 

        # Validation: Database says these CANNOT be NULL
        if not res_id or not name or not raw_price:
            return jsonify({"status": "error", "message": "Name and Price are required"}), 400

        # Convert price to float to satisfy decimal(8,2)
        price = float(raw_price)

        query = """
            INSERT INTO menuitem (restaurant_id, item_name, price, availability, category_id) 
            VALUES (%s, %s, %s, %s, %s)
        """
        # We pass 1 for availability as default
        cursor.execute(query, (res_id, name, price, 1, cat_id))
        
        conn.commit()
        return jsonify({"status": "success"})
        
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid price format"}), 400
    except Exception as e:
        # CHECK YOUR TERMINAL: This will print the exact SQL error
        print(f"--- SQL ERROR ---: {str(e)}") 
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
        
@restaurant_bp.route('/menu/update', methods=['PUT', 'OPTIONS'])
def update_item():
    if request.method == 'OPTIONS': return jsonify({}), 200
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE menuitem SET item_name=%s, price=%s, availability=%s WHERE item_id=%s
        """, (data['item_name'], data['price'], data.get('availability', 1), data['item_id']))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@restaurant_bp.route('/menu/delete/<int:item_id>', methods=['DELETE', 'OPTIONS'])
def delete_item(item_id):
    if request.method == 'OPTIONS': return jsonify({}), 200
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM menuitem WHERE item_id = %s", (item_id,))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# --- PROFILE & ORDERS ---

@restaurant_bp.route('/profile/update', methods=['PUT', 'OPTIONS'])
def update_profile():
    if request.method == 'OPTIONS': return jsonify({}), 200
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Convert is_open to int for MySQL boolean
        is_open_val = int(data.get('is_open', 1))
        cursor.execute("""
            UPDATE restaurant SET name=%s, addressLine=%s, contact_number=%s, is_open=%s 
            WHERE restaurant_id=%s
        """, (data['name'], data['addressLine'], data['contact_number'], is_open_val, data['restaurant_id']))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@restaurant_bp.route('/order/update_status', methods=['POST', 'OPTIONS'])
def update_order_status():
    if request.method == 'OPTIONS': 
        return jsonify({}), 200
        
    data = request.json
    status = data.get('status')
    order_id = data.get('order_id')
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # 1. Update the Order Status in the main orders table
        cursor.execute("UPDATE orders SET order_status = %s WHERE order_id = %s", (status, order_id))
        
        # 2. Synchronize with Delivery table
        # We use a nested try-except here because sometimes a 'delivery' row 
        # isn't created until a rider accepts it.
        if status == 'OUT_FOR_DELIVERY':
            try:
                cursor.execute("UPDATE delivery SET delivery_status = 'PICKED_UP' WHERE order_id = %s", (order_id,))
            except Exception as delivery_err:
                print(f"Non-critical Delivery table update error: {delivery_err}")
            
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"STATUS UPDATE ERROR: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close() 