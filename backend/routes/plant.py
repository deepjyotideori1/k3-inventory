from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials
from database import db
from deps import get_current_user, security
from models import PlantIssuanceCreate, PlantIssuanceResponse
from typing import Optional
from datetime import datetime, timezone
import uuid

router = APIRouter()

@router.post("/plant/issue-to-dealer")
async def issue_cylinders_to_dealer(data: PlantIssuanceCreate, user: dict = Depends(get_current_user)):
    """Issue filled cylinders from Hollongi Plant to a dealer"""
    if data.qty_15kg <= 0 and data.qty_21kg <= 0:
        raise HTTPException(status_code=400, detail="At least one cylinder quantity must be greater than 0")
    if data.qty_15kg < 0 or data.qty_21kg < 0:
        raise HTTPException(status_code=400, detail="Cylinder quantities cannot be negative")
    
    # Validate dealer
    dealer = await db.dealers.find_one({'id': data.dealer_id, 'is_active': True}, {'_id': 0})
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    
    # Check plant stock from latest plant report
    latest_report = await db.plant_reports.find_one({}, {'_id': 0}, sort=[('date', -1)])
    available_15kg = latest_report.get('closing_15kg_filled', 0) if latest_report else 0
    available_21kg = latest_report.get('closing_21kg_filled', 0) if latest_report else 0
    
    # Also check any issuances already made today that haven't been reflected in the closing stock
    today_issuances = await db.plant_issuances.find({'date': data.date}, {'_id': 0}).to_list(1000)
    already_issued_15 = sum(i.get('qty_15kg', 0) for i in today_issuances)
    already_issued_21 = sum(i.get('qty_21kg', 0) for i in today_issuances)
    
    effective_15 = available_15kg - already_issued_15
    effective_21 = available_21kg - already_issued_21
    
    if data.qty_15kg > effective_15:
        raise HTTPException(status_code=400, detail=f"Insufficient 15kg filled stock. Available: {effective_15}, Requested: {data.qty_15kg}")
    if data.qty_21kg > effective_21:
        raise HTTPException(status_code=400, detail=f"Insufficient 21kg filled stock. Available: {effective_21}, Requested: {data.qty_21kg}")
    
    # Create plant issuance record
    issuance = {
        'id': str(uuid.uuid4()),
        'date': data.date,
        'dealer_id': data.dealer_id,
        'dealer_name': dealer['name'],
        'qty_15kg': data.qty_15kg,
        'qty_21kg': data.qty_21kg,
        'remarks': data.remarks[:500] if data.remarks else "",
        'submitted_by': user['name'],
        'submitted_at': datetime.now(timezone.utc).isoformat(),
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    await db.plant_issuances.insert_one(issuance)
    
    # Auto-create corresponding dealer entry
    existing_dealer_entry = await db.dealer_entries.find_one({'dealer_id': data.dealer_id, 'date': data.date}, {'_id': 0})
    if existing_dealer_entry:
        # Add to existing entry
        await db.dealer_entries.update_one(
            {'id': existing_dealer_entry['id']},
            {'$inc': {'issued_15kg': data.qty_15kg, 'issued_21kg': data.qty_21kg}}
        )
    else:
        dealer_entry = {
            'id': str(uuid.uuid4()),
            'dealer_id': data.dealer_id,
            'dealer_name': dealer['name'],
            'date': data.date,
            'issued_15kg': data.qty_15kg,
            'issued_21kg': data.qty_21kg,
            'refilled_15kg': 0,
            'refilled_21kg': 0,
            'remarks': f"Auto-entry from Hollongi Plant issuance",
            'submitted_by': user['name'],
            'submitted_at': datetime.now(timezone.utc).isoformat(),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'source': 'plant_issuance'
        }
        await db.dealer_entries.insert_one(dealer_entry)
    
    issuance.pop('_id', None)
    return PlantIssuanceResponse(**{k: v for k, v in issuance.items() if k in PlantIssuanceResponse.__fields__})

@router.get("/plant/issuance-history")
async def get_plant_issuance_history(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    dealer_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get plant cylinder issuance history"""
    query = {}
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    if dealer_id:
        query['dealer_id'] = dealer_id
    
    entries = await db.plant_issuances.find(query, {'_id': 0}).sort('date', -1).to_list(1000)
    return entries

@router.get("/plant/available-stock")
async def get_plant_available_stock(
    date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get current available filled stock at Hollongi Plant"""
    latest_report = await db.plant_reports.find_one({}, {'_id': 0}, sort=[('date', -1)])
    available_15kg = latest_report.get('closing_15kg_filled', 0) if latest_report else 0
    available_21kg = latest_report.get('closing_21kg_filled', 0) if latest_report else 0
    
    # Deduct today's issuances
    check_date = date or datetime.now(timezone.utc).strftime('%Y-%m-%d')
    today_issuances = await db.plant_issuances.find({'date': check_date}, {'_id': 0}).to_list(1000)
    issued_15 = sum(i.get('qty_15kg', 0) for i in today_issuances)
    issued_21 = sum(i.get('qty_21kg', 0) for i in today_issuances)
    
    return {
        'available_15kg': available_15kg - issued_15,
        'available_21kg': available_21kg - issued_21,
        'closing_15kg': available_15kg,
        'closing_21kg': available_21kg,
        'issued_today_15kg': issued_15,
        'issued_today_21kg': issued_21
    }

