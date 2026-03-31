from fastapi import APIRouter, HTTPException, Depends
from database import db
from deps import get_current_user, require_admin
from models import (
    WarehouseCreate, WarehouseResponse,
    InventoryItemCreate, InventoryItemResponse
)
from typing import List
from datetime import datetime, timezone
import uuid

router = APIRouter()

# ============ WAREHOUSE ROUTES ============

@router.get("/warehouses", response_model=List[WarehouseResponse])
async def get_warehouses(user: dict = Depends(get_current_user)):
    warehouses = await db.warehouses.find({}, {'_id': 0}).to_list(100)
    return [WarehouseResponse(**w) for w in warehouses]

@router.post("/warehouses", response_model=WarehouseResponse)
async def create_warehouse(data: WarehouseCreate, user: dict = Depends(require_admin)):
    warehouse = {
        'id': str(uuid.uuid4()),
        'name': data.name,
        'location': data.location,
        'is_plant': data.is_plant,
        'is_active': data.is_active,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    await db.warehouses.insert_one(warehouse)
    return WarehouseResponse(**warehouse)

@router.put("/warehouses/{warehouse_id}", response_model=WarehouseResponse)
async def update_warehouse(warehouse_id: str, data: WarehouseCreate, user: dict = Depends(require_admin)):
    await db.warehouses.update_one(
        {'id': warehouse_id},
        {'$set': {'name': data.name, 'location': data.location, 'is_plant': data.is_plant, 'is_active': data.is_active}}
    )
    warehouse = await db.warehouses.find_one({'id': warehouse_id}, {'_id': 0})
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return WarehouseResponse(**warehouse)

@router.delete("/warehouses/{warehouse_id}")
async def delete_warehouse(warehouse_id: str, user: dict = Depends(require_admin)):
    result = await db.warehouses.delete_one({'id': warehouse_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return {"message": "Warehouse deleted successfully"}

# ============ INVENTORY ITEMS ROUTES ============

@router.get("/inventory-items", response_model=List[InventoryItemResponse])
async def get_inventory_items(user: dict = Depends(get_current_user)):
    items = await db.inventory_items.find({}, {'_id': 0}).to_list(100)
    return [InventoryItemResponse(**item) for item in items]

@router.post("/inventory-items", response_model=InventoryItemResponse)
async def create_inventory_item(data: InventoryItemCreate, user: dict = Depends(require_admin)):
    item = {
        'id': str(uuid.uuid4()),
        'name': data.name,
        'unit': data.unit,
        'category': data.category,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    await db.inventory_items.insert_one(item)
    return InventoryItemResponse(**item)

