import bcrypt
import jwt
import logging
from datetime import datetime, timezone, timedelta
from database import db

logger = logging.getLogger(__name__)

JWT_SECRET = None
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24


def init_jwt_secret(secret):
    global JWT_SECRET
    JWT_SECRET = secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        'user_id': user_id,
        'email': email,
        'role': role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


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


async def log_audit(user_id: str, user_name: str, action: str, resource_type: str, resource_id: str = None, details: str = None):
    """Log an audit entry for tracking user actions"""
    try:
        audit_entry = {
            'user_id': user_id,
            'user_name': user_name,
            'action': action,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'details': details,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        await db.audit_logs.insert_one(audit_entry)
    except Exception as e:
        logger.error(f"Failed to log audit: {e}")


def _count_cylinders(cylinder_nos_str):
    """Count cylinder quantity from the cylinder_nos field (should be a number)"""
    if not cylinder_nos_str or not str(cylinder_nos_str).strip():
        return 0
    val = str(cylinder_nos_str).strip()
    try:
        return int(val)
    except ValueError:
        parts = [p.strip() for p in val.split(',') if p.strip()]
        return len(parts)


def _get_date_range_for_period(period, custom_start=None, custom_end=None):
    """Return (start_date, end_date) strings for a given period"""
    today = datetime.now(timezone.utc).date()
    if period == 'daily':
        return str(today), str(today)
    elif period == 'monthly':
        return str(today.replace(day=1)), str(today)
    elif period == 'quarterly':
        q_month = ((today.month - 1) // 3) * 3 + 1
        return str(today.replace(month=q_month, day=1)), str(today)
    elif period == 'yearly':
        return str(today.replace(month=1, day=1)), str(today)
    elif period == 'custom' and custom_start and custom_end:
        return custom_start, custom_end
    return str(today), str(today)
