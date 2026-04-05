# CS432 Assignment 3 

## Group Name
P & Team

## Video Demo
(https://drive.google.com/file/d/1j9A88eCZsyOMBJvNatYaWzyokjfEVlJn/view?usp=sharing)

## Project Overview
A food delivery backend built with Flask and MySQL, featuring a custom
B+ Tree index with full ACID transaction support.

## Module A — Transaction Engine & Crash Recovery

### How to run
1. Install dependencies:
   pip install flask flask-cors mysql-connector-python

2. Set up MySQL database and update db.py with your credentials

3. Run the server:
   python app.py

### Key files
- bptree.py — Custom B+ Tree implementation
- wal.py — Write-Ahead Log for durability and crash recovery
- validation.py — DB and B+ Tree consistency checker
- routes.py — API routes with WAL and validation integrated

### API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/validate | Check DB and Tree consistency |
| GET | /api/wal/log | View WAL log entries |
| POST | /api/menu | Add menu item |
| DELETE | /api/menu/<id> | Delete menu item |
| PUT | /api/menu/<id> | Update menu item |
| POST | /api/menu/crash | Simulate crash and rollback |

### ACID Properties implemented
- Atomicity: Crash rollback on both DB and B+ Tree
- Consistency: validate() checks DB and Tree match after every operation
- Durability: WAL persists to disk, replayed on restart


Module B: Multi-User Behaviour and Stress Testing

## Overview
This module tests how the food delivery system behaves when many users interact with it at the same time. Four experiments were conducted — concurrent usage, race condition, failure simulation, and stress testing.

---

## Tech Stack
- **Backend** — Flask/FastAPI (localhost:5001)
- **Database** — SQLite (B+ Tree internally)
- **Testing** — Python threading module
- **Language** — Python 3

---

## Folder Structure
module-b/
step1.py        # Concurrent users test
step2.py        # Race condition test
step3.py        # Failure simulation
step4.py        # Stress test

---

## How to Run

**1. Start your backend**
```bash
python app.py
```

**2. Run each test**
```bash
python step1.py
python step2.py
python step3.py
python step4.py
```

---

## Experiments

### Step 1 — Concurrent Users
Simulates 5 customers placing orders at the same time using Python threads.
Each thread represents one real user hitting the `/book` endpoint simultaneously.

**Output:**
=== 5 Customers ordering food at the same time ===
User 2 -> Order Placed! Order ID: 2145 | Time: 2.14s
User 0 -> Order Placed! Order ID: 2143 | Time: 2.14s
User 4 -> Order Placed! Order ID: 2142 | Time: 2.14s
User 1 -> Order Placed! Order ID: 2144 | Time: 2.15s
User 3 -> Order Placed! Order ID: 2146 | Time: 2.14s
=== All orders processed in 2.15s ===

---

### Step 2 — Race Condition
10 users simultaneously order from limited stock items. Only one user can claim the last item — the rest get sold out.

**Protection used:**
- `threading.Lock()` — only one thread checks stock at a time
- Stock never goes below zero

**Output:**
=== Restaurant Menu Stock ===
Burger -> 2 left
Pizza -> 1 left
Biryani -> 3 left
Pasta -> 1 left
Coke -> 2 left
User 1 -> Ordered Pizza -> CONFIRMED! (Stock left: 0)
User 9 -> Ordered Pizza -> SORRY! Pizza is SOLD OUT!
=== Order Summary ===
Successful Orders : 7
Failed Orders     : 3

---

### Step 3 — Failure Simulation
Simulates real server failures during order processing. When a failure occurs, the database transaction is rolled back — no partial data is saved.

**Errors simulated:**
- 400 Bad Request
- 404 Not Found
- 503 Service Unavailable

**Output:**
User 0 -> Order FAILED: 400 Restaurant Server Down!
User 1 -> Order FAILED: 404 Restaurant Server Down!
User 2 -> Order Confirmed! 201
--- Summary ---
Orders Successful : 8
Orders Failed     : 2
Failure Rate      : 20%

---

### Step 4 — Stress Test
Fires 100 concurrent requests to test system stability under heavy load.

**Output:**
========== STRESS TEST REPORT ==========
Total Orders     : 100
Successful       : 83
Failed           : 17
Total Time       : 2.27s
Orders/second    : 44.1
Failure Rate     : 17%

---

## How Correctness is Ensured
- Every order is wrapped in a database transaction — full commit or full rollback
- Stock is only reduced after a successful order confirmation
- Failed orders leave no trace in the database

## How Failures Are Handled
- Connection errors and server errors are caught with try/except
- Transaction is rolled back on any failure
- User receives a clear error message

## How Race Conditions Are Prevented
- `threading.Lock()` ensures only one thread checks stock at a time
- Stock update uses conditional check — stock never goes negative
- Multi-user isolation maintained throughout all tests

## Database Consistency
- SQLite uses B+ Tree internally for all table storage and indexes
- After every test, successful order count matches stock reduction exactly
- No negative stock values observed in any test

---

## Results Summary

| Test | Users | Successful | Failed | Time |
|---|---|---|---|---|
| Concurrent | 5 | 5 | 0 | 2.15s |
| Race Condition | 10 | 7 | 3 | — |
| Failure Simulation | 10 | 8 | 2 | 2.95s |
| Stress Test | 100 | 83 | 17 | 2.27s |

---

## Limitations
- SQLite has limited concurrent write support — PostgreSQL recommended for production
- Failures in Step 3 are simulated, not real network failures
- All tests run on localhost — real network latency not tested
