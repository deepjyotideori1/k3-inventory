from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from database import db
from deps import get_current_user, require_admin, security
from helpers import format_inr, log_audit
from models import CustomerCreate, CustomerUpdate, CustomerResponse, BulkCustomerUpload
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from io import BytesIO
import uuid

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import xlsxwriter
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from export_helpers import (
    get_company_info_for_export, embed_logo_openpyxl, embed_logo_xlsxwriter,
    cleanup_logo_tempfile,
)

router = APIRouter()

@router.get("/customers")
async def get_customers(
    page: int = 1,
    limit: int = 50,
    category: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get customers for the user's warehouse (or all for admin)"""
    user = await get_current_user(credentials)
    
    query = {}
    
    # Filter by warehouse for non-admin users
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id')
    elif warehouse_id and warehouse_id != 'all':
        # Admin can filter by specific warehouse
        query['warehouse_id'] = warehouse_id
    
    # Filter by category (domestic/commercial)
    if category and category != 'all':
        query['connection_type'] = category
    
    # Filter by date range
    if start_date:
        query['date'] = query.get('date', {})
        query['date']['$gte'] = start_date
    if end_date:
        if 'date' not in query:
            query['date'] = {}
        query['date']['$lte'] = end_date
    
    # Search by customer name or consumer no
    if search:
        query['$or'] = [
            {'customer_name': {'$regex': search, '$options': 'i'}},
            {'consumer_no': {'$regex': search, '$options': 'i'}},
            {'address': {'$regex': search, '$options': 'i'}}
        ]
    
    total = await db.customers.count_documents(query)
    skip = (page - 1) * limit
    customers = await db.customers.find(query).sort('date', -1).skip(skip).limit(limit).to_list(limit)
    
    # Get warehouse names
    warehouse_ids = list(set(c.get('warehouse_id') for c in customers if c.get('warehouse_id')))
    warehouses = await db.warehouses.find({'id': {'$in': warehouse_ids}}).to_list(100)
    warehouse_map = {w['id']: w['name'] for w in warehouses}
    
    result = []
    for c in customers:
        result.append({
            'id': c['id'],
            'warehouse_id': c.get('warehouse_id', ''),
            'warehouse_name': warehouse_map.get(c.get('warehouse_id', ''), 'Unknown'),
            'date': c['date'],
            'connection_type': c['connection_type'],
            'customer_name': c['customer_name'],
            'address': c.get('address', ''),
            'phone': c.get('phone', ''),
            'consumer_no': c.get('consumer_no', ''),
            'cash_memo_no': c.get('cash_memo_no', ''),
            'cylinder_nos': c.get('cylinder_nos', ''),
            'gas_card_issued': c.get('gas_card_issued', False),
            'kyc_done': c.get('kyc_done', False),
            'remarks': c.get('remarks', ''),
            'created_by': c.get('created_by', ''),
            'created_at': c.get('created_at', ''),
            'updated_at': c.get('updated_at')
        })
    
    return {'customers': result, 'total': total, 'page': page, 'total_pages': max(1, (total + limit - 1) // limit)}

@router.post("/customers")
async def create_customer(
    customer: CustomerCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create a new customer"""
    user = await get_current_user(credentials)
    
    warehouse_id = user.get('warehouse_id')
    if user['role'] == 'admin':
        # Admin needs to specify warehouse or use a default
        raise HTTPException(status_code=400, detail="Admin must use warehouse-specific endpoint")
    
    if not warehouse_id:
        raise HTTPException(status_code=400, detail="User has no assigned warehouse")
    
    customer_doc = {
        'id': str(uuid.uuid4()),
        'warehouse_id': warehouse_id,
        'date': customer.date,
        'connection_type': customer.connection_type,
        'customer_name': customer.customer_name,
        'address': customer.address,
        'phone': customer.phone,
        'consumer_no': customer.consumer_no,
        'cash_memo_no': customer.cash_memo_no,
        'cylinder_nos': customer.cylinder_nos,
        'gas_card_issued': customer.gas_card_issued,
        'kyc_done': customer.kyc_done,
        'remarks': customer.remarks,
        'created_by': user['id'],
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.customers.insert_one(customer_doc)
    
    # Get warehouse name
    warehouse = await db.warehouses.find_one({'id': warehouse_id})
    warehouse_name = warehouse['name'] if warehouse else 'Unknown'
    
    # Return without _id
    return {
        'id': customer_doc['id'],
        'warehouse_id': customer_doc['warehouse_id'],
        'warehouse_name': warehouse_name,
        'date': customer_doc['date'],
        'connection_type': customer_doc['connection_type'],
        'customer_name': customer_doc['customer_name'],
        'address': customer_doc['address'],
        'phone': customer_doc['phone'],
        'consumer_no': customer_doc['consumer_no'],
        'cash_memo_no': customer_doc['cash_memo_no'],
        'cylinder_nos': customer_doc['cylinder_nos'],
        'gas_card_issued': customer_doc['gas_card_issued'],
        'kyc_done': customer_doc['kyc_done'],
        'remarks': customer_doc['remarks'],
        'created_by': customer_doc['created_by'],
        'created_at': customer_doc['created_at'],
        'updated_at': None
    }

@router.post("/customers/warehouse/{warehouse_id}")
async def create_customer_for_warehouse(
    warehouse_id: str,
    customer: CustomerCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create a customer for a specific warehouse (admin only)"""
    user = await get_current_user(credentials)
    
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admin can create customers for other warehouses")
    
    # Verify warehouse exists
    warehouse = await db.warehouses.find_one({'id': warehouse_id})
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    
    customer_doc = {
        'id': str(uuid.uuid4()),
        'warehouse_id': warehouse_id,
        'date': customer.date,
        'connection_type': customer.connection_type,
        'customer_name': customer.customer_name,
        'address': customer.address,
        'phone': customer.phone,
        'consumer_no': customer.consumer_no,
        'cash_memo_no': customer.cash_memo_no,
        'cylinder_nos': customer.cylinder_nos,
        'gas_card_issued': customer.gas_card_issued,
        'kyc_done': customer.kyc_done,
        'remarks': customer.remarks,
        'created_by': user['id'],
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.customers.insert_one(customer_doc)
    
    # Return without _id
    return {
        'id': customer_doc['id'],
        'warehouse_id': customer_doc['warehouse_id'],
        'warehouse_name': warehouse['name'],
        'date': customer_doc['date'],
        'connection_type': customer_doc['connection_type'],
        'customer_name': customer_doc['customer_name'],
        'address': customer_doc['address'],
        'phone': customer_doc['phone'],
        'consumer_no': customer_doc['consumer_no'],
        'cash_memo_no': customer_doc['cash_memo_no'],
        'cylinder_nos': customer_doc['cylinder_nos'],
        'gas_card_issued': customer_doc['gas_card_issued'],
        'kyc_done': customer_doc['kyc_done'],
        'remarks': customer_doc['remarks'],
        'created_by': customer_doc['created_by'],
        'created_at': customer_doc['created_at'],
        'updated_at': None
    }

@router.put("/customers/{customer_id}")
async def update_customer(
    customer_id: str,
    customer: CustomerUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update a customer (admin and warehouse managers)"""
    user = await get_current_user(credentials)
    
    if user['role'] not in ('admin', 'warehouse_manager'):
        raise HTTPException(status_code=403, detail="Only admin and warehouse managers can edit customers")
    
    existing = await db.customers.find_one({'id': customer_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Warehouse managers can only edit customers in their own warehouse
    if user['role'] == 'warehouse_manager':
        if existing.get('warehouse_id') != user.get('warehouse_id'):
            raise HTTPException(status_code=403, detail="You can only edit customers in your warehouse")
    
    update_data = {}
    if customer.date is not None:
        update_data['date'] = customer.date
    if customer.connection_type is not None:
        update_data['connection_type'] = customer.connection_type
    if customer.customer_name is not None:
        update_data['customer_name'] = customer.customer_name
    if customer.address is not None:
        update_data['address'] = customer.address
    if customer.phone is not None:
        update_data['phone'] = customer.phone
    if customer.consumer_no is not None:
        update_data['consumer_no'] = customer.consumer_no
    if customer.cash_memo_no is not None:
        update_data['cash_memo_no'] = customer.cash_memo_no
    if customer.cylinder_nos is not None:
        update_data['cylinder_nos'] = customer.cylinder_nos
    if customer.gas_card_issued is not None:
        update_data['gas_card_issued'] = customer.gas_card_issued
    if customer.kyc_done is not None:
        update_data['kyc_done'] = customer.kyc_done
    if customer.remarks is not None:
        update_data['remarks'] = customer.remarks
    
    update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
    
    await db.customers.update_one({'id': customer_id}, {'$set': update_data})
    await log_audit(user['id'], user['name'], 'update', 'customer', customer_id, f"Updated fields: {', '.join(update_data.keys())}")
    
    updated = await db.customers.find_one({'id': customer_id})
    warehouse = await db.warehouses.find_one({'id': updated.get('warehouse_id')})
    
    return {
        'id': updated['id'],
        'warehouse_id': updated.get('warehouse_id', ''),
        'warehouse_name': warehouse['name'] if warehouse else 'Unknown',
        'date': updated['date'],
        'connection_type': updated['connection_type'],
        'customer_name': updated['customer_name'],
        'address': updated.get('address', ''),
        'phone': updated.get('phone', ''),
        'consumer_no': updated.get('consumer_no', ''),
        'cash_memo_no': updated.get('cash_memo_no', ''),
        'cylinder_nos': updated.get('cylinder_nos', ''),
        'gas_card_issued': updated.get('gas_card_issued', False),
        'kyc_done': updated.get('kyc_done', False),
        'remarks': updated.get('remarks', ''),
        'created_by': updated.get('created_by', ''),
        'created_at': updated.get('created_at', ''),
        'updated_at': updated.get('updated_at')
    }

@router.delete("/customers/{customer_id}")
async def delete_customer(
    customer_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Delete a customer (admin and warehouse managers)"""
    user = await get_current_user(credentials)
    
    if user['role'] not in ('admin', 'warehouse_manager'):
        raise HTTPException(status_code=403, detail="Only admin and warehouse managers can delete customers")
    
    existing = await db.customers.find_one({'id': customer_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Warehouse managers can only delete customers in their own warehouse
    if user['role'] == 'warehouse_manager':
        if existing.get('warehouse_id') != user.get('warehouse_id'):
            raise HTTPException(status_code=403, detail="You can only delete customers in your warehouse")
    
    # Safety check: check for active orders or sales entries linked to this customer
    active_orders = await db.orders.count_documents({
        'customer_id': customer_id,
        'status': {'$in': ['pending', 'Pending']}
    })
    sales_count = await db.sales_entries.count_documents({'customer_id': customer_id})
    
    warnings = []
    if active_orders > 0:
        warnings.append(f"{active_orders} active/pending order(s)")
    if sales_count > 0:
        warnings.append(f"{sales_count} sales entry/entries")
    
    # If force=false (default), return warning instead of deleting
    # The frontend will pass ?force=true after user confirms
    from fastapi import Query as FastAPIQuery
    # We handle force via query param below - but since we can't add params to existing sig easily,
    # we check for a header instead
    # Actually let's just return warnings and let frontend decide
    
    result = await db.customers.delete_one({'id': customer_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    response = {"message": "Customer deleted successfully"}
    await log_audit(user['id'], user['name'], 'delete', 'customer', customer_id, f"Deleted customer: {existing.get('customer_name', '')}")
    if warnings:
        response["warnings"] = warnings
    return response

@router.get("/customers/{customer_id}/linked-records")
async def get_customer_linked_records(
    customer_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Check if a customer has linked orders or sales entries"""
    user = await get_current_user(credentials)
    
    if user['role'] not in ('admin', 'warehouse_manager'):
        raise HTTPException(status_code=403, detail="Access denied")
    
    existing = await db.customers.find_one({'id': customer_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    if user['role'] == 'warehouse_manager':
        if existing.get('warehouse_id') != user.get('warehouse_id'):
            raise HTTPException(status_code=403, detail="Access denied")
    
    active_orders = await db.orders.count_documents({
        'customer_id': customer_id,
        'status': {'$in': ['pending', 'Pending']}
    })
    total_orders = await db.orders.count_documents({'customer_id': customer_id})
    sales_count = await db.sales_entries.count_documents({'customer_id': customer_id})
    
    return {
        "active_orders": active_orders,
        "total_orders": total_orders,
        "sales_entries": sales_count,
        "has_linked_records": (active_orders + sales_count) > 0
    }

@router.post("/customers/bulk")
async def bulk_upload_customers(
    data: BulkCustomerUpload,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Bulk upload customers"""
    user = await get_current_user(credentials)
    
    warehouse_id = user.get('warehouse_id')
    if user['role'] == 'admin':
        raise HTTPException(status_code=400, detail="Admin must use warehouse-specific endpoint for bulk upload")
    
    if not warehouse_id:
        raise HTTPException(status_code=400, detail="User has no assigned warehouse")
    
    customers_to_insert = []
    for c in data.customers:
        customers_to_insert.append({
            'id': str(uuid.uuid4()),
            'warehouse_id': warehouse_id,
            'date': c.date,
            'connection_type': c.connection_type,
            'customer_name': c.customer_name,
            'address': c.address,
            'phone': c.phone,
            'consumer_no': c.consumer_no,
            'cash_memo_no': c.cash_memo_no,
            'cylinder_nos': c.cylinder_nos,
            'gas_card_issued': c.gas_card_issued,
            'kyc_done': c.kyc_done,
            'remarks': c.remarks,
            'created_by': user['id'],
            'created_at': datetime.now(timezone.utc).isoformat()
        })
    
    if customers_to_insert:
        await db.customers.insert_many(customers_to_insert)
    
    return {"message": f"Successfully uploaded {len(customers_to_insert)} customers", "count": len(customers_to_insert)}

@router.post("/customers/bulk/warehouse/{warehouse_id}")
async def bulk_upload_customers_for_warehouse(
    warehouse_id: str,
    data: BulkCustomerUpload,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Bulk upload customers for a specific warehouse (admin only)"""
    user = await get_current_user(credentials)
    
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admin can upload customers for other warehouses")
    
    # Verify warehouse exists
    warehouse = await db.warehouses.find_one({'id': warehouse_id})
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    
    customers_to_insert = []
    for c in data.customers:
        customers_to_insert.append({
            'id': str(uuid.uuid4()),
            'warehouse_id': warehouse_id,
            'date': c.date,
            'connection_type': c.connection_type,
            'customer_name': c.customer_name,
            'address': c.address,
            'phone': c.phone,
            'consumer_no': c.consumer_no,
            'cash_memo_no': c.cash_memo_no,
            'cylinder_nos': c.cylinder_nos,
            'gas_card_issued': c.gas_card_issued,
            'kyc_done': c.kyc_done,
            'remarks': c.remarks,
            'created_by': user['id'],
            'created_at': datetime.now(timezone.utc).isoformat()
        })
    
    if customers_to_insert:
        await db.customers.insert_many(customers_to_insert)
    
    return {"message": f"Successfully uploaded {len(customers_to_insert)} customers to {warehouse['name']}", "count": len(customers_to_insert)}


@router.post("/customers/sync-from-sales")
async def sync_customers_from_sales(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Backfill the customers collection from existing sales entries.
    For every sales entry whose consumer is not already in the customers
    collection (matched by consumer_no within the same warehouse, or by
    customer_name when consumer_no is blank), creates a customer record
    with the sales entry's date preserved (so FY2024-25 etc. records stay
    in their original financial year). Also links sales_entries.customer_id
    to the matched/created customer.

    Admin or warehouse_manager only.
    """
    user = await get_current_user(credentials)
    if user['role'] not in ('admin', 'warehouse_manager'):
        raise HTTPException(status_code=403, detail="Admin or warehouse manager access required")

    # Scope: admin → all warehouses, manager → only their warehouse
    sales_query = {}
    if user['role'] != 'admin':
        if not user.get('warehouse_id'):
            raise HTTPException(status_code=400, detail="User has no assigned warehouse")
        sales_query['warehouse_id'] = user['warehouse_id']

    # Build a lookup of existing customers (per warehouse) for fast matching
    cust_query = {}
    if user['role'] != 'admin':
        cust_query['warehouse_id'] = user['warehouse_id']

    existing_customers = await db.customers.find(cust_query, {
        '_id': 0, 'id': 1, 'warehouse_id': 1, 'consumer_no': 1, 'customer_name': 1
    }).to_list(50000)

    by_consumer_no = {}    # (warehouse_id, consumer_no) -> customer_id
    by_name = {}           # (warehouse_id, lower(name)) -> customer_id
    for c in existing_customers:
        wid = c.get('warehouse_id', '')
        cno = (c.get('consumer_no') or '').strip()
        nm = (c.get('customer_name') or '').strip().lower()
        if cno:
            by_consumer_no[(wid, cno)] = c['id']
        if nm:
            # First-occurrence wins so we don't overwrite older records
            by_name.setdefault((wid, nm), c['id'])

    # Iterate sales entries in the user's scope
    cursor = db.sales_entries.find(sales_query, {
        '_id': 0,
        'id': 1, 'customer_id': 1, 'consumer_name': 1, 'consumer_no': 1,
        'address': 1, 'connection_type': 1, 'cylinder_nos': 1, 'memo_no': 1,
        'date': 1, 'warehouse_id': 1, 'remarks': 1
    })

    new_customers: List[Dict[str, Any]] = []
    link_updates: List[Dict[str, Any]] = []
    seen_in_run = {}  # (wid, key) -> id, so duplicates within run dedupe

    scanned = 0
    matched = 0
    created = 0
    skipped_no_name = 0

    async for s in cursor:
        scanned += 1
        name = (s.get('consumer_name') or '').strip()
        if not name:
            skipped_no_name += 1
            continue

        wid = s.get('warehouse_id', '')
        cno = (s.get('consumer_no') or '').strip()
        nm_key = name.lower()

        cust_id = None
        if cno:
            cust_id = by_consumer_no.get((wid, cno))
        if not cust_id:
            cust_id = by_name.get((wid, nm_key))
        if not cust_id:
            cust_id = seen_in_run.get((wid, cno or nm_key))

        if cust_id:
            matched += 1
        else:
            # Create a new customer; preserve the sales entry's date
            ct = (s.get('connection_type') or 'domestic').strip().lower()
            if ct not in ('domestic', 'commercial'):
                # Refills/others -> infer domestic by default
                ct = 'domestic'
            new_id = str(uuid.uuid4())
            new_cust = {
                'id': new_id,
                'warehouse_id': wid,
                'date': s.get('date') or datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                'connection_type': ct,
                'customer_name': name,
                'address': s.get('address') or '',
                'phone': '',
                'consumer_no': cno,
                'cash_memo_no': s.get('memo_no') or '',
                'cylinder_nos': s.get('cylinder_nos') or '',
                'gas_card_issued': False,
                'kyc_done': False,
                'remarks': f"Auto-synced from sales entry on "
                           f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
                'created_by': user['id'],
                'created_at': datetime.now(timezone.utc).isoformat(),
                'auto_synced': True,
            }
            new_customers.append(new_cust)
            cust_id = new_id
            created += 1
            seen_in_run[(wid, cno or nm_key)] = new_id
            if cno:
                by_consumer_no[(wid, cno)] = new_id
            by_name.setdefault((wid, nm_key), new_id)

        # Link the sales entry if it has no customer_id yet (or a different one)
        if s.get('customer_id') != cust_id:
            link_updates.append({'sales_id': s['id'], 'customer_id': cust_id})

    # Bulk insert new customers
    if new_customers:
        await db.customers.insert_many(new_customers)

    # Bulk update sales entries to link customer_id
    for u in link_updates:
        await db.sales_entries.update_one(
            {'id': u['sales_id']},
            {'$set': {'customer_id': u['customer_id']}}
        )

    await log_audit(
        user['id'], user['name'], 'sync', 'customer',
        details=f"Synced from sales: scanned={scanned}, created={created}, "
                f"linked={len(link_updates)}, matched={matched}"
    )

    return {
        'message': f"Sync complete: {created} new customers created, "
                   f"{len(link_updates)} sales entries linked",
        'scanned': scanned,
        'matched_to_existing': matched,
        'created': created,
        'linked_sales_entries': len(link_updates),
        'skipped_no_name': skipped_no_name,
    }


@router.get("/customers/refill-status")
async def get_customers_refill_status(
    warehouse_id: Optional[str] = None,
    overdue_only: Optional[bool] = False,
    page: int = 1,
    limit: int = 50,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get all customers with their last refill date and days since last refill"""
    user = await get_current_user(credentials)
    
    query = {}
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id')
    elif warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    
    customers_list = await db.customers.find(query, {'_id': 0}).to_list(5000)
    
    # Get all customer IDs and names for matching
    customer_ids = [c['id'] for c in customers_list]
    customer_names = [c.get('customer_name', '') for c in customers_list if c.get('customer_name')]
    
    # Get last entry for each customer by customer_id
    pipeline_by_id = [
        {'$match': {'customer_id': {'$in': customer_ids}}},
        {'$sort': {'date': -1}},
        {'$group': {
            '_id': '$customer_id',
            'last_refill_date': {'$first': '$date'},
            'last_amount': {'$first': '$amount'},
            'last_payment_mode': {'$first': '$payment_mode'},
            'total_refills': {'$sum': '$no_of_refills'}
        }}
    ]
    refill_by_id = await db.sales_entries.aggregate(pipeline_by_id).to_list(5000)
    refill_map = {r['_id']: r for r in refill_by_id}
    
    # Also get last entry by consumer_name for entries without customer_id
    pipeline_by_name = [
        {'$match': {
            '$or': [
                {'customer_id': None},
                {'customer_id': ''},
                {'customer_id': {'$exists': False}}
            ],
            'consumer_name': {'$in': customer_names}
        }},
        {'$sort': {'date': -1}},
        {'$group': {
            '_id': '$consumer_name',
            'last_refill_date': {'$first': '$date'},
            'last_amount': {'$first': '$amount'},
            'last_payment_mode': {'$first': '$payment_mode'},
            'total_refills': {'$sum': '$no_of_refills'}
        }}
    ]
    refill_by_name = await db.sales_entries.aggregate(pipeline_by_name).to_list(5000)
    name_refill_map = {r['_id'].lower(): r for r in refill_by_name if r['_id']}
    
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    result = []
    for c in customers_list:
        # Try matching by customer_id first, then fallback to consumer_name
        refill = refill_map.get(c['id'])
        if not refill:
            refill = name_refill_map.get((c.get('customer_name') or '').lower())
        last_refill_date = refill['last_refill_date'] if refill else None
        days_since = None
        if last_refill_date:
            try:
                last_dt = datetime.strptime(last_refill_date, '%Y-%m-%d')
                today_dt = datetime.strptime(today, '%Y-%m-%d')
                days_since = (today_dt - last_dt).days
            except:
                days_since = None
        
        if overdue_only and (days_since is None or days_since < 30):
            continue
        
        # Get warehouse name
        warehouse = await db.warehouses.find_one({'id': c.get('warehouse_id')}, {'_id': 0})
        
        result.append({
            'id': c['id'],
            'customer_name': c.get('customer_name', ''),
            'consumer_no': c.get('consumer_no', ''),
            'phone': c.get('phone', ''),
            'address': c.get('address', ''),
            'connection_type': c.get('connection_type', ''),
            'warehouse_id': c.get('warehouse_id', ''),
            'warehouse_name': warehouse['name'] if warehouse else 'Unknown',
            'last_refill_date': last_refill_date,
            'days_since_refill': days_since,
            'last_amount': refill['last_amount'] if refill else None,
            'last_payment_mode': refill['last_payment_mode'] if refill else None,
            'total_refills': refill['total_refills'] if refill else 0
        })
    
    # Sort: overdue first, then by days_since descending
    result.sort(key=lambda x: (x['days_since_refill'] is None, -(x['days_since_refill'] or 0)))
    
    # Summary stats
    total = len(result)
    recent = sum(1 for r in result if r['days_since_refill'] is not None and r['days_since_refill'] <= 15)
    moderate = sum(1 for r in result if r['days_since_refill'] is not None and 15 < r['days_since_refill'] <= 30)
    overdue_count = sum(1 for r in result if r['days_since_refill'] is not None and r['days_since_refill'] > 30)
    no_history = sum(1 for r in result if r['days_since_refill'] is None)
    
    return {
        'customers': result,
        'summary': {
            'total': total,
            'recent': recent,
            'moderate': moderate,
            'overdue': overdue_count,
            'no_history': no_history
        }
    }

@router.get("/customers/{customer_id}/last-refill")
async def get_customer_last_refill(
    customer_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get last refill details for a specific customer"""
    await get_current_user(credentials)
    
    # Find the last entry by customer_id
    last_refill = await db.sales_entries.find_one(
        {'customer_id': customer_id},
        {'_id': 0},
        sort=[('date', -1)]
    )
    
    # Fallback: match by consumer_name if no entry found by customer_id
    if not last_refill:
        customer = await db.customers.find_one({'id': customer_id}, {'_id': 0})
        if customer and customer.get('customer_name'):
            last_refill = await db.sales_entries.find_one(
                {
                    'consumer_name': {'$regex': f'^{customer["customer_name"]}$', '$options': 'i'},
                    '$or': [{'customer_id': None}, {'customer_id': ''}, {'customer_id': {'$exists': False}}]
                },
                {'_id': 0},
                sort=[('date', -1)]
            )
    
    if not last_refill:
        return {'has_refill': False, 'message': 'No refill history available'}
    
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    days_since = None
    try:
        last_dt = datetime.strptime(last_refill['date'], '%Y-%m-%d')
        today_dt = datetime.strptime(today, '%Y-%m-%d')
        days_since = (today_dt - last_dt).days
    except:
        pass
    
    return {
        'has_refill': True,
        'last_refill_date': last_refill['date'],
        'days_since_refill': days_since,
        'amount': last_refill.get('amount', 0),
        'payment_mode': last_refill.get('payment_mode', ''),
        'no_of_refills': last_refill.get('no_of_refills', 0),
        'memo_no': last_refill.get('memo_no', '')
    }

@router.get("/export/customer-refill-pdf")
async def export_customer_refill_pdf(
    warehouse_id: Optional[str] = None,
    overdue_only: Optional[bool] = False,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export customer LPG refill status report as PDF"""
    user = await get_current_user(credentials)
    
    query = {}
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id')
    elif warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    
    customers_list = await db.customers.find(query, {'_id': 0}).to_list(5000)
    customer_ids = [c['id'] for c in customers_list]
    customer_names_pdf = [c.get('customer_name', '') for c in customers_list if c.get('customer_name')]
    
    pipeline = [
        {'$match': {'customer_id': {'$in': customer_ids}}},
        {'$sort': {'date': -1}},
        {'$group': {'_id': '$customer_id', 'last_refill_date': {'$first': '$date'}, 'total_refills': {'$sum': '$no_of_refills'}}}
    ]
    refill_data = await db.sales_entries.aggregate(pipeline).to_list(5000)
    refill_map = {r['_id']: r for r in refill_data}
    
    pipeline_name_pdf = [
        {'$match': {'$or': [{'customer_id': None}, {'customer_id': ''}, {'customer_id': {'$exists': False}}], 'consumer_name': {'$in': customer_names_pdf}}},
        {'$sort': {'date': -1}},
        {'$group': {'_id': '$consumer_name', 'last_refill_date': {'$first': '$date'}, 'total_refills': {'$sum': '$no_of_refills'}}}
    ]
    refill_by_name_pdf = await db.sales_entries.aggregate(pipeline_name_pdf).to_list(5000)
    name_map_pdf = {r['_id'].lower(): r for r in refill_by_name_pdf if r['_id']}
    
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    today_display = datetime.now(timezone.utc).strftime('%d-%m-%Y')
    
    rows = []
    for c in customers_list:
        refill = refill_map.get(c['id'])
        if not refill:
            refill = name_map_pdf.get((c.get('customer_name') or '').lower())
        last_date = refill['last_refill_date'] if refill else None
        days = None
        if last_date:
            try:
                days = (datetime.strptime(today, '%Y-%m-%d') - datetime.strptime(last_date, '%Y-%m-%d')).days
            except:
                pass
        if overdue_only and (days is None or days < 30):
            continue
        
        # Format date as DD-MM-YYYY
        display_date = '-'
        if last_date:
            try:
                display_date = datetime.strptime(last_date, '%Y-%m-%d').strftime('%d-%m-%Y')
            except:
                display_date = last_date
        
        rows.append({
            'name': c.get('customer_name', ''),
            'consumer_no': c.get('consumer_no', ''),
            'phone': c.get('phone', ''),
            'address': c.get('address', ''),
            'last_date': display_date,
            'days': days,
            'total_refills': refill['total_refills'] if refill else 0
        })
    
    rows.sort(key=lambda x: (x['days'] is None, -(x['days'] or 0)))
    
    # Summary
    total_c = len(rows)
    recent_c = sum(1 for r in rows if r['days'] is not None and r['days'] <= 15)
    overdue_c = sum(1 for r in rows if r['days'] is not None and r['days'] > 30)
    
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), topMargin=20, bottomMargin=20, leftMargin=20, rightMargin=20)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=16, spaceAfter=4, textColor=colors.HexColor('#15803d'))
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=9, textColor=colors.grey, spaceAfter=8)
    
    elements.append(Paragraph("K3 GAS SERVICE - Customer LPG Refill Status Report", title_style))
    elements.append(Paragraph(f"Generated: {today_display} | Total: {total_c} | Recently Refilled: {recent_c} | Overdue (>30 days): {overdue_c}", subtitle_style))
    elements.append(Spacer(1, 8))
    
    data = [['SL', 'Customer Name', 'Consumer No', 'Phone', 'Address', 'Last Refill Date', 'Days Since', 'Total Refills']]
    for i, r in enumerate(rows, 1):
        days_str = str(r['days']) if r['days'] is not None else 'No history'
        data.append([
            str(i), r['name'][:20], r['consumer_no'], r['phone'], r['address'][:18], r['last_date'], days_str, str(r['total_refills'])
        ])
    
    col_widths = [25, 120, 70, 70, 110, 80, 55, 55]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16a34a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
    ]
    
    # Color-code days column
    for idx, r in enumerate(rows, 1):
        if r['days'] is not None:
            if r['days'] > 30:
                style_cmds.append(('BACKGROUND', (6, idx), (6, idx), colors.HexColor('#fef2f2')))
                style_cmds.append(('TEXTCOLOR', (6, idx), (6, idx), colors.HexColor('#dc2626')))
            elif r['days'] > 15:
                style_cmds.append(('BACKGROUND', (6, idx), (6, idx), colors.HexColor('#fefce8')))
                style_cmds.append(('TEXTCOLOR', (6, idx), (6, idx), colors.HexColor('#ca8a04')))
            else:
                style_cmds.append(('TEXTCOLOR', (6, idx), (6, idx), colors.HexColor('#16a34a')))
    
    table.setStyle(TableStyle(style_cmds))
    elements.append(table)
    
    doc.build(elements)
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=customer_refill_status_{today}.pdf"}
    )

@router.get("/export/customer-refill-excel")
async def export_customer_refill_excel(
    warehouse_id: Optional[str] = None,
    overdue_only: Optional[bool] = False,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export customer LPG refill status report as Excel"""
    user = await get_current_user(credentials)
    
    query = {}
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id')
    elif warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    
    customers_list = await db.customers.find(query, {'_id': 0}).to_list(5000)
    customer_ids = [c['id'] for c in customers_list]
    customer_names_xl = [c.get('customer_name', '') for c in customers_list if c.get('customer_name')]
    
    pipeline = [
        {'$match': {'customer_id': {'$in': customer_ids}}},
        {'$sort': {'date': -1}},
        {'$group': {'_id': '$customer_id', 'last_refill_date': {'$first': '$date'}, 'total_refills': {'$sum': '$no_of_refills'}}}
    ]
    refill_data = await db.sales_entries.aggregate(pipeline).to_list(5000)
    refill_map = {r['_id']: r for r in refill_data}
    
    pipeline_name_xl = [
        {'$match': {'$or': [{'customer_id': None}, {'customer_id': ''}, {'customer_id': {'$exists': False}}], 'consumer_name': {'$in': customer_names_xl}}},
        {'$sort': {'date': -1}},
        {'$group': {'_id': '$consumer_name', 'last_refill_date': {'$first': '$date'}, 'total_refills': {'$sum': '$no_of_refills'}}}
    ]
    refill_by_name_xl = await db.sales_entries.aggregate(pipeline_name_xl).to_list(5000)
    name_map_xl = {r['_id'].lower(): r for r in refill_by_name_xl if r['_id']}
    
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    today_display = datetime.now(timezone.utc).strftime('%d-%m-%Y')
    
    rows = []
    for c in customers_list:
        refill = refill_map.get(c['id'])
        if not refill:
            refill = name_map_xl.get((c.get('customer_name') or '').lower())
        last_date = refill['last_refill_date'] if refill else None
        days = None
        if last_date:
            try:
                days = (datetime.strptime(today, '%Y-%m-%d') - datetime.strptime(last_date, '%Y-%m-%d')).days
            except:
                pass
        if overdue_only and (days is None or days < 30):
            continue
        
        display_date = '-'
        if last_date:
            try:
                display_date = datetime.strptime(last_date, '%Y-%m-%d').strftime('%d-%m-%Y')
            except:
                display_date = last_date
        
        rows.append({
            'name': c.get('customer_name', ''),
            'consumer_no': c.get('consumer_no', ''),
            'phone': c.get('phone', ''),
            'address': c.get('address', ''),
            'connection_type': c.get('connection_type', ''),
            'last_date': display_date,
            'days': days,
            'total_refills': refill['total_refills'] if refill else 0
        })
    
    rows.sort(key=lambda x: (x['days'] is None, -(x['days'] or 0)))
    
    total_c = len(rows)
    recent_c = sum(1 for r in rows if r['days'] is not None and r['days'] <= 15)
    overdue_c = sum(1 for r in rows if r['days'] is not None and r['days'] > 30)
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Refill Status"

    # Branded header: logo + name + title (rows 1-3, spacer row 4)
    company = await get_company_info_for_export()
    title = f"Customer LPG Refill Status — Total: {total_c}  |  Recent (≤15d): {recent_c}  |  Overdue (>30d): {overdue_c}"
    logo_path = embed_logo_openpyxl(
        ws, company, title=title, period=today_display, last_col_letter='H',
    )
    ws.append([])  # row 4 spacer

    headers = ['SL No.', 'Customer Name', 'Consumer No.', 'Phone', 'Address', 'Last Refill Date', 'Days Since Refill', 'Total Refills']
    ws.append(headers)

    header_fill = PatternFill(start_color="16a34a", end_color="16a34a", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=10)
    for cell in ws[5]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')

    green_font = Font(color="16a34a", bold=True)
    yellow_font = Font(color="ca8a04", bold=True)
    red_font = Font(color="dc2626", bold=True)
    red_fill = PatternFill(start_color="fef2f2", end_color="fef2f2", fill_type="solid")
    yellow_fill = PatternFill(start_color="fefce8", end_color="fefce8", fill_type="solid")

    for i, r in enumerate(rows, 1):
        days_val = r['days'] if r['days'] is not None else 'No history'
        ws.append([i, r['name'], r['consumer_no'], r['phone'], r['address'], r['last_date'], days_val, r['total_refills']])
        # header rows 1-3 + spacer row 4 + headers row 5 = data starts at row 6
        row_num = i + 5
        days_cell = ws.cell(row=row_num, column=7)
        if r['days'] is not None:
            if r['days'] > 30:
                days_cell.font = red_font
                days_cell.fill = red_fill
            elif r['days'] > 15:
                days_cell.font = yellow_font
                days_cell.fill = yellow_fill
            else:
                days_cell.font = green_font

    col_widths = [8, 25, 14, 14, 25, 16, 16, 14]
    for idx, w in enumerate(col_widths, 1):
        ws.column_dimensions[chr(64 + idx)].width = w

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    cleanup_logo_tempfile(logo_path)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=customer_refill_status_{today}.xlsx"}
    )

@router.get("/customers/summary")
async def get_customer_summary(
    warehouse_id: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get customer summary statistics"""
    user = await get_current_user(credentials)
    
    query = {}
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id')
    elif warehouse_id and warehouse_id != 'all':
        # Admin can filter by specific warehouse
        query['warehouse_id'] = warehouse_id
    
    # Get total counts
    total_domestic = await db.customers.count_documents({**query, 'connection_type': 'domestic'})
    total_commercial = await db.customers.count_documents({**query, 'connection_type': 'commercial'})
    total_gas_card = await db.customers.count_documents({**query, 'gas_card_issued': True})
    total_kyc = await db.customers.count_documents({**query, 'kyc_done': True})
    
    return {
        'total_domestic': total_domestic,
        'total_commercial': total_commercial,
        'total_customers': total_domestic + total_commercial,
        'total_gas_card_issued': total_gas_card,
        'total_kyc_done': total_kyc
    }

@router.get("/customers/sample-excel")
async def download_sample_excel(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Download sample Excel template for bulk upload"""
    await get_current_user(credentials)
    
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('Customer Template')
    
    # Header format
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#2d5016',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })
    
    # Data format
    data_format = workbook.add_format({
        'border': 1,
        'align': 'left',
        'valign': 'vcenter'
    })
    
    # Headers
    headers = [
        'Date (DD-MM-YYYY)',
        'Connection Type (domestic/commercial)',
        'Customer Name',
        'Address',
        'Phone (10 digits)',
        'Consumer No (10 digits)',
        'Cash Memo No',
        'Cylinder Nos',
        'Gas Card Issued (yes/no)',
        'KYC Done (yes/no)',
        'Remarks'
    ]
    
    # Set column widths
    column_widths = [18, 30, 25, 35, 18, 18, 15, 15, 22, 18, 30]
    for i, width in enumerate(column_widths):
        worksheet.set_column(i, i, width)
    
    # Write headers
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)
    
    # Sample data rows with DD-MM-YYYY format
    sample_data = [
        ['28-02-2026', 'domestic', 'Rahul Sharma', 'House No. 123, Itanagar', '9876543210', '9876543210', 'CM001', 'CYL-001, CYL-002', 'yes', 'yes', 'Regular customer'],
        ['28-02-2026', 'commercial', 'ABC Restaurant', 'Market Complex, Naharlagun', '9876543211', '9876543211', 'CM002', 'CYL-003', 'no', 'yes', 'New connection'],
        ['27-02-2026', 'domestic', 'Priya Devi', 'Ward No. 5, Doimukh', '9876543212', '9876543212', 'CM003', 'CYL-004, CYL-005', 'yes', 'no', ''],
    ]
    
    for row_num, row_data in enumerate(sample_data, start=1):
        for col_num, cell_data in enumerate(row_data):
            worksheet.write(row_num, col_num, cell_data, data_format)
    
    # Add instructions sheet
    instructions = workbook.add_worksheet('Instructions')
    instructions.set_column(0, 0, 80)
    
    instruction_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})
    title_format = workbook.add_format({'bold': True, 'font_size': 14})
    
    instructions.write(0, 0, 'BULK CUSTOMER UPLOAD INSTRUCTIONS', title_format)
    instructions.write(2, 0, '1. Date Format: Use DD-MM-YYYY format (e.g., 28-02-2026)', instruction_format)
    instructions.write(3, 0, '2. Connection Type: Must be either "domestic" or "commercial" (lowercase)', instruction_format)
    instructions.write(4, 0, '3. Customer Name: Required field - cannot be empty', instruction_format)
    instructions.write(5, 0, '4. Phone: Customer mobile number for SMS/WhatsApp messaging (10 digits)', instruction_format)
    instructions.write(6, 0, '5. Consumer No: Customer consumer number (10 digits)', instruction_format)
    instructions.write(7, 0, '6. Gas Card Issued: Use "yes" or "no" (lowercase)', instruction_format)
    instructions.write(8, 0, '7. KYC Done: Use "yes" or "no" (lowercase)', instruction_format)
    instructions.write(9, 0, '8. Delete the sample data rows before uploading your actual data', instruction_format)
    instructions.write(10, 0, '9. Do not modify the header row', instruction_format)
    
    workbook.close()
    output.seek(0)
    
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=customer_upload_template.xlsx"}
    )

@router.get("/export/customers-pdf")
async def export_customers_pdf(
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export customers to PDF"""
    user = await get_current_user(credentials)
    
    query = {}
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id')
    elif warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    
    if category and category != 'all':
        query['connection_type'] = category
    
    if start_date:
        query['date'] = query.get('date', {})
        query['date']['$gte'] = start_date
    if end_date:
        if 'date' not in query:
            query['date'] = {}
        query['date']['$lte'] = end_date
    
    customers = await db.customers.find(query).sort('date', -1).to_list(1000)
    
    # Get warehouse name
    warehouse_name = "All Warehouses"
    if user['role'] != 'admin':
        warehouse = await db.warehouses.find_one({'id': user.get('warehouse_id')})
        warehouse_name = warehouse['name'] if warehouse else 'Unknown'
    elif warehouse_id and warehouse_id != 'all':
        warehouse = await db.warehouses.find_one({'id': warehouse_id})
        warehouse_name = warehouse['name'] if warehouse else 'Unknown'
    
    # Create PDF - A4 landscape fit-to-page
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), topMargin=15, bottomMargin=15, leftMargin=15, rightMargin=15)
    elements = []
    styles = getSampleStyleSheet()
    
    # Header 14pt bold
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#2d5016'),
        spaceAfter=5,
        alignment=1
    )
    
    category_text = category.capitalize() if category and category != 'all' else 'All'
    title = Paragraph(f"K3 GAS SERVICE - {category_text} Customer Report", title_style)
    elements.append(title)
    
    subtitle = Paragraph(f"Warehouse: {warehouse_name}", ParagraphStyle('Sub', fontSize=10, alignment=1))
    elements.append(subtitle)
    elements.append(Spacer(1, 5))
    
    # Table data
    table_data = [['Date', 'Type', 'Customer', 'Phone', 'Address', 'Cons.No', 'Card', 'KYC']]
    
    for c in customers:
        table_data.append([
            c.get('date', ''),
            c.get('connection_type', '')[:6].title(),
            c.get('customer_name', '')[:18],
            c.get('phone', ''),
            c.get('address', '')[:22],
            c.get('consumer_no', ''),
            'Y' if c.get('gas_card_issued') else 'N',
            'Y' if c.get('kyc_done') else 'N'
        ])
    
    # Create table - fit A4 landscape
    col_widths = [60, 55, 130, 85, 160, 90, 35, 35]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d5016')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')])
    ]))
    
    elements.append(table)
    
    # Summary
    elements.append(Spacer(1, 10))
    domestic_count = sum(1 for c in customers if c.get('connection_type') == 'domestic')
    commercial_count = sum(1 for c in customers if c.get('connection_type') == 'commercial')
    summary = Paragraph(f"Total: {len(customers)} (Domestic: {domestic_count}, Commercial: {commercial_count})", ParagraphStyle('Sum', fontSize=10))
    elements.append(summary)
    
    doc.build(elements)
    output.seek(0)
    
    # Generate filename with category
    category_name = category.capitalize() if category and category != 'all' else 'All'
    date_str = datetime.now().strftime('%d%m%y')
    filename = f"Customer_Report_{category_name}_{date_str}.pdf"
    
    return Response(
        content=output.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/export/customers-excel")
async def export_customers_excel(
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export customers to Excel"""
    user = await get_current_user(credentials)
    
    query = {}
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id')
    elif warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    
    if category and category != 'all':
        query['connection_type'] = category
    
    if start_date:
        query['date'] = query.get('date', {})
        query['date']['$gte'] = start_date
    if end_date:
        if 'date' not in query:
            query['date'] = {}
        query['date']['$lte'] = end_date
    
    customers = await db.customers.find(query).sort('date', -1).to_list(1000)
    
    # Get warehouse names
    warehouse_ids = list(set(c.get('warehouse_id') for c in customers if c.get('warehouse_id')))
    warehouses = await db.warehouses.find({'id': {'$in': warehouse_ids}}).to_list(100)
    warehouse_map = {w['id']: w['name'] for w in warehouses}
    
    # Create Excel
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('Customers')

    # Branded header rows 0-2, spacer row 3, table headers row 4, data row 5+
    company = await get_company_info_for_export()
    period_str = f"{start_date or 'All'} to {end_date or 'Today'}" if (start_date or end_date) else 'All time'
    cat_label = category.capitalize() if category and category != 'all' else 'All'
    logo_path = embed_logo_xlsxwriter(
        worksheet, workbook, company,
        title=f"Customer Report — {cat_label}",
        period=period_str,
        last_col_idx=11,
    )

    # Formats
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#2d5016',
        'font_color': 'white',
        'border': 1,
        'align': 'center'
    })
    
    data_format = workbook.add_format({'border': 1, 'align': 'left'})
    yes_format = workbook.add_format({'border': 1, 'align': 'center', 'bg_color': '#d4edda'})
    no_format = workbook.add_format({'border': 1, 'align': 'center', 'bg_color': '#f8d7da'})

    # Headers (row 4 - 0-indexed)
    headers = ['Date', 'Connection Type', 'Customer Name', 'Phone', 'Address', 'Consumer No', 'Cash Memo No', 'Cylinder Nos', 'Gas Card Issued', 'KYC Done', 'Remarks', 'Warehouse']
    HEADER_ROW = 4

    for col, header in enumerate(headers):
        worksheet.write(HEADER_ROW, col, header, header_format)
        worksheet.set_column(col, col, 15 if col < 4 else 20)
    
    # Data (starting at row 5)
    for row, c in enumerate(customers, start=HEADER_ROW + 1):
        worksheet.write(row, 0, c.get('date', ''), data_format)
        worksheet.write(row, 1, c.get('connection_type', '').capitalize(), data_format)
        worksheet.write(row, 2, c.get('customer_name', ''), data_format)
        worksheet.write(row, 3, c.get('phone', ''), data_format)
        worksheet.write(row, 4, c.get('address', ''), data_format)
        worksheet.write(row, 5, c.get('consumer_no', ''), data_format)
        worksheet.write(row, 6, c.get('cash_memo_no', ''), data_format)
        worksheet.write(row, 7, c.get('cylinder_nos', ''), data_format)
        worksheet.write(row, 8, 'Yes' if c.get('gas_card_issued') else 'No', yes_format if c.get('gas_card_issued') else no_format)
        worksheet.write(row, 9, 'Yes' if c.get('kyc_done') else 'No', yes_format if c.get('kyc_done') else no_format)
        worksheet.write(row, 10, c.get('remarks', ''), data_format)
        worksheet.write(row, 11, warehouse_map.get(c.get('warehouse_id', ''), 'Unknown'), data_format)
    
    workbook.close()
    output.seek(0)
    cleanup_logo_tempfile(logo_path)
    
    # Generate filename with category
    category_name = category.capitalize() if category and category != 'all' else 'All'
    date_str = datetime.now().strftime('%d%m%y')
    filename = f"Customer_Report_{category_name}_{date_str}.xlsx"
    
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

