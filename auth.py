from flask import Blueprint, request, jsonify
from db import get_db
from auth_middleware import audit_log
import uuid, datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/api')

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    email    = data.get('email')
    password = data.get('password')

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT m.member_id, m.name, m.email, r.roleName as role
            FROM member m
            JOIN MemberRoleMapping mrm ON m.member_id = mrm.member_id
            JOIN Roles r ON mrm.roleID = r.roleID
            WHERE m.email = %s AND m.password = %s AND m.isDeleted = 0
        """, (email, password))
        user = cursor.fetchone()

        if not user:
            return jsonify({"status": "error", "message": "Invalid credentials"}), 401

        # Create session token (expires in 8 hours)
        token = str(uuid.uuid4())
        expires_at = datetime.datetime.now() + datetime.timedelta(hours=8)

        cursor.execute("""
            INSERT INTO Sessions (member_id, token, expires_at)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE token=VALUES(token), expires_at=VALUES(expires_at)
        """, (user['member_id'], token, expires_at))
        conn.commit()

        audit_log(
            member_id=user['member_id'],
            action="LOGIN",
            table_name="Sessions",
            details=f"{user['name']} logged in as {user['role']}"
        )

        return jsonify({
            "status": "success",
            "token": token,
            "user": {
                "id":    user['member_id'],
                "name":  user['name'],
                "email": user['email'],
                "role":  user['role']
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route('/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return jsonify({"status": "error", "message": "No token"}), 400

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT member_id FROM Sessions WHERE token = %s", (token,))
        row = cursor.fetchone()
        if row:
            audit_log(member_id=row['member_id'], action="LOGOUT", table_name="Sessions", details="User logged out")
            cursor.execute("DELETE FROM Sessions WHERE token = %s", (token,))
            conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()