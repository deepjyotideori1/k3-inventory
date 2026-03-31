from fastapi import APIRouter, Depends
from database import db
from deps import require_admin
from helpers import log_audit
from typing import Optional
from datetime import datetime, timezone
import uuid

router = APIRouter()

@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = 100,
    page: int = 1,
    resource_type: Optional[str] = None,
    user: dict = Depends(require_admin)
):
    """Get audit logs (admin only)"""
    query = {}
    if resource_type:
        query['resource_type'] = resource_type
    
    skip = (page - 1) * limit
    total = await db.audit_logs.count_documents(query)
    logs = await db.audit_logs.find(query, {'_id': 0}).sort('timestamp', -1).skip(skip).limit(limit).to_list(limit)
    
    return {
        'logs': logs,
        'total': total,
        'page': page,
        'pages': (total + limit - 1) // limit
    }

