from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx

from . import config, db

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    try:
        r = httpx.get(
            f"{config.SUPABASE_URL}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": config.SUPABASE_ANON_KEY},
            timeout=5.0
        )
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_data = r.json()
        email = user_data.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="No email found in token")
        
        row = db.query_one("SELECT role FROM user_roles WHERE email=:e", {"e": email})
        role = row["role"] if row else "GUEST"
        return {"email": email, "role": role}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Authentication failed")

def require_role(allowed_roles: list[str]):
    def role_checker(user = Security(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return role_checker
