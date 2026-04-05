from flask import Flask, jsonify
from flask_cors import CORS

from routes import menu_bp
from auth import auth_bp
from customer import customer_bp
from Restaurant import restaurant_bp
from delivery import delivery_bp
from admin import admin_bp
from booking import booking_bp   # ← Module B APIs
from db import get_db
from wal import wal_replay 

from bptree import BPlusTree   

app = Flask(__name__)

CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)


bptree = BPlusTree(order=3)


def load_bptree():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT item_id FROM menuitem")
    rows = cursor.fetchall()
    for row in rows:
        bptree.insert(row[0], None)
    cursor.close()
    conn.close()

    # 🔥 REPLAY WAL — crash recovery
    conn2 = get_db()
    cursor2 = conn2.cursor()
    wal_replay(bptree, cursor2)
    cursor2.close()
    conn2.close()

    print("✅ B+ Tree synced with DB")



load_bptree()


# Register blueprints
app.register_blueprint(menu_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(customer_bp)
app.register_blueprint(restaurant_bp, url_prefix='/api/restaurant')
app.register_blueprint(delivery_bp, url_prefix='/api/delivery')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(booking_bp)              # ← /insert, /delete, /book

import routes
routes.bptree = bptree

import booking
booking.bptree = bptree


@app.route('/')
def index():
    return jsonify({"status": "Server is Up", "message": "Quick Bites Backend Running"})


if __name__ == '__main__':
    app.run(debug=True, port=5001)