from app import db
import json

res = db.query_one("SELECT metrics FROM model_runs WHERE run_type='xgboost' ORDER BY run_id DESC LIMIT 1")
if res:
    print(json.dumps(res['metrics'], indent=2))
else:
    print("No metrics found")
