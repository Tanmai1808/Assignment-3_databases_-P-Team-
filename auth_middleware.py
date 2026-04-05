from functools import wraps
from flask import request, jsonify, g
from db import get_db

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({"status": "error", "message": "No token provided. Please login."}), 401
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT s.member_id, m.name, r.roleName as role
                FROM Sessions s
                JOIN member m ON s.member_id = m.member_id
                JOIN MemberRoleMapping mrm ON m.member_id = mrm.member_id
                JOIN Roles r ON mrm.roleID = r.roleID
                WHERE s.token = %s AND s.expires_at > NOW()
            """, (token,))
            session = cursor.fetchone()
            if not session:
                return jsonify({"status": "error", "message": "Invalid or expired session. Please login again."}), 401
            g.user = session  # attach to request context
        finally:
            cursor.close()
            conn.close()
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({"status": "error", "message": "No token provided."}), 401

        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT s.member_id, m.name, r.roleName as role
                FROM Sessions s
                JOIN member m ON s.member_id = m.member_id
                JOIN MemberRoleMapping mrm ON m.member_id = mrm.member_id
                JOIN Roles r ON mrm.roleID = r.roleID
                WHERE s.token = %s AND s.expires_at > NOW()
            """, (token,))
            session = cursor.fetchone()
            if not session:
                return jsonify({"status": "error", "message": "Invalid or expired session."}), 401
            if session['role'] != 'Admin':
                # Log unauthorized attempt
                audit_log(
                    member_id=session['member_id'],
                    action="UNAUTHORIZED_ACCESS_ATTEMPT",
                    table_name="admin",
                    details=f"User {session['name']} (role={session['role']}) tried to access admin endpoint: {request.path}"
                )
                return jsonify({"status": "error", "message": "Access denied. Admins only."}), 403
            g.user = session
        finally:
            cursor.close()
            conn.close()
        return f(*args, **kwargs)
    return decorated


def audit_log(member_id, action, table_name, details="", record_id=None):
    """Write to both DB table and local audit.log file."""
    import datetime

    # 1. Write to DB
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO AuditLog (member_id, action, table_name, record_id, details, performed_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (member_id, action, table_name, record_id, details))
        conn.commit()
    except Exception as e:
        print(f"[AUDIT DB ERROR] {e}")
    finally:
        cursor.close()
        conn.close()

    # 2. Write to local file
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] member_id={member_id} action={action} table={table_name} record_id={record_id} | {details}\n"
        with open("audit.log", "a") as f:
            f.write(line)
    except Exception as e:
        print(f"[AUDIT FILE ERROR] {e}")