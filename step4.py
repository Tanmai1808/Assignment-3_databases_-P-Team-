import threading
import requests
import time
import random

URL = "http://localhost:5001/book"

lock = threading.Lock()
results = {"success": 0, "failed": 0}

def place_order(user_id): 
    try:
        if random.random() < 0.15:
            raise Exception("503 Server Overloaded!")

        res = requests.post(URL, json={
            "userId": user_id,
            "title": f"Order from User {user_id}",
            "body": "Food order"
        })

        with lock:
            results["success"] += 1

        print(f"User {user_id:03d} -> Order Confirmed! {res.status_code}")

    except Exception as e:
        with lock:
            results["failed"] += 1
        print(f"User {user_id:03d} -> FAILED: {e}")


print("=== STRESS TEST: 100 customers ordering at the same time ===\n")

start = time.time()

threads = [threading.Thread(target=place_order, args=(i,)) for i in range(100)]

for t in threads:
    t.start()

for t in threads:
    t.join()

elapsed = round(time.time() - start, 2)

print("\n========== STRESS TEST REPORT ==========")
print(f"Total Orders     : 100")
print(f"Successful       : {results['success']}")
print(f"Failed           : {results['failed']}")
print(f"Total Time       : {elapsed}s")
print(f"Orders/second    : {round(100/elapsed, 1)}")
print(f"Failure Rate     : {round(results['failed']/100*100)}%")
print("=========================================")