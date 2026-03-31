from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import db
import jwt
import os

JWT_SECRET = os.environ.get('JWT_SECRET', 'k3gas_secret_key_2024_secure')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
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

def format_inr(amount, use_symbol=True):
    """Format number in Indian Rupee format (Rs.XX,XX,XXX)"""
    if amount is None or amount == '':
        return 'Rs.0' if use_symbol else '0'
    try:
        num = float(amount)
        prefix = 'Rs.' if use_symbol else ''
        if num < 0:
            return '-' + prefix + format_inr(-num, False)
        s = str(int(num))
        if len(s) <= 3:
            result = s
        else:
            result = s[-3:]
            s = s[:-3]
            while s:
                result = s[-2:] + ',' + result
                s = s[:-2]
        decimal_part = num - int(num)
        if decimal_part > 0:
            result += f'.{int(decimal_part * 100):02d}'
        return prefix + result
    except (ValueError, TypeError):
        return 'Rs.0' if use_symbol else '0'
