from fastapi import APIRouter, HTTPException, Depends
from database import db
from deps import require_admin
from models import StockUpdateRequest, PlantStockUpdateRequest
from datetime import datetime, timezone
import uuid

router = APIRouter()

# ============ STOCK UPDATE (Admin) ============

@router.post("/stock/update")
async def update_stock(data: StockUpdateRequest, user: dict = Depends(require_admin)):
    """Admin can directly update stock levels"""
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    warehouse = await db.warehouses.find_one({'id': data.warehouse_id}, {'_id': 0})
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    
    # Log the stock update
    stock_update = {
        'id': str(uuid.uuid4()),
        'warehouse_id': data.warehouse_id,
        'warehouse_name': warehouse['name'],
        'stock_15kg_filled': data.stock_15kg_filled,
        'stock_21kg_filled': data.stock_21kg_filled,
        'stock_15kg_empty': data.stock_15kg_empty,
        'stock_21kg_empty': data.stock_21kg_empty,
        'reason': data.reason,
        'updated_by': user['name'],
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Create a copy for insertion to avoid _id modification affecting response
    doc_to_insert = stock_update.copy()
    await db.stock_updates.insert_one(doc_to_insert)
    
    # Also create/update a daily report so it shows in dashboard
    daily_report = {
        'id': str(uuid.uuid4()),
        'warehouse_id': data.warehouse_id,
        'warehouse_name': warehouse['name'],
        'date': today,
        'opening_15kg_filled': data.stock_15kg_filled,
        'opening_21kg_filled': data.stock_21kg_filled,
        'opening_15kg_empty': data.stock_15kg_empty,
        'opening_21kg_empty': data.stock_21kg_empty,
        'sold_15kg_filled': 0,
        'sold_21kg_filled': 0,
        'refilling_15kg': 0,
        'refilling_21kg': 0,
        'refilling_plant_15kg': 0,
        'refilling_plant_21kg': 0,
        'closing_15kg_filled': data.stock_15kg_filled,
        'closing_21kg_filled': data.stock_21kg_filled,
        'closing_15kg_empty': data.stock_15kg_empty,
        'closing_21kg_empty': data.stock_21kg_empty,
        'remarks': data.reason or 'Stock updated by admin',
        'discrepancy_15kg_filled': 0,
        'discrepancy_21kg_filled': 0,
        'discrepancy_15kg_empty': 0,
        'discrepancy_21kg_empty': 0,
        'has_discrepancy': False,
        'submitted_by': user['name'],
        'submitted_at': datetime.now(timezone.utc).isoformat(),
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Check if report exists for today
    existing = await db.daily_reports.find_one({'warehouse_id': data.warehouse_id, 'date': today}, {'_id': 0})
    if existing:
        # Update the closing stock values AND reset discrepancies (admin override)
        await db.daily_reports.update_one(
            {'id': existing['id']}, 
            {'$set': {
                'opening_15kg_filled': data.stock_15kg_filled,
                'opening_21kg_filled': data.stock_21kg_filled,
                'opening_15kg_empty': data.stock_15kg_empty,
                'opening_21kg_empty': data.stock_21kg_empty,
                'sold_15kg_filled': 0,
                'sold_21kg_filled': 0,
                'refilling_15kg': 0,
                'refilling_21kg': 0,
                'refilling_plant_15kg': 0,
                'refilling_plant_21kg': 0,
                'closing_15kg_filled': data.stock_15kg_filled,
                'closing_21kg_filled': data.stock_21kg_filled,
                'closing_15kg_empty': data.stock_15kg_empty,
                'closing_21kg_empty': data.stock_21kg_empty,
                'discrepancy_15kg_filled': 0,
                'discrepancy_21kg_filled': 0,
                'discrepancy_15kg_empty': 0,
                'discrepancy_21kg_empty': 0,
                'has_discrepancy': False,
                'remarks': data.reason or 'Stock reset by admin',
                'submitted_by': user['name'],
                'submitted_at': datetime.now(timezone.utc).isoformat()
            }}
        )
    else:
        report_to_insert = daily_report.copy()
        await db.daily_reports.insert_one(report_to_insert)
    
    return {"message": "Stock updated successfully", "update": stock_update}

@router.post("/stock/plant-update")
async def update_plant_stock(data: PlantStockUpdateRequest, user: dict = Depends(require_admin)):
    """Admin can directly update Plant Hollongi stock levels including bullet tank"""
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    # Create a plant report with the initial stock
    report = {
        'id': str(uuid.uuid4()),
        'date': today,
        'opening_bullet_tank_kg': data.bullet_tank_kg,
        'opening_15kg_filled': data.stock_15kg_filled,
        'opening_21kg_filled': data.stock_21kg_filled,
        'opening_15kg_empty': data.stock_15kg_empty,
        'opening_21kg_empty': data.stock_21kg_empty,
        'day_refilled_15kg': 0,
        'day_refilled_21kg': 0,
        'delivery_15kg': [],
        'delivery_21kg': [],
        'received_empty_15kg': [],
        'received_empty_21kg': [],
        'closing_bullet_tank_kg': data.bullet_tank_kg,
        'closing_15kg_filled': data.stock_15kg_filled,
        'closing_21kg_filled': data.stock_21kg_filled,
        'closing_15kg_empty': data.stock_15kg_empty,
        'closing_21kg_empty': data.stock_21kg_empty,
        'remarks': data.reason or 'Initial stock set by admin',
        'submitted_by': user['name'],
        'submitted_at': datetime.now(timezone.utc).isoformat(),
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Check if report exists for today
    existing = await db.plant_reports.find_one({'date': today}, {'_id': 0})
    if existing:
        await db.plant_reports.update_one({'id': existing['id']}, {'$set': report})
        report['id'] = existing['id']
    else:
        doc_to_insert = report.copy()
        await db.plant_reports.insert_one(doc_to_insert)
    
    return {
        "message": "Plant stock updated successfully", 
        "stock": {
            "bullet_tank_kg": data.bullet_tank_kg,
            "stock_15kg_filled": data.stock_15kg_filled,
            "stock_21kg_filled": data.stock_21kg_filled,
            "stock_15kg_empty": data.stock_15kg_empty,
            "stock_21kg_empty": data.stock_21kg_empty
        }
    }

