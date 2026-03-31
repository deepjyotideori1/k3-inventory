from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials
from database import db
from deps import get_current_user, require_admin, security
from typing import Optional
from datetime import datetime, timezone, timedelta

router = APIRouter()

# ============ DASHBOARD CHART DATA ============

@router.get("/dashboard/chart-data")
async def get_dashboard_chart_data(
    period: str = "30d",
    warehouse_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get aggregated chart data for dashboard"""
    now = datetime.now(timezone.utc)
    if period == "7d":
        start = (now - timedelta(days=7)).strftime('%Y-%m-%d')
    elif period == "30d":
        start = (now - timedelta(days=30)).strftime('%Y-%m-%d')
    elif period == "90d":
        start = (now - timedelta(days=90)).strftime('%Y-%m-%d')
    else:
        start = (now - timedelta(days=30)).strftime('%Y-%m-%d')
    
    end = now.strftime('%Y-%m-%d')
    
    query = {'date': {'$gte': start, '$lte': end}}
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id', '')
    elif warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    
    entries = await db.sales_entries.find(query, {'_id': 0}).to_list(5000)
    
    # 1. Daily sales trend
    daily_sales = {}
    for e in entries:
        d = e.get('date', '')
        if d not in daily_sales:
            daily_sales[d] = {'date': d, 'amount': 0, 'count': 0}
        daily_sales[d]['amount'] += e.get('amount', 0) or 0
        daily_sales[d]['count'] += 1
    daily_trend = sorted(daily_sales.values(), key=lambda x: x['date'])
    
    # 2. Payment mode breakdown
    payment_breakdown = {'cash': 0, 'online': 0, 'pending': 0}
    for e in entries:
        cash_a = e.get('cash_amount', 0) or 0
        online_a = e.get('online_amount', 0) or 0
        credit_a = e.get('credit_amount', 0) or 0
        pm = e.get('payment_mode', 'cash')
        if cash_a == 0 and online_a == 0 and credit_a == 0:
            if pm == 'cash': cash_a = e.get('amount', 0) or 0
            elif pm == 'online': online_a = e.get('amount', 0) or 0
            elif pm == 'pending': credit_a = e.get('amount', 0) or 0
        payment_breakdown['cash'] += cash_a
        payment_breakdown['online'] += online_a
        payment_breakdown['pending'] += credit_a
    
    payment_pie = [
        {'name': 'Cash', 'value': payment_breakdown['cash']},
        {'name': 'Online', 'value': payment_breakdown['online']},
        {'name': 'Pending', 'value': payment_breakdown['pending']}
    ]
    
    # 3. Connection type breakdown
    conn_types = {}
    for e in entries:
        ct = e.get('connection_type', 'unknown')
        label = {'domestic': 'Dom. New', 'commercial': 'Com. New', 'domestic_refill': 'Dom. Refill', 'commercial_refill': 'Com. Refill'}.get(ct, ct)
        conn_types[label] = conn_types.get(label, 0) + 1
    conn_bar = [{'name': k, 'count': v} for k, v in conn_types.items()]
    
    # 4. Warehouse-wise totals (admin only)
    warehouse_bar = []
    if user['role'] == 'admin' and not warehouse_id:
        wh_totals = {}
        for e in entries:
            wid = e.get('warehouse_id', '')
            wname = e.get('warehouse_name', wid)
            if wid not in wh_totals:
                wh_totals[wid] = {'name': wname, 'amount': 0, 'count': 0}
            wh_totals[wid]['amount'] += e.get('amount', 0) or 0
            wh_totals[wid]['count'] += 1
        # Resolve warehouse names
        warehouses = await db.warehouses.find({}, {'_id': 0}).to_list(100)
        wh_names = {w['id']: w['name'] for w in warehouses}
        warehouse_bar = [{'name': wh_names.get(k, v['name']), 'amount': v['amount'], 'count': v['count']} for k, v in wh_totals.items()]
    
    return {
        'daily_trend': daily_trend,
        'payment_breakdown': payment_pie,
        'connection_types': conn_bar,
        'warehouse_totals': warehouse_bar,
        'total_amount': sum(e.get('amount', 0) or 0 for e in entries),
        'total_entries': len(entries)
    }


# ============ DASHBOARD STATS ============

@router.get("/dashboard/stats")
async def get_dashboard_stats(user: dict = Depends(get_current_user)):
    warehouses = await db.warehouses.find({'is_plant': False}, {'_id': 0}).to_list(100)
    
    # Batch fetch latest reports using aggregation to avoid N+1 queries
    warehouse_ids = [w['id'] for w in warehouses]
    pipeline = [
        {'$match': {'warehouse_id': {'$in': warehouse_ids}}},
        {'$sort': {'date': -1}},
        {'$group': {'_id': '$warehouse_id', 'latest': {'$first': '$$ROOT'}}}
    ]
    latest_reports_cursor = db.daily_reports.aggregate(pipeline)
    latest_reports = {}
    async for r in latest_reports_cursor:
        latest_reports[r['_id']] = r['latest']
    
    stats = {
        'total_warehouses': len(warehouses),
        'warehouses': [],
        'discrepancies': [],
        'total_15kg_filled': 0,
        'total_21kg_filled': 0,
        'total_15kg_empty': 0,
        'total_21kg_empty': 0
    }
    
    for w in warehouses:
        latest = latest_reports.get(w['id'])
        
        warehouse_stat = {
            'id': w['id'],
            'name': w['name'],
            'closing_15kg_filled': latest['closing_15kg_filled'] if latest else 0,
            'closing_21kg_filled': latest['closing_21kg_filled'] if latest else 0,
            'closing_15kg_empty': latest['closing_15kg_empty'] if latest else 0,
            'closing_21kg_empty': latest['closing_21kg_empty'] if latest else 0,
            'last_report_date': latest['date'] if latest else None,
            'has_discrepancy': latest['has_discrepancy'] if latest else False
        }
        
        stats['warehouses'].append(warehouse_stat)
        stats['total_15kg_filled'] += warehouse_stat['closing_15kg_filled']
        stats['total_21kg_filled'] += warehouse_stat['closing_21kg_filled']
        stats['total_15kg_empty'] += warehouse_stat['closing_15kg_empty']
        stats['total_21kg_empty'] += warehouse_stat['closing_21kg_empty']
        
        if latest and latest['has_discrepancy']:
            stats['discrepancies'].append({
                'warehouse_id': w['id'],
                'warehouse_name': w['name'],
                'date': latest['date'],
                'discrepancy_15kg_filled': latest['discrepancy_15kg_filled'],
                'discrepancy_21kg_filled': latest['discrepancy_21kg_filled'],
                'discrepancy_15kg_empty': latest['discrepancy_15kg_empty'],
                'discrepancy_21kg_empty': latest['discrepancy_21kg_empty']
            })
    
    # Get plant stats
    plant_latest = await db.plant_reports.find_one({}, {'_id': 0}, sort=[('date', -1)])
    if plant_latest:
        stats['plant'] = {
            'bullet_tank_kg': plant_latest['closing_bullet_tank_kg'],
            'closing_15kg_filled': plant_latest['closing_15kg_filled'],
            'closing_21kg_filled': plant_latest['closing_21kg_filled'],
            'closing_15kg_empty': plant_latest['closing_15kg_empty'],
            'closing_21kg_empty': plant_latest['closing_21kg_empty'],
            'last_report_date': plant_latest['date']
        }
    else:
        stats['plant'] = None
    
    return stats

