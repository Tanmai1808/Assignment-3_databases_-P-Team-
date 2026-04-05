from flask import Blueprint, jsonify, request, g
from db import get_db
from auth_middleware import admin_required, audit_log

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_all_users():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT 
                m.member_id, m.name, m.email, m.contact_number,
                m.username, m.dateOfBirth, m.image_url,
                COALESCE(r.roleName, 'Customer') as role_type,
                c.customer_id, c.signup_date, c.loyalty_points,
                dp.partner_id, dp.vehicle_type, dp.vehicleNumber,
                dp.licenseID, dp.isOnline, dp.averageRating,
                ro.owner_id, ro.role_start_date, ro.is_active
            FROM member m
            LEFT JOIN MemberRoleMapping mrm ON m.member_id = mrm.member_id
            LEFT JOIN Roles r ON mrm.roleID = r.roleID
            LEFT JOIN customer c ON m.member_id = c.member_id
            LEFT JOIN deliverypartner dp ON m.member_id = dp.member_id
            LEFT JOIN restaurantowner ro ON m.member_id = ro.member_id
            WHERE m.isDeleted = 0
            ORDER BY m.member_id
        """)
        users = cursor.fetchall()
        for u in users:
            for key in ['dateOfBirth', 'signup_date', 'role_start_date']:
                if u.get(key) and hasattr(u[key], 'isoformat'):
                    u[key] = u[key].isoformat()
        return jsonify({"status": "success", "users": users})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/user/update', methods=['PUT'])
@admin_required
def update_user():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE member 
            SET name=%s, email=%s, contact_number=%s, username=%s, dateOfBirth=%s
            WHERE member_id=%s
        """, (
            data['name'], data['email'], data['contact_number'],
            data['username'], data.get('dateOfBirth') or None,
            data['member_id']
        ))

        role = data.get('role_type')
        if role == 'Customer' and data.get('customer_id'):
            cursor.execute("UPDATE customer SET loyalty_points=%s WHERE customer_id=%s",
                           (data.get('loyalty_points') or 0, data['customer_id']))
        elif role == 'DeliveryPartner' and data.get('partner_id'):
            cursor.execute("""UPDATE deliverypartner
                SET vehicle_type=%s, vehicleNumber=%s, licenseID=%s
                WHERE partner_id=%s""",
                (data.get('vehicle_type'), data.get('vehicleNumber'),
                 data.get('licenseID'), data['partner_id']))
        elif role == 'RestaurantOwner' and data.get('owner_id'):
            cursor.execute("""UPDATE restaurantowner
                SET is_active=%s, role_start_date=%s WHERE owner_id=%s""",
                (1 if data.get('is_active') else 0,
                 data.get('role_start_date') or None, data['owner_id']))

        conn.commit()

        audit_log(
            member_id=g.user['member_id'],
            action="UPDATE",
            table_name="member",
            record_id=data['member_id'],
            details=f"Admin {g.user['name']} updated member_id={data['member_id']} (role={role})"
        )
        return jsonify({"status": "success"})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@admin_bp.route('/user/delete/<int:m_id>', methods=['DELETE'])
@admin_required
def delete_user(m_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE member SET isDeleted = 1 WHERE member_id = %s", (m_id,))
        conn.commit()
        audit_log(
            member_id=g.user['member_id'],
            action="DELETE",
            table_name="member",
            record_id=m_id,
            details=f"Admin {g.user['name']} soft-deleted member_id={m_id}"
        )
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()