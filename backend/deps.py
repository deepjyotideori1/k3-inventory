from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import db
import jwt
import os

JWT_SECRET = os.environ.get('JWT_SECRET', 'k3gas_secret_key_2024_secure')
JWT_ALGORITHM = 'HS256'

security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({'id': payload['user_id']}, {'_id': 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_admin(user: dict = Depends(get_current_user)):
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_hrms_access(user: dict = Depends(get_current_user)):
    if user['role'] not in ('admin', 'hr_admin', 'hrms_employee'):
        raise HTTPException(status_code=403, detail="HRMS access required")
    return user


async def require_hrms_admin(user: dict = Depends(get_current_user)):
    if user['role'] not in ('admin', 'hr_admin'):
        raise HTTPException(status_code=403, detail="Admin or HR Admin access required")
    return user
