from flask import Blueprint, jsonify, request
# Assuming you have a get_db function in your main app or a db file
from db import get_db 

customer_bp = Blueprint('customer', __name__)

@customer_bp.route('/api/customer/init', methods=['GET'])
def get_customer_init():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM category")
        categories = cursor.fetchall()
        
        cursor.execute("SELECT * FROM restaurant WHERE is_open = 1 AND isDeleted = 0")
        restaurants = cursor.fetchall()
        
        return jsonify({
            "status": "success",
            "categories": categories,
            "restaurants": restaurants
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@customer_bp.route('/api/menu/filter', methods=['GET'])
def filter_menu():
    cat_id = request.args.get('category_id')
    res_id = request.args.get('restaurant_id')
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = "SELECT * FROM menuitem WHERE availability = 1"
        params = []
        
        if cat_id:
            query += " AND category_id = %s"
            params.append(cat_id)
        if res_id:
            query += " AND restaurant_id = %s"
            params.append(res_id)
            
        cursor.execute(query, params)
        items = cursor.fetchall()
        return jsonify({"status": "success", "data": items})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@customer_bp.route('/api/customer/orders/<int:m_id>', methods=['GET'])
def get_orders(m_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # We use LEFT JOIN for everything after 'orders' 
        # so that missing data doesn't hide the whole order.
        query = """
            SELECT 
                o.order_id, 
                o.order_time, 
                o.order_status, 
                o.total_amount, 
                r.name as restaurant_name,
                p.payment_mode,
                p.payment_status,
                a.house_no, 
                a.street,
                GROUP_CONCAT(mi.item_name SEPARATOR ' | ') as food_items
            FROM member m
            INNER JOIN customer c ON m.member_id = c.member_id
            INNER JOIN orders o ON c.customer_id = o.customer_id
            LEFT JOIN restaurant r ON o.restaurant_id = r.restaurant_id
            LEFT JOIN payment p ON o.order_id = p.order_id
            LEFT JOIN address a ON o.address_id = a.address_id
            LEFT JOIN orderitem oi ON o.order_id = oi.order_id
            LEFT JOIN menuitem mi ON oi.item_id = mi.item_id
            WHERE m.member_id = %s
            GROUP BY o.order_id
            ORDER BY o.order_time DESC
        """
        cursor.execute(query, (m_id,))
        orders = cursor.fetchall()
        
        # This print is your best friend. Check your terminal!
        print(f"--- DEBUG DATA ---")
        print(f"Requested Member ID: {m_id}")
        print(f"Results Found: {len(orders)}")
        
        return jsonify({"status": "success", "data": orders})
    except Exception as e:
        print(f"SQL CRASHED: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@customer_bp.route('/api/customer/profile/<int:m_id>', methods=['GET'])
def get_profile(m_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    # Join member with address via the customer table
    query = """
        SELECT m.name, m.email, m.contact_number, m.dateOfBirth, 
               a.house_no, a.street, a.city, a.pincode, a.landmark
        FROM member m
        JOIN customer c ON m.member_id = c.member_id
        LEFT JOIN address a ON c.customer_id = a.customer_id
        WHERE m.member_id = %s
        LIMIT 1
    """
    cursor.execute(query, (m_id,))
    profile = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify({"status": "success", "data": profile}) if profile else (jsonify({"status": "error"}), 404)

@customer_bp.route('/api/customer/profile/update/<int:m_id>', methods=['POST'])
def update_profile(m_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    try:
        # 1. Update Member Table
        cursor.execute("""
            UPDATE member 
            SET name=%s, contact_number=%s, dateOfBirth=%s 
            WHERE member_id=%s
        """, (data['name'], data['contact_number'], data['dateOfBirth'], m_id))
        
        # 2. Update Address Table (Assumes the user already has one entry)
        cursor.execute("""
            UPDATE address a
            JOIN customer c ON a.customer_id = c.customer_id
            SET a.house_no=%s, a.street=%s, a.city=%s, a.pincode=%s, a.landmark=%s
            WHERE c.member_id=%s
        """, (data['house_no'], data['street'], data['city'], data['pincode'], data['landmark'], m_id))
        
        conn.commit()
        return jsonify({"status": "success", "message": "Profile Updated!"})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
@customer_bp.route('/api/customer/place_order', methods=['POST'])
def place_order():
    data = request.json
    m_id = data['member_id']
    cart = data['cart'] 
    payment_mode = data['payment_mode']
    lat = data['lat']
    lng = data['lng']
    total = data['total']
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # 1. Get customer_id
        cursor.execute("SELECT customer_id FROM customer WHERE member_id = %s", (m_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"status": "error", "message": "Customer not found"}), 404
        c_id = row[0]
        
        # 2. Get the address_id
        cursor.execute("SELECT address_id FROM address WHERE customer_id = %s LIMIT 1", (c_id,))
        addr_row = cursor.fetchone()
        addr_id = addr_row[0] if addr_row else None

        # 3. Insert into ORDERS
        res_id = list(cart.values())[0]['restaurant_id']
        cursor.execute("""
            INSERT INTO orders (customer_id, restaurant_id, address_id, order_time, order_status, total_amount)
            VALUES (%s, %s, %s, NOW(), 'PLACED', %s)
        """, (c_id, res_id, addr_id, total))
        o_id = cursor.lastrowid

        # 4. Insert into ORDERITEM
        for item_id, item in cart.items():
            cursor.execute("""
                INSERT INTO orderitem (order_id, item_id, quantity, item_price)
                VALUES (%s, %s, %s, %s)
            """, (o_id, item_id, item['qty'], item['price']))

        # 5. Insert into PAYMENT 
        cursor.execute("""
            INSERT INTO payment (order_id, payment_mode, payment_status, amount)
            VALUES (%s, %s, 'PENDING', %s)
        """, (o_id, payment_mode, total))

        # 6. Insert into DELIVERY (partner_id is omitted so it stays NULL)
        cursor.execute("""
            INSERT INTO delivery (order_id, delivery_status) 
            VALUES (%s, 'PREPARING')
        """, (o_id,))
        d_id = cursor.lastrowid

        # 7. Insert into DELIVERYLOCATION
        cursor.execute("""
            INSERT INTO deliverylocation (delivery_id, latitude, longitude, recorded_at)
            VALUES (%s, %s, %s, NOW())
        """, (d_id, lat, lng))

        conn.commit()
        return jsonify({"status": "success", "order_id": o_id})

    except Exception as e:
        conn.rollback()
        print(f"SQL ORDER ERROR: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close() 