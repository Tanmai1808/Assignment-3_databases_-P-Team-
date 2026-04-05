import mysql.connector

def get_db():
    return mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="root123",
        database="mydb"
    )

# 👇 ADD THIS TEST CODE
if __name__ == "__main__":
    try:
        conn = get_db()
        print("✅ Connected to MySQL successfully!")
        conn.close()
    except Exception as e:
        print("❌ Error:", e) 