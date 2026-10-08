from app import db
try:
    print("Testing DB connection...")
    res = db.query_one("SELECT 1 as success")
    print("Success:", res)
except Exception as e:
    print("Error:", e)
