import requests
import sys
import threading

sys.stdout.reconfigure(encoding='utf-8')

INSERT_URL = "http://localhost:5001/insert"
DELETE_URL = "http://localhost:5001/delete"
BOOK_URL   = "http://localhost:5001/book"

results = {"success": 0, "failed": 0}
lock = threading.Lock()

total_users = 10

print("=== Simulating restaurant server failures ===")
print()

def place_order(user_id):
    try:
        res = requests.post(BOOK_URL, json={
            "member_id": user_id,
            "cart": {
                "701": {
                    "item_name": "Biryani",
                    "price": 230,
                    "qty": 1,
                    "restaurant_id": 401
                }
            },
            "payment_mode": "CASH",
            "lat": 17.3850,
            "lng": 78.4867,
            "total": 230
        })

        with lock:
            if res.status_code == 201:
                print(f"User {user_id} -> Order Confirmed! 201")
                results["success"] += 1
            else:
                print(f"User {user_id} -> Order FAILED: {res.status_code} Restaurant Server Down!")
                results["failed"] += 1

    except requests.exceptions.ConnectionError:
        with lock:
            print(f"User {user_id} -> Order FAILED: 503 Restaurant Server Down!")
            results["failed"] += 1

# Launch all users as threads (simulates concurrent orders)
threads = []
for user_id in range(total_users):
    t = threading.Thread(target=place_order, args=(user_id,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

# Summary
failure_rate = int((results["failed"] / total_users) * 100)

print()
print("--- Summary ---")
print(f"Orders Successful : {results['success']}")
print(f"Orders Failed     : {results['failed']}")
print(f"Failure Rate      : {failure_rate}%")
print()
print("=== Failure simulation done ===")