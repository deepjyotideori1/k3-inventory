from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from database import db
from deps import require_admin
from typing import Optional
import csv
import io

router = APIRouter()


def _build_query(resource_type, start_date, end_date, search):
    query = {}
    if resource_type:
        query['resource_type'] = resource_type
    # Timestamps are stored as ISO strings — prefix-range compare works for YYYY-MM-DD
    ts = {}
    if start_date:
        ts['$gte'] = start_date
    if end_date:
        # Add T23:59:59 so end_date itself is inclusive
        ts['$lte'] = f"{end_date}T23:59:59.999999"
    if ts:
        query['timestamp'] = ts
    if search:
        safe = search.strip()
        if safe:
            query['$or'] = [
                {'user_name': {'$regex': safe, '$options': 'i'}},
                {'action': {'$regex': safe, '$options': 'i'}},
                {'details': {'$regex': safe, '$options': 'i'}},
                {'resource_id': {'$regex': safe, '$options': 'i'}},
            ]
    return query


@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = 100,
    page: int = 1,
    resource_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    user: dict = Depends(require_admin)
):
    """Get audit logs (admin only).
    Filters: resource_type, start_date (YYYY-MM-DD), end_date (YYYY-MM-DD), search (user/action/details/resource_id).
    """
    query = _build_query(resource_type, start_date, end_date, search)
    skip = (page - 1) * limit
    total = await db.audit_logs.count_documents(query)
    logs = await db.audit_logs.find(query, {'_id': 0}).sort('timestamp', -1).skip(skip).limit(limit).to_list(limit)
    return {
        'logs': logs,
        'total': total,
        'page': page,
        'pages': (total + limit - 1) // limit
    }


@router.get("/audit-logs/export")
async def export_audit_logs(
    resource_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    user: dict = Depends(require_admin)
):
    """Export filtered audit logs as CSV (admin only). Capped at 50,000 rows per download."""
    query = _build_query(resource_type, start_date, end_date, search)
    logs = await db.audit_logs.find(query, {'_id': 0}).sort('timestamp', -1).to_list(50000)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Timestamp', 'User', 'User ID', 'Action', 'Resource Type', 'Resource ID', 'Details'])
    for log in logs:
        writer.writerow([
            log.get('timestamp', ''),
            log.get('user_name', ''),
            log.get('user_id', ''),
            log.get('action', ''),
            log.get('resource_type', ''),
            log.get('resource_id', ''),
            (log.get('details') or '').replace('\n', ' ').replace('\r', ' '),
        ])
    csv_bytes = buf.getvalue().encode('utf-8-sig')  # BOM so Excel opens UTF-8 correctly

    suffix = ''
    if start_date or end_date:
        suffix = f"_{start_date or 'all'}_to_{end_date or 'now'}"
    filename = f"audit_logs{suffix}.csv"

    return StreamingResponse(
        iter([csv_bytes]),
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )
