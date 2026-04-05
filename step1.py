import threading
import requests
import time

URL = "http://localhost:5001/book"

# Real data from database
MEMBER_IDS = [2, 3, 4, 5, 6]  # real member_ids from  DB

def place_order(user_id):
    order = {
        "member_id": MEMBER_IDS[user_id],
        "cart": {
            "701": {
                "item_name": "Chicken Biryani",
                "price": 230,
                "qty": 1,
                "restaurant_id": 401
            }
        },
        "payment_mode": "CASH",
        "lat": 17.3850,
        "lng": 78.4867,
        "total": 230
    }
    try:
        res = requests.post(URL, json=order)
        data = res.json()
        if data["status"] == "success":
            print(f"User {user_id} -> Order Placed! Order ID: {data['order_id']} | Time: {res.elapsed.total_seconds():.2f}s")
        else:
            print(f"User {user_id} -> Order FAILED: {data['message']}")
    except Exception as e:
        print(f"User {user_id} -> Order FAILED: {e}")


print("=== 5 Customers ordering food at the same time ===\n")

start = time.time()

threads = [threading.Thread(target=place_order, args=(i,)) for i in range(5)]

for t in threads:
    t.start()

for t in threads:
    t.join()

elapsed = round(time.time() - start, 2)

print(f"\n=== All orders processed in {elapsed}s ===")