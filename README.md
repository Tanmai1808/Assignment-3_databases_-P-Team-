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
