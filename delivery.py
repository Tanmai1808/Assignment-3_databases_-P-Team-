from flask import Blueprint, jsonify, request
from db import get_db

delivery_bp = Blueprint('delivery', __name__)

# ─── PROFILE ──────────────────────────────────────────────────────────────────

@delivery_bp.route('/profile/<int:m_id>', methods=['GET'])
def get_delivery_profile(m_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Profile Data - Matches your deliverypartner and member tables
        cursor.execute("""
            SELECT m.member_id, m.name, m.email, m.contact_number, m.dateOfBirth,
                   m.username, m.image_url,
                   dp.partner_id, dp.vehicle_type, dp.vehicleNumber,
                   dp.licenseID, dp.isOnline, dp.isDeleted, dp.averageRating
            FROM member m
            JOIN deliverypartner dp ON m.member_id = dp.member_id
            WHERE m.member_id = %s
        """, (m_id,))
        profile = cursor.fetchone()

        if not profile:
            return jsonify({"status": "error", "message": "Delivery partner not found"}), 404

        # 2. Stats Data - Earnings (10% commission) & Count
        cursor.execute("""
            SELECT COUNT(d.delivery_id) as total_deliveries,
                   COALESCE(SUM(o.total_amount * 0.1), 0) as total_earnings
            FROM delivery d
            JOIN deliverypartner dp ON d.partner_id = dp.partner_id
            JOIN orders o ON d.order_id = o.order_id
            WHERE dp.member_id = %s AND d.delivery_status = 'DELIVERED'
        """, (m_id,))
        stats = cursor.fetchone()

        # 3. Rating Data - Matches table 'DeliveryReview' and column 'review_time'
        cursor.execute("""
            SELECT dp.averageRating as avg_rating,
                   COUNT(dr.delivery_review_id) as total_reviews
            FROM deliverypartner dp
            LEFT JOIN DeliveryReview dr ON dp.partner_id = dr.partner_id
            WHERE dp.member_id = %s
            GROUP BY dp.partner_id
        """, (m_id,))
        rating = cursor.fetchone()

        return jsonify({"status": "success", "data": profile, "stats": stats, "rating": rating})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ─── ORDERS ───────────────────────────────────────────────────────────────────

@delivery_bp.route('/orders/<int:m_id>', methods=['GET'])
def get_delivery_orders(m_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT d.delivery_id, d.delivery_status,
                   o.order_id, o.order_status, o.total_amount, o.order_time,
                   r.name as restaurant_name, r.addressLine as restaurant_address,
                   r.city as restaurant_city,
                   mem.name as customer_name, mem.contact_number as customer_phone,
                   a.house_no, a.street, a.city as delivery_city,
                   GROUP_CONCAT(mi.item_name SEPARATOR ' | ') as food_items,
                   p.payment_mode, p.payment_status
            FROM deliverypartner dp
            JOIN delivery d ON dp.partner_id = d.partner_id
            JOIN orders o ON d.order_id = o.order_id
            JOIN restaurant r ON o.restaurant_id = r.restaurant_id
            JOIN customer c ON o.customer_id = c.customer_id
            JOIN member mem ON c.member_id = mem.member_id
            LEFT JOIN Address a ON o.address_id = a.address_id
            LEFT JOIN orderitem oi ON o.order_id = oi.order_id
            LEFT JOIN MenuItem mi ON oi.item_id = mi.item_id
            LEFT JOIN payment p ON o.order_id = p.order_id
            WHERE dp.member_id = %s
            GROUP BY d.delivery_id
            ORDER BY o.order_time DESC
        """, (m_id,))
        orders = cursor.fetchall()
        return jsonify({"status": "success", "data": orders})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ─── REVIEWS ──────────────────────────────────────────────────────────────────

@delivery_bp.route('/reviews/<int:m_id>', methods=['GET'])
def get_delivery_reviews(m_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # Table is 'DeliveryReview', Columns are 'comments' and 'review_time'
        cursor.execute("""
            SELECT dr.delivery_review_id, dr.rating, dr.comments, dr.review_time,
                   mem.name as customer_name,
                   o.order_id, o.order_time
            FROM deliverypartner dp
            JOIN DeliveryReview dr ON dp.partner_id = dr.partner_id
            JOIN orders o ON dr.order_id = o.order_id
            JOIN customer c ON o.customer_id = c.customer_id
            JOIN member mem ON c.member_id = mem.member_id
            WHERE dp.member_id = %s
            ORDER BY dr.review_time DESC
        """, (m_id,))
        reviews = cursor.fetchall()
        return jsonify({"status": "success", "data": reviews})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ... (Keep other functions like available-orders, accept, update-status, and toggle-status)  current delivery.py....give the updated code