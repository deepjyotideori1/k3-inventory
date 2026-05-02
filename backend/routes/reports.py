from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials
from database import db
from deps import get_current_user, require_admin, security
from models import DailyReportCreate, DailyReportResponse, PlantReportCreate, PlantReportResponse
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid

router = APIRouter()

# ============ DAILY REPORT ROUTES ============

@router.post("/reports/daily", response_model=DailyReportResponse)
async def create_daily_report(data: DailyReportCreate, user: dict = Depends(get_current_user)):
    # Calculate expected closing based on formula
    # Filled = Opening - Sold - Refilling (local) + Received from Plant
    # Empty = Opening + Refilling (Local) - Refilling at Plant Hollongi
    expected_15kg_filled = data.opening_15kg_filled - data.sold_15kg_filled - data.refilling_15kg + data.received_from_plant_15kg
    expected_21kg_filled = data.opening_21kg_filled - data.sold_21kg_filled - data.refilling_21kg + data.received_from_plant_21kg
    expected_15kg_empty = data.opening_15kg_empty + data.refilling_15kg - data.refilling_plant_15kg
    expected_21kg_empty = data.opening_21kg_empty + data.refilling_21kg - data.refilling_plant_21kg
    
    # Calculate discrepancies
    discrepancy_15kg_filled = data.closing_15kg_filled - expected_15kg_filled
    discrepancy_21kg_filled = data.closing_21kg_filled - expected_21kg_filled
    discrepancy_15kg_empty = data.closing_15kg_empty - expected_15kg_empty
    discrepancy_21kg_empty = data.closing_21kg_empty - expected_21kg_empty
    
    has_discrepancy = any([discrepancy_15kg_filled, discrepancy_21kg_filled, discrepancy_15kg_empty, discrepancy_21kg_empty])
    
    # Get warehouse name
    warehouse = await db.warehouses.find_one({'id': data.warehouse_id}, {'_id': 0})
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    
    report = {
        'id': str(uuid.uuid4()),
        'warehouse_id': data.warehouse_id,
        'warehouse_name': warehouse['name'],
        'date': data.date,
        'opening_15kg_filled': data.opening_15kg_filled,
        'opening_21kg_filled': data.opening_21kg_filled,
        'opening_15kg_empty': data.opening_15kg_empty,
        'opening_21kg_empty': data.opening_21kg_empty,
        'sold_15kg_filled': data.sold_15kg_filled,
        'sold_21kg_filled': data.sold_21kg_filled,
        'refilling_15kg': data.refilling_15kg,
        'refilling_21kg': data.refilling_21kg,
        'refilling_plant_15kg': data.refilling_plant_15kg,
        'refilling_plant_21kg': data.refilling_plant_21kg,
        'received_from_plant_15kg': data.received_from_plant_15kg,
        'received_from_plant_21kg': data.received_from_plant_21kg,
        'closing_15kg_filled': data.closing_15kg_filled,
        'closing_21kg_filled': data.closing_21kg_filled,
        'closing_15kg_empty': data.closing_15kg_empty,
        'closing_21kg_empty': data.closing_21kg_empty,
        'remarks': data.remarks[:500] if data.remarks else "",
        'discrepancy_15kg_filled': discrepancy_15kg_filled,
        'discrepancy_21kg_filled': discrepancy_21kg_filled,
        'discrepancy_15kg_empty': discrepancy_15kg_empty,
        'discrepancy_21kg_empty': discrepancy_21kg_empty,
        'has_discrepancy': has_discrepancy,
        'status': data.status,
        'submitted_by': user['name'],
        'submitted_at': datetime.now(timezone.utc).isoformat(),
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Check if report exists for same date and warehouse
    existing = await db.daily_reports.find_one({'warehouse_id': data.warehouse_id, 'date': data.date}, {'_id': 0})
    if existing:
        # Preserve original created_at
        report['created_at'] = existing.get('created_at', report['created_at'])
        await db.daily_reports.update_one({'id': existing['id']}, {'$set': report})
        report['id'] = existing['id']
    else:
        await db.daily_reports.insert_one(report)
    
    return DailyReportResponse(**report)

@router.get("/reports/daily/today/{warehouse_id}")
async def get_today_report(warehouse_id: str, date: str = None, user: dict = Depends(get_current_user)):
    """Get today's report (including drafts) for a warehouse"""
    if not date:
        date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    report = await db.daily_reports.find_one(
        {'warehouse_id': warehouse_id, 'date': date},
        {'_id': 0}
    )
    
    if not report:
        return None
    
    # Ensure status field exists (for backward compatibility with old reports)
    if 'status' not in report:
        report['status'] = 'submitted'  # Old reports without status are considered submitted
    
    return report

@router.put("/reports/daily/{report_id}")
async def update_daily_report(report_id: str, data: DailyReportCreate, user: dict = Depends(get_current_user)):
    """Update an existing daily report - for editing drafts or own submitted reports"""
    existing = await db.daily_reports.find_one({'id': report_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check permissions: admin can edit any, managers can edit their own warehouse reports
    if user['role'] != 'admin':
        if existing['warehouse_id'] != user.get('warehouse_id'):
            raise HTTPException(status_code=403, detail="Cannot edit reports from other warehouses")
        # Managers can edit their own reports (both draft and submitted)
    
    # Get warehouse name
    warehouse = await db.warehouses.find_one({'id': data.warehouse_id}, {'_id': 0})
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    
    # Calculate expected closing based on formula
    # Filled = Opening - Sold - Refilling (local) + Received from Plant
    # Empty = Opening + Refilling (Local) - Refilling at Plant Hollongi
    expected_15kg_filled = data.opening_15kg_filled - data.sold_15kg_filled - data.refilling_15kg + data.received_from_plant_15kg
    expected_21kg_filled = data.opening_21kg_filled - data.sold_21kg_filled - data.refilling_21kg + data.received_from_plant_21kg
    expected_15kg_empty = data.opening_15kg_empty + data.refilling_15kg - data.refilling_plant_15kg
    expected_21kg_empty = data.opening_21kg_empty + data.refilling_21kg - data.refilling_plant_21kg
    
    discrepancy_15kg_filled = data.closing_15kg_filled - expected_15kg_filled
    discrepancy_21kg_filled = data.closing_21kg_filled - expected_21kg_filled
    discrepancy_15kg_empty = data.closing_15kg_empty - expected_15kg_empty
    discrepancy_21kg_empty = data.closing_21kg_empty - expected_21kg_empty
    
    has_discrepancy = any([discrepancy_15kg_filled, discrepancy_21kg_filled, discrepancy_15kg_empty, discrepancy_21kg_empty])
    
    update_data = {
        'warehouse_id': data.warehouse_id,
        'warehouse_name': warehouse['name'],
        'date': data.date,
        'opening_15kg_filled': data.opening_15kg_filled,
        'opening_21kg_filled': data.opening_21kg_filled,
        'opening_15kg_empty': data.opening_15kg_empty,
        'opening_21kg_empty': data.opening_21kg_empty,
        'sold_15kg_filled': data.sold_15kg_filled,
        'sold_21kg_filled': data.sold_21kg_filled,
        'refilling_15kg': data.refilling_15kg,
        'refilling_21kg': data.refilling_21kg,
        'refilling_plant_15kg': data.refilling_plant_15kg,
        'refilling_plant_21kg': data.refilling_plant_21kg,
        'received_from_plant_15kg': data.received_from_plant_15kg,
        'received_from_plant_21kg': data.received_from_plant_21kg,
        'closing_15kg_filled': data.closing_15kg_filled,
        'closing_21kg_filled': data.closing_21kg_filled,
        'closing_15kg_empty': data.closing_15kg_empty,
        'closing_21kg_empty': data.closing_21kg_empty,
        'remarks': data.remarks[:500] if data.remarks else "",
        'discrepancy_15kg_filled': discrepancy_15kg_filled,
        'discrepancy_21kg_filled': discrepancy_21kg_filled,
        'discrepancy_15kg_empty': discrepancy_15kg_empty,
        'discrepancy_21kg_empty': discrepancy_21kg_empty,
        'has_discrepancy': has_discrepancy,
        'status': data.status,
        'submitted_by': user['name'],
        'submitted_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.daily_reports.update_one({'id': report_id}, {'$set': update_data})
    
    updated = await db.daily_reports.find_one({'id': report_id}, {'_id': 0})
    return DailyReportResponse(**updated)

@router.get("/reports/warehouse-received-from-plant/{warehouse_id}/{date}")
async def get_warehouse_received_from_plant(warehouse_id: str, date: str, user: dict = Depends(get_current_user)):
    """Get filled cylinders delivered to a specific warehouse from Plant Hollongi for a specific date"""
    # Find plant report for this date
    plant_report = await db.plant_reports.find_one({'date': date}, {'_id': 0})
    
    received_15kg = 0
    received_21kg = 0
    
    if plant_report:
        # Check deliveries to this warehouse
        for delivery in plant_report.get('delivery_15kg', []):
            if delivery.get('warehouse_id') == warehouse_id:
                received_15kg += delivery.get('quantity', 0)
        
        for delivery in plant_report.get('delivery_21kg', []):
            if delivery.get('warehouse_id') == warehouse_id:
                received_21kg += delivery.get('quantity', 0)
    
    return {
        'date': date,
        'warehouse_id': warehouse_id,
        'received_15kg_filled': received_15kg,
        'received_21kg_filled': received_21kg,
        'synced_from_plant': plant_report is not None
    }

@router.get("/reports/plant-received/{date}")
async def get_plant_received_from_warehouses(date: str, user: dict = Depends(get_current_user)):
    """Get all warehouse refilling at plant entries for a specific date - these are empties sent to plant"""
    # Find all daily reports for this date where refilling_plant_15kg or refilling_plant_21kg > 0
    reports = await db.daily_reports.find({
        'date': date,
        '$or': [
            {'refilling_plant_15kg': {'$gt': 0}},
            {'refilling_plant_21kg': {'$gt': 0}}
        ]
    }, {'_id': 0}).to_list(100)
    
    received_15kg = []
    received_21kg = []
    total_15kg = 0
    total_21kg = 0
    
    for r in reports:
        if r.get('refilling_plant_15kg', 0) > 0:
            received_15kg.append({
                'warehouse_id': r['warehouse_id'],
                'warehouse_name': r['warehouse_name'],
                'quantity': r['refilling_plant_15kg'],
                'submitted_by': r.get('submitted_by', 'Unknown'),
                'submitted_at': r.get('submitted_at', '')
            })
            total_15kg += r['refilling_plant_15kg']
        
        if r.get('refilling_plant_21kg', 0) > 0:
            received_21kg.append({
                'warehouse_id': r['warehouse_id'],
                'warehouse_name': r['warehouse_name'],
                'quantity': r['refilling_plant_21kg'],
                'submitted_by': r.get('submitted_by', 'Unknown'),
                'submitted_at': r.get('submitted_at', '')
            })
            total_21kg += r['refilling_plant_21kg']
    
    return {
        'date': date,
        'received_15kg': received_15kg,
        'received_21kg': received_21kg,
        'total_15kg': total_15kg,
        'total_21kg': total_21kg
    }

@router.get("/reports/warehouses-received-summary/{date}")
async def get_warehouses_received_from_plant_summary(date: str, user: dict = Depends(get_current_user)):
    """Get summary of what all warehouses recorded as received from Plant Hollongi for a given date"""
    # Allow admin and Plant Hollongi managers to access this
    if user['role'] != 'admin':
        # Check if user is from Plant Hollongi
        warehouse = await db.warehouses.find_one({'id': user.get('warehouse_id')})
        if not warehouse or not warehouse.get('is_plant'):
            return {'detail': 'Access restricted to admin and Plant Hollongi managers'}
    
    # Get all warehouse daily reports for the date
    reports = await db.daily_reports.find(
        {'date': date},
        {'_id': 0}
    ).to_list(100)
    
    received_15kg = []
    received_21kg = []
    total_15kg = 0
    total_21kg = 0
    
    for r in reports:
        warehouse = await db.warehouses.find_one({'id': r.get('warehouse_id')})
        warehouse_name = warehouse['name'] if warehouse else 'Unknown'
        
        # Skip Plant Hollongi itself
        if warehouse_name == 'Plant Hollongi':
            continue
        
        if r.get('received_from_plant_15kg', 0) > 0:
            received_15kg.append({
                'warehouse_id': r.get('warehouse_id'),
                'warehouse_name': warehouse_name,
                'quantity': r.get('received_from_plant_15kg'),
                'status': r.get('status')
            })
            total_15kg += r.get('received_from_plant_15kg', 0)
        
        if r.get('received_from_plant_21kg', 0) > 0:
            received_21kg.append({
                'warehouse_id': r.get('warehouse_id'),
                'warehouse_name': warehouse_name,
                'quantity': r.get('received_from_plant_21kg'),
                'status': r.get('status')
            })
            total_21kg += r.get('received_from_plant_21kg', 0)
    
    return {
        'date': date,
        'received_15kg': received_15kg,
        'received_21kg': received_21kg,
        'total_15kg': total_15kg,
        'total_21kg': total_21kg
    }

@router.get("/reports/daily", response_model=List[DailyReportResponse])
async def get_daily_reports(
    warehouse_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    query = {}
    # Filter by warehouse - non-admin users can only see their own warehouse
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id')
    elif warehouse_id:
        query['warehouse_id'] = warehouse_id
    
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    reports = await db.daily_reports.find(query, {'_id': 0}).sort('date', -1).to_list(1000)
    return [DailyReportResponse(**r) for r in reports]

@router.get("/reports/daily/latest/{warehouse_id}")
async def get_latest_closing(warehouse_id: str, user: dict = Depends(get_current_user)):
    """Get the latest closing stock to use as opening for next day"""
    report = await db.daily_reports.find_one(
        {'warehouse_id': warehouse_id},
        {'_id': 0},
        sort=[('date', -1)]
    )
    if report:
        return {
            'opening_15kg_filled': report['closing_15kg_filled'],
            'opening_21kg_filled': report['closing_21kg_filled'],
            'opening_15kg_empty': report['closing_15kg_empty'],
            'opening_21kg_empty': report['closing_21kg_empty'],
            'last_date': report['date']
        }
    return {
        'opening_15kg_filled': 0,
        'opening_21kg_filled': 0,
        'opening_15kg_empty': 0,
        'opening_21kg_empty': 0,
        'last_date': None
    }

# ============ PLANT HOLLONGI REPORT ROUTES ============

@router.post("/reports/plant", response_model=PlantReportResponse)
async def create_plant_report(data: PlantReportCreate, user: dict = Depends(get_current_user)):
    report = {
        'id': str(uuid.uuid4()),
        'date': data.date,
        'opening_bullet_tank_kg': data.opening_bullet_tank_kg,
        'opening_15kg_filled': data.opening_15kg_filled,
        'opening_21kg_filled': data.opening_21kg_filled,
        'opening_15kg_empty': data.opening_15kg_empty,
        'opening_21kg_empty': data.opening_21kg_empty,
        'day_reloading_kg': data.day_reloading_kg,
        'day_refilled_15kg': data.day_refilled_15kg,
        'day_refilled_21kg': data.day_refilled_21kg,
        'delivery_15kg': data.delivery_15kg,
        'delivery_21kg': data.delivery_21kg,
        'received_empty_15kg': data.received_empty_15kg,
        'received_empty_21kg': data.received_empty_21kg,
        'closing_bullet_tank_kg': data.closing_bullet_tank_kg,
        'closing_15kg_filled': data.closing_15kg_filled,
        'closing_21kg_filled': data.closing_21kg_filled,
        'closing_15kg_empty': data.closing_15kg_empty,
        'closing_21kg_empty': data.closing_21kg_empty,
        'remarks': data.remarks[:500] if data.remarks else "",
        'submitted_by': user['name'],
        'submitted_at': datetime.now(timezone.utc).isoformat(),
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Check if report exists for same date
    existing = await db.plant_reports.find_one({'date': data.date}, {'_id': 0})
    if existing:
        await db.plant_reports.update_one({'id': existing['id']}, {'$set': report})
        report['id'] = existing['id']
    else:
        await db.plant_reports.insert_one(report)

    # === Mirror dealer deliveries AND dealer empty-receipts into dealer_entries ===
    # So the Dealer Reports / Dispatch summary / Inventory logs all reflect
    # the plant's dealer-direction rows automatically.
    # Idempotent: every re-submit for the same date wipes prior plant-sourced
    # entries for that date first, then re-creates them from the latest payload.
    await db.dealer_entries.delete_many({
        'date': data.date,
        'source': {'$in': ['plant_delivery', 'plant_empty_receipt']}
    })

    # Build a per-dealer totals dict: one row combines issued + returned empties.
    dealer_totals: Dict[str, Dict[str, int]] = {}

    def _add(did: str, key: str, qty):
        dealer_totals.setdefault(did, {
            'issued_15kg': 0, 'issued_21kg': 0,
            'returned_empty_15kg': 0, 'returned_empty_21kg': 0,
        })
        try:
            dealer_totals[did][key] += int(qty or 0)
        except (TypeError, ValueError):
            pass

    for row in (data.delivery_15kg or []):
        if row.get('recipient_type') == 'dealer' and row.get('dealer_id'):
            _add(row['dealer_id'], 'issued_15kg', row.get('quantity'))
    for row in (data.delivery_21kg or []):
        if row.get('recipient_type') == 'dealer' and row.get('dealer_id'):
            _add(row['dealer_id'], 'issued_21kg', row.get('quantity'))
    for row in (data.received_empty_15kg or []):
        if row.get('recipient_type') == 'dealer' and row.get('dealer_id'):
            _add(row['dealer_id'], 'returned_empty_15kg', row.get('quantity'))
    for row in (data.received_empty_21kg or []):
        if row.get('recipient_type') == 'dealer' and row.get('dealer_id'):
            _add(row['dealer_id'], 'returned_empty_21kg', row.get('quantity'))

    if dealer_totals:
        # Enrich with dealer names
        dealer_ids = list(dealer_totals.keys())
        dealer_docs = await db.dealers.find(
            {'id': {'$in': dealer_ids}}, {'_id': 0, 'id': 1, 'name': 1}
        ).to_list(len(dealer_ids))
        dealer_name_map = {d['id']: d.get('name', '') for d in dealer_docs}
        now_iso = datetime.now(timezone.utc).isoformat()
        bulk = []
        for did, qtys in dealer_totals.items():
            has_issue = qtys['issued_15kg'] + qtys['issued_21kg'] > 0
            has_receipt = qtys['returned_empty_15kg'] + qtys['returned_empty_21kg'] > 0
            if has_issue:
                bulk.append({
                    'id': str(uuid.uuid4()),
                    'dealer_id': did,
                    'dealer_name': dealer_name_map.get(did, ''),
                    'date': data.date,
                    'issued_15kg': qtys['issued_15kg'],
                    'issued_21kg': qtys['issued_21kg'],
                    'refilled_15kg': 0,
                    'refilled_21kg': 0,
                    'remarks': f"Auto-synced from Plant Daily Entry ({data.date})",
                    'source': 'plant_delivery',
                    'source_report_id': report['id'],
                    'submitted_by': user['name'],
                    'submitted_at': now_iso,
                })
            if has_receipt:
                bulk.append({
                    'id': str(uuid.uuid4()),
                    'dealer_id': did,
                    'dealer_name': dealer_name_map.get(did, ''),
                    'date': data.date,
                    'issued_15kg': 0,
                    'issued_21kg': 0,
                    'refilled_15kg': 0,
                    'refilled_21kg': 0,
                    'returned_empty_15kg': qtys['returned_empty_15kg'],
                    'returned_empty_21kg': qtys['returned_empty_21kg'],
                    'remarks': f"Empties received from dealer ({data.date})",
                    'source': 'plant_empty_receipt',
                    'source_report_id': report['id'],
                    'submitted_by': user['name'],
                    'submitted_at': now_iso,
                })
        if bulk:
            await db.dealer_entries.insert_many(bulk)

    return PlantReportResponse(**report)

@router.get("/reports/plant", response_model=List[PlantReportResponse])
async def get_plant_reports(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    query = {}
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    reports = await db.plant_reports.find(query, {'_id': 0}).sort('date', -1).to_list(1000)
    return [PlantReportResponse(**r) for r in reports]

@router.get("/reports/plant/latest")
async def get_latest_plant_closing(user: dict = Depends(get_current_user)):
    """Get the latest plant closing stock to use as opening for next day"""
    report = await db.plant_reports.find_one({}, {'_id': 0}, sort=[('date', -1)])
    if report:
        return {
            'opening_bullet_tank_kg': report['closing_bullet_tank_kg'],
            'opening_15kg_filled': report['closing_15kg_filled'],
            'opening_21kg_filled': report['closing_21kg_filled'],
            'opening_15kg_empty': report['closing_15kg_empty'],
            'opening_21kg_empty': report['closing_21kg_empty'],
            'last_date': report['date']
        }
    return {
        'opening_bullet_tank_kg': 0,
        'opening_15kg_filled': 0,
        'opening_21kg_filled': 0,
        'opening_15kg_empty': 0,
        'opening_21kg_empty': 0,
        'last_date': None
    }

