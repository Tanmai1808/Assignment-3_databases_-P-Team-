def validate(cursor, bptree, table, key_col):
    # Fetch all keys from DB
    cursor.execute(f"SELECT {key_col} FROM {table} ORDER BY {key_col}")
    db_keys = sorted([row[0] for row in cursor.fetchall()])

    # Fetch all keys from B+ Tree
    tree_keys = sorted(bptree.get_all_keys())

    if db_keys == tree_keys:
        print(f"✅ VALID: DB and B+ Tree are in sync. Keys: {db_keys}")
        return True
    else:
        print(f"❌ MISMATCH!")
        print(f"   DB keys:   {db_keys}")
        print(f"   Tree keys: {tree_keys}")
        return False