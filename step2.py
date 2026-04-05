import threading
import requests

URL = "http://localhost:5001/book"

lock = threading.Lock()
stock_lock = threading.Lock()
results = {}

# Restaurant menu with limited stock
menu = {
    "Burger":  2,
    "Pizza":   1,
    "Biryani": 3,
    "Pasta":   1,
    "Coke":    2
}

def place_order(user_id):
    # each user randomly picks items to order
    import random
    item = random.choice(list(menu.keys()))

    with stock_lock:  # only 1 thread checks stock at a time
        if menu[item] > 0:
            menu[item] -= 1
            status = "SUCCESS"
        else:
            status = "SOLD OUT"

    if status == "SUCCESS":
        res = requests.post(URL, json={
            "user": f"user_{user_id}",
            "item": item,
            "quantity": 1
        })
        print(f"User {user_id} -> Ordered {item} -> CONFIRMED! (Stock left: {menu[item]})")
    else:
        print(f"User {user_id} -> Ordered {item} -> SORRY! {item} is SOLD OUT!")

    with lock:
        results[user_id] = {"item": item, "status": status}


print("=== Restaurant Menu Stock ===")
for item, qty in menu.items():
    print(f"  {item} -> {qty} left")

print("\n=== 10 Customers ordering at the same time ===\n")

threads = [threading.Thread(target=place_order, args=(i,)) for i in range(10)]

for t in threads:
    t.start()

for t in threads:
    t.join()

print("\n=== Final Stock After Orders ===")
for item, qty in menu.items():
    if qty == 0:
        print(f"  {item} -> SOLD OUT")
    else:
        print(f"  {item} -> {qty} left")

print("\n=== Order Summary ===")
success = [u for u, r in results.items() if r["status"] == "SUCCESS"]
failed  = [u for u, r in results.items() if r["status"] == "SOLD OUT"]
print(f"  Successful Orders : {len(success)}")
print(f"  Failed Orders     : {len(failed)}")

print("\n=== Done ===")