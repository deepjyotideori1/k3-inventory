from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from database import db
from deps import get_current_user, require_admin, security
from helpers import format_inr, _count_cylinders
from models import SalesEntryCreate, SalesEntryUpdate
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from io import BytesIO
import uuid
import json

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import xlsxwriter
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from routes.gst_billing import auto_generate_invoice_from_sale

router = APIRouter()

@router.get("/sales-entries")
async def get_sales_entries(
    warehouse_id: str = None,
    start_date: str = None,
    end_date: str = None,
    payment_mode: str = None,
    connection_type: str = None,
    search: str = None,
    page: int = 1,
    limit: int = 50,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get sales entries with filters"""
    user = await get_current_user(credentials)
    
    query = {}
    
    # Filter by warehouse
    if user['role'] == 'admin':
        if warehouse_id:
            query['warehouse_id'] = warehouse_id
    else:
        query['warehouse_id'] = user.get('warehouse_id')
    
    # Filter by date range
    if start_date:
        query['date'] = query.get('date', {})
        query['date']['$gte'] = start_date
    if end_date:
        if 'date' not in query:
            query['date'] = {}
        query['date']['$lte'] = end_date
    
    # Filter by payment mode
    if payment_mode and payment_mode != 'all':
        query['payment_mode'] = payment_mode
    
    # Filter by connection type
    if connection_type and connection_type != 'all':
        query['connection_type'] = connection_type
    
    # Search - strip extra whitespace, support flexible matching
    if search:
        search = search.strip()
        search = ' '.join(search.split())  # collapse multiple spaces
        # Escape regex special chars for safe search
        import re as re_module
        escaped = re_module.escape(search)
        query['$or'] = [
            {'consumer_name': {'$regex': escaped, '$options': 'i'}},
            {'consumer_no': {'$regex': escaped, '$options': 'i'}},
            {'memo_no': {'$regex': escaped, '$options': 'i'}},
            {'address': {'$regex': escaped, '$options': 'i'}},
            {'remarks': {'$regex': escaped, '$options': 'i'}}
        ]
    
    entries = await db.sales_entries.find(query, {'_id': 0}).sort('date', 1).skip((page - 1) * limit).limit(limit).to_list(limit)
    total_count = await db.sales_entries.count_documents(query)
    
    # Get warehouse names
    warehouse_ids = list(set(e.get('warehouse_id') for e in entries if e.get('warehouse_id')))
    warehouses = await db.warehouses.find({'id': {'$in': warehouse_ids}}, {'_id': 0}).to_list(100)
    warehouse_map = {w['id']: w['name'] for w in warehouses}
    
    # Get user names
    user_ids = list(set(e.get('created_by') for e in entries if e.get('created_by')))
    users = await db.users.find({'id': {'$in': user_ids}}, {'_id': 0, 'password': 0}).to_list(100)
    user_map = {u['id']: u['name'] for u in users}
    
    result = []
    for e in entries:
        entry_data = {
            'id': e['id'],
            'warehouse_id': e.get('warehouse_id', ''),
            'warehouse_name': warehouse_map.get(e.get('warehouse_id', ''), 'Unknown'),
            'date': e['date'],
            'customer_id': e.get('customer_id'),
            'consumer_name': e['consumer_name'],
            'address': e.get('address', ''),
            'consumer_no': e.get('consumer_no', ''),
            'memo_no': e.get('memo_no', ''),
            'amount': e.get('amount', 0),
            'connection_type': e.get('connection_type', 'domestic'),
            'cylinder_nos': e.get('cylinder_nos', ''),
            'payment_mode': e.get('payment_mode', 'cash'),
            'no_of_refills': e.get('no_of_refills', 0),
            'remarks': e.get('remarks', ''),
            'created_by': e.get('created_by', ''),
            'created_by_name': user_map.get(e.get('created_by', ''), 'Unknown'),
            'created_at': e.get('created_at', ''),
            'updated_at': e.get('updated_at')
        }
        
        # Add split payment amounts with backward compat
        cash_amt = e.get('cash_amount', 0) or 0
        online_amt = e.get('online_amount', 0) or 0
        credit_amt = e.get('credit_amount', 0) or 0
        if cash_amt == 0 and online_amt == 0 and credit_amt == 0:
            pm = e.get('payment_mode', 'cash')
            amt = e.get('amount', 0) or 0
            if pm == 'cash': cash_amt = amt
            elif pm == 'online': online_amt = amt
            elif pm == 'pending': credit_amt = amt
        entry_data['cash_amount'] = cash_amt
        entry_data['online_amount'] = online_amt
        entry_data['credit_amount'] = credit_amt
        
        result.append(entry_data)
    
    return {
        'entries': result,
        'total': total_count,
        'page': page,
        'limit': limit,
        'pages': (total_count + limit - 1) // limit
    }

@router.post("/sales-entries")
async def create_sales_entry(
    entry: SalesEntryCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create a new sales entry"""
    user = await get_current_user(credentials)
    
    warehouse_id = user.get('warehouse_id')
    if user['role'] == 'admin':
        raise HTTPException(status_code=400, detail="Admin must use warehouse-specific endpoint")
    
    if not warehouse_id:
        raise HTTPException(status_code=400, detail="User has no assigned warehouse")
    
    # Get warehouse name
    warehouse = await db.warehouses.find_one({'id': warehouse_id}, {'_id': 0})
    warehouse_name = warehouse['name'] if warehouse else 'Unknown'
    
    entry_doc = {
        'id': str(uuid.uuid4()),
        'warehouse_id': warehouse_id,
        'date': entry.date,
        'customer_id': entry.customer_id,
        'consumer_name': entry.consumer_name,
        'address': entry.address,
        'consumer_no': entry.consumer_no,
        'memo_no': entry.memo_no,
        'amount': entry.amount,
        'connection_type': entry.connection_type,
        'cylinder_nos': entry.cylinder_nos,
        'payment_mode': entry.payment_mode,
        'cash_amount': entry.cash_amount,
        'online_amount': entry.online_amount,
        'credit_amount': entry.credit_amount,
        'no_of_refills': entry.no_of_refills,
        'remarks': entry.remarks,
        'created_by': user['id'],
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Normalize payment amounts
    split_total = entry.cash_amount + entry.online_amount + entry.credit_amount
    if split_total > 0:
        entry_doc['amount'] = split_total
        modes_used = sum(1 for a in [entry.cash_amount, entry.online_amount, entry.credit_amount] if a > 0)
        if modes_used > 1:
            entry_doc['payment_mode'] = 'split'
        elif entry.cash_amount > 0:
            entry_doc['payment_mode'] = 'cash'
        elif entry.online_amount > 0:
            entry_doc['payment_mode'] = 'online'
        elif entry.credit_amount > 0:
            entry_doc['payment_mode'] = 'pending'
    else:
        if entry.payment_mode == 'cash':
            entry_doc['cash_amount'] = entry.amount
        elif entry.payment_mode == 'online':
            entry_doc['online_amount'] = entry.amount
        elif entry.payment_mode == 'pending':
            entry_doc['credit_amount'] = entry.amount
    
    await db.sales_entries.insert_one(entry_doc)
    
    # Remove MongoDB's _id before returning (insert_one mutates the dict)
    entry_doc.pop('_id', None)
    
    # Auto-create customer for new connections (not refills)
    is_new_connection = entry.connection_type in ('domestic', 'commercial')
    if is_new_connection and not entry.customer_id:
        new_cust = {
            'id': str(uuid.uuid4()),
            'date': entry.date,
            'customer_name': entry.consumer_name,
            'address': entry.address or '',
            'consumer_no': entry.consumer_no or '',
            'cash_memo_no': entry.memo_no or '',
            'connection_type': 'Domestic' if entry.connection_type == 'domestic' else 'Commercial',
            'category': 'Domestic' if entry.connection_type == 'domestic' else 'Commercial',
            'cylinder_nos': entry.cylinder_nos or '',
            'phone': '',
            'gas_card_issued': False,
            'kyc_done': False,
            'remarks': entry.remarks or '',
            'warehouse_id': warehouse_id,
            'warehouse_name': warehouse_name,
            'created_by': user['id'],
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        await db.customers.insert_one(new_cust)
        new_cust.pop('_id', None)
        # Link the sales entry to the new customer
        await db.sales_entries.update_one({'id': entry_doc['id']}, {'$set': {'customer_id': new_cust['id']}})
        entry_doc['customer_id'] = new_cust['id']
    
    # Auto-generate GST invoice (best-effort, non-blocking)
    entry_doc['warehouse_name'] = warehouse_name
    await auto_generate_invoice_from_sale(entry_doc, 'sales_entry', user)
    
    return {
        **entry_doc,
        'warehouse_name': warehouse_name,
        'created_by_name': user['name']
    }

@router.post("/sales-entries/warehouse/{warehouse_id}")
async def create_sales_entry_for_warehouse(
    warehouse_id: str,
    entry: SalesEntryCreate,
    user: dict = Depends(require_admin)
):
    """Create a sales entry for a specific warehouse (admin only)"""
    warehouse = await db.warehouses.find_one({'id': warehouse_id}, {'_id': 0})
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    
    entry_doc = {
        'id': str(uuid.uuid4()),
        'warehouse_id': warehouse_id,
        'date': entry.date,
        'customer_id': entry.customer_id,
        'consumer_name': entry.consumer_name,
        'address': entry.address,
        'consumer_no': entry.consumer_no,
        'memo_no': entry.memo_no,
        'amount': entry.amount,
        'connection_type': entry.connection_type,
        'cylinder_nos': entry.cylinder_nos,
        'payment_mode': entry.payment_mode,
        'cash_amount': entry.cash_amount,
        'online_amount': entry.online_amount,
        'credit_amount': entry.credit_amount,
        'no_of_refills': entry.no_of_refills,
        'remarks': entry.remarks,
        'created_by': user['id'],
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Normalize payment amounts
    split_total = entry.cash_amount + entry.online_amount + entry.credit_amount
    if split_total > 0:
        entry_doc['amount'] = split_total
        modes_used = sum(1 for a in [entry.cash_amount, entry.online_amount, entry.credit_amount] if a > 0)
        if modes_used > 1:
            entry_doc['payment_mode'] = 'split'
        elif entry.cash_amount > 0:
            entry_doc['payment_mode'] = 'cash'
        elif entry.online_amount > 0:
            entry_doc['payment_mode'] = 'online'
        elif entry.credit_amount > 0:
            entry_doc['payment_mode'] = 'pending'
    else:
        if entry.payment_mode == 'cash':
            entry_doc['cash_amount'] = entry.amount
        elif entry.payment_mode == 'online':
            entry_doc['online_amount'] = entry.amount
        elif entry.payment_mode == 'pending':
            entry_doc['credit_amount'] = entry.amount
    
    await db.sales_entries.insert_one(entry_doc)
    
    # Remove MongoDB's _id before returning (insert_one mutates the dict)
    entry_doc.pop('_id', None)
    
    # Auto-create customer for new connections (not refills)
    is_new_connection = entry.connection_type in ('domestic', 'commercial')
    if is_new_connection and not entry.customer_id:
        new_cust = {
            'id': str(uuid.uuid4()),
            'date': entry.date,
            'customer_name': entry.consumer_name,
            'address': entry.address or '',
            'consumer_no': entry.consumer_no or '',
            'cash_memo_no': entry.memo_no or '',
            'connection_type': 'Domestic' if entry.connection_type == 'domestic' else 'Commercial',
            'category': 'Domestic' if entry.connection_type == 'domestic' else 'Commercial',
            'cylinder_nos': entry.cylinder_nos or '',
            'phone': '',
            'gas_card_issued': False,
            'kyc_done': False,
            'remarks': entry.remarks or '',
            'warehouse_id': warehouse_id,
            'warehouse_name': warehouse['name'],
            'created_by': user['id'],
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        await db.customers.insert_one(new_cust)
        new_cust.pop('_id', None)
        # Link the sales entry to the new customer
        await db.sales_entries.update_one({'id': entry_doc['id']}, {'$set': {'customer_id': new_cust['id']}})
        entry_doc['customer_id'] = new_cust['id']
    
    # Auto-generate GST invoice (best-effort, non-blocking)
    entry_doc['warehouse_name'] = warehouse['name']
    await auto_generate_invoice_from_sale(entry_doc, 'sales_entry', user)
    
    return {
        **entry_doc,
        'warehouse_name': warehouse['name'],
        'created_by_name': user['name']
    }

@router.put("/sales-entries/{entry_id}")
async def update_sales_entry(
    entry_id: str,
    entry: SalesEntryUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update a sales entry"""
    user = await get_current_user(credentials)
    
    existing = await db.sales_entries.find_one({'id': entry_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Sales entry not found")
    
    # Check access - admin can edit any, others can only edit their own warehouse's entries
    if user['role'] != 'admin' and existing.get('warehouse_id') != user.get('warehouse_id'):
        raise HTTPException(status_code=403, detail="Access denied")
    
    update_data = {k: v for k, v in entry.dict().items() if v is not None}
    update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
    
    # Normalize split amounts on update
    cash_a = update_data.get('cash_amount', existing.get('cash_amount', 0)) or 0
    online_a = update_data.get('online_amount', existing.get('online_amount', 0)) or 0
    credit_a = update_data.get('credit_amount', existing.get('credit_amount', 0)) or 0
    split_total = cash_a + online_a + credit_a
    if split_total > 0:
        update_data['amount'] = split_total
        modes_used = sum(1 for a in [cash_a, online_a, credit_a] if a > 0)
        if modes_used > 1:
            update_data['payment_mode'] = 'split'
        elif cash_a > 0:
            update_data['payment_mode'] = 'cash'
        elif online_a > 0:
            update_data['payment_mode'] = 'online'
        elif credit_a > 0:
            update_data['payment_mode'] = 'pending'
    
    await db.sales_entries.update_one({'id': entry_id}, {'$set': update_data})
    
    updated = await db.sales_entries.find_one({'id': entry_id}, {'_id': 0})
    warehouse = await db.warehouses.find_one({'id': updated.get('warehouse_id')}, {'_id': 0})
    
    return {
        **updated,
        'warehouse_name': warehouse['name'] if warehouse else 'Unknown'
    }

@router.delete("/sales-entries/{entry_id}")
async def delete_sales_entry(
    entry_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Delete a sales entry"""
    user = await get_current_user(credentials)
    
    existing = await db.sales_entries.find_one({'id': entry_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Sales entry not found")
    
    # Check access
    if user['role'] != 'admin' and existing.get('warehouse_id') != user.get('warehouse_id'):
        raise HTTPException(status_code=403, detail="Access denied")
    
    await db.sales_entries.delete_one({'id': entry_id})
    return {"message": "Sales entry deleted successfully"}

@router.get("/sales-entries/summary")
async def get_sales_summary(
    warehouse_id: str = None,
    start_date: str = None,
    end_date: str = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get sales summary with totals"""
    user = await get_current_user(credentials)
    
    match_stage = {}
    
    if user['role'] == 'admin':
        if warehouse_id:
            match_stage['warehouse_id'] = warehouse_id
    else:
        match_stage['warehouse_id'] = user.get('warehouse_id')
    
    if start_date:
        match_stage['date'] = match_stage.get('date', {})
        match_stage['date']['$gte'] = start_date
    if end_date:
        if 'date' not in match_stage:
            match_stage['date'] = {}
        match_stage['date']['$lte'] = end_date
    
    # Calculate summary using per-entry split amounts for accuracy
    all_entries = await db.sales_entries.find(match_stage, {'_id': 0, 'connection_type': 1, 'cylinder_nos': 1, 'no_of_refills': 1, 'payment_mode': 1, 'amount': 1, 'cash_amount': 1, 'online_amount': 1, 'credit_amount': 1}).to_list(5000)
    
    def get_new_conn_cylinders(entry):
        cn = _count_cylinders(entry.get('cylinder_nos', ''))
        if cn > 0: return cn
        nr = int(entry.get('no_of_refills', 0) or 0)
        return nr if nr > 0 else 1
    
    def get_refill_cylinders(entry):
        return int(entry.get('no_of_refills', 0) or 0)
    
    # Calculate per-category totals
    categories = {
        'domestic_new_cyl': 0, 'commercial_new_cyl': 0,
        'domestic_refill_cyl': 0, 'commercial_refill_cyl': 0,
        'domestic_new_count': 0, 'commercial_new_count': 0,
        'domestic_refill_count': 0, 'commercial_refill_count': 0
    }
    
    # Calculate payment mode totals from split amounts
    total_cash = 0
    total_online = 0
    total_credit = 0
    total_amount = 0
    entry_count = 0
    total_refill_cyl = 0
    total_new_cyl = 0
    
    for e in all_entries:
        ct = e.get('connection_type', '')
        amt = e.get('amount', 0) or 0
        cash_a = e.get('cash_amount', 0) or 0
        online_a = e.get('online_amount', 0) or 0
        credit_a = e.get('credit_amount', 0) or 0
        
        # Backward compat: if no split amounts, derive from payment_mode
        if cash_a == 0 and online_a == 0 and credit_a == 0:
            pm = e.get('payment_mode', 'cash')
            if pm == 'cash': cash_a = amt
            elif pm == 'online': online_a = amt
            elif pm == 'pending': credit_a = amt
        
        total_cash += cash_a
        total_online += online_a
        total_credit += credit_a
        total_amount += amt
        entry_count += 1
        
        if ct == 'domestic':
            categories['domestic_new_count'] += 1
            cyl = get_new_conn_cylinders(e)
            categories['domestic_new_cyl'] += cyl
            total_new_cyl += cyl
        elif ct == 'commercial':
            categories['commercial_new_count'] += 1
            cyl = get_new_conn_cylinders(e)
            categories['commercial_new_cyl'] += cyl
            total_new_cyl += cyl
        elif ct == 'domestic_refill':
            categories['domestic_refill_count'] += 1
            cyl = get_refill_cylinders(e)
            categories['domestic_refill_cyl'] += cyl
            total_refill_cyl += cyl
        elif ct == 'commercial_refill':
            categories['commercial_refill_count'] += 1
            cyl = get_refill_cylinders(e)
            categories['commercial_refill_cyl'] += cyl
            total_refill_cyl += cyl
    
    summary = {
        'cash': {'amount': total_cash, 'count': sum(1 for e in all_entries if (e.get('cash_amount', 0) or 0) > 0 or (e.get('cash_amount', 0) == 0 and e.get('online_amount', 0) == 0 and e.get('credit_amount', 0) == 0 and e.get('payment_mode') == 'cash'))},
        'online': {'amount': total_online, 'count': sum(1 for e in all_entries if (e.get('online_amount', 0) or 0) > 0 or (e.get('cash_amount', 0) == 0 and e.get('online_amount', 0) == 0 and e.get('credit_amount', 0) == 0 and e.get('payment_mode') == 'online'))},
        'pending': {'amount': total_credit, 'count': sum(1 for e in all_entries if (e.get('credit_amount', 0) or 0) > 0 or (e.get('cash_amount', 0) == 0 and e.get('online_amount', 0) == 0 and e.get('credit_amount', 0) == 0 and e.get('payment_mode') == 'pending'))},
        'total': {
            'amount': total_amount,
            'count': entry_count,
            'refills': total_refill_cyl,
            'cylinders': total_new_cyl + total_refill_cyl,
            'new_connections': categories['domestic_new_count'] + categories['commercial_new_count'],
            'new_connection_cylinders': total_new_cyl,
            'refill_cylinders': total_refill_cyl
        },
        'categories': categories
    }
    
    return summary

@router.get("/sales-entries/frequent-customers")
async def get_frequent_customers(
    limit: int = 10,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get frequently refilled customers for quick refill feature"""
    user = await get_current_user(credentials)
    
    # Build match stage based on user role
    match_stage = {}
    if user['role'] != 'admin':
        match_stage['warehouse_id'] = user.get('warehouse_id')
    
    # Only include refill entries
    match_stage['connection_type'] = {'$in': ['domestic_refill', 'commercial_refill']}
    
    # Aggregate to find customers with most refills
    pipeline = [
        {'$match': match_stage},
        {'$group': {
            '_id': {
                'consumer_name': '$consumer_name',
                'consumer_no': '$consumer_no',
                'address': '$address',
                'warehouse_id': '$warehouse_id'
            },
            'total_refills': {'$sum': {'$ifNull': ['$no_of_refills', 1]}},
            'total_entries': {'$sum': 1},
            'last_refill_date': {'$max': '$date'},
            'avg_amount': {'$avg': '$amount'},
            'connection_type': {'$last': '$connection_type'},
            'memo_no': {'$last': '$memo_no'}
        }},
        {'$sort': {'total_refills': -1, 'last_refill_date': -1}},
        {'$limit': limit}
    ]
    
    results = await db.sales_entries.aggregate(pipeline).to_list(limit)
    
    # Get warehouse names
    warehouse_ids = list(set([r['_id'].get('warehouse_id') for r in results if r['_id'].get('warehouse_id')]))
    warehouses = {}
    if warehouse_ids:
        warehouse_docs = await db.warehouses.find({'id': {'$in': warehouse_ids}}, {'_id': 0}).to_list(100)
        warehouses = {w['id']: w['name'] for w in warehouse_docs}
    
    # Format response
    frequent_customers = []
    for r in results:
        customer_data = r['_id']
        frequent_customers.append({
            'consumer_name': customer_data.get('consumer_name', ''),
            'consumer_no': customer_data.get('consumer_no', ''),
            'address': customer_data.get('address', ''),
            'warehouse_id': customer_data.get('warehouse_id', ''),
            'warehouse_name': warehouses.get(customer_data.get('warehouse_id', ''), 'Unknown'),
            'total_refills': r.get('total_refills', 0),
            'total_entries': r.get('total_entries', 0),
            'last_refill_date': r.get('last_refill_date', ''),
            'avg_amount': round(r.get('avg_amount', 0), 2),
            'connection_type': r.get('connection_type', 'domestic_refill'),
            'memo_no': r.get('memo_no', '')
        })
    
    return frequent_customers

@router.get("/export/sales-pdf")
async def export_sales_pdf(
    warehouse_id: str = None,
    start_date: str = None,
    end_date: str = None,
    payment_mode: str = None,
    connection_type: str = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export sales entries to PDF - A4 fit-to-page"""
    user = await get_current_user(credentials)
    
    query = {}
    
    if user['role'] == 'admin':
        if warehouse_id:
            query['warehouse_id'] = warehouse_id
    else:
        query['warehouse_id'] = user.get('warehouse_id')
    
    if start_date:
        query['date'] = query.get('date', {})
        query['date']['$gte'] = start_date
    if end_date:
        if 'date' not in query:
            query['date'] = {}
        query['date']['$lte'] = end_date
    
    if payment_mode and payment_mode != 'all':
        query['payment_mode'] = payment_mode
    
    if connection_type and connection_type != 'all':
        query['connection_type'] = connection_type
    
    entries = await db.sales_entries.find(query, {'_id': 0}).sort('date', 1).to_list(5000)
    
    # Also fetch accessory sales with same filters
    acc_query = {}
    if query.get('warehouse_id'):
        acc_query['warehouse_id'] = query['warehouse_id']
    if start_date:
        acc_query['date'] = acc_query.get('date', {})
        acc_query['date']['$gte'] = start_date
    if end_date:
        if 'date' not in acc_query:
            acc_query['date'] = {}
        acc_query['date']['$lte'] = end_date
    if payment_mode and payment_mode != 'all':
        acc_query['payment_mode'] = payment_mode
    
    acc_sales = []
    if not connection_type or connection_type == 'all':
        acc_sales = await db.accessory_sales.find(acc_query, {'_id': 0}).sort('date', 1).to_list(5000)
    
    warehouse_name = "All Warehouses"
    if query.get('warehouse_id'):
        warehouse = await db.warehouses.find_one({'id': query['warehouse_id']}, {'_id': 0})
        warehouse_name = warehouse['name'] if warehouse else 'Unknown'
    
    # Create PDF - A4 landscape fit-to-page
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=15, bottomMargin=15, leftMargin=15, rightMargin=15)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title - Header 14pt bold
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=14, alignment=1, textColor=colors.HexColor('#15803d'))
    elements.append(Paragraph(f"K3 GAS SERVICE - Sales Report - {warehouse_name}", title_style))
    
    date_range = ""
    if start_date and end_date:
        date_range = f"Period: {start_date} to {end_date}"
    elif start_date:
        date_range = f"From: {start_date}"
    elif end_date:
        date_range = f"Until: {end_date}"
    
    if date_range:
        elements.append(Paragraph(date_range, ParagraphStyle('DateRange', fontSize=10, alignment=1)))
    
    elements.append(Spacer(1, 5))
    
    # Table data - include Memo No, Cylinder Nos and Refills
    data = [['SL', 'Date', 'Consumer', 'Address', 'Cons.No', 'Memo No', 'Type', 'Amount', 'Cash', 'Online', 'Credit', 'New Cyl', 'Refill Cyl']]
    
    total_amount = 0
    total_new_cyl = 0
    total_refill_cyl = 0
    dom_new_cyl = 0
    com_new_cyl = 0
    dom_refill_cyl = 0
    com_refill_cyl = 0
    
    def _get_new_cyl(entry):
        cn = _count_cylinders(entry.get('cylinder_nos', ''))
        if cn > 0: return cn
        nr = int(entry.get('no_of_refills', 0) or 0)
        return nr if nr > 0 else 1
    
    for i, e in enumerate(entries, 1):
        conn_type = e.get('connection_type', 'domestic')
        is_refill = 'refill' in conn_type.lower()
        cylinder_nos = e.get('cylinder_nos', '')
        
        # Calculate cylinder count per entry
        if is_refill:
            cyl = int(e.get('no_of_refills', 0) or 0)
            total_refill_cyl += cyl
            if conn_type == 'domestic_refill': dom_refill_cyl += cyl
            else: com_refill_cyl += cyl
        else:
            cyl = _get_new_cyl(e)
            total_new_cyl += cyl
            if conn_type == 'domestic': dom_new_cyl += cyl
            else: com_new_cyl += cyl
        
        # Get split amounts with backward compat
        cash_a = e.get('cash_amount', 0) or 0
        online_a = e.get('online_amount', 0) or 0
        credit_a = e.get('credit_amount', 0) or 0
        if cash_a == 0 and online_a == 0 and credit_a == 0:
            pm = e.get('payment_mode', 'cash')
            amt_val = e.get('amount', 0) or 0
            if pm == 'cash': cash_a = amt_val
            elif pm == 'online': online_a = amt_val
            elif pm == 'pending': credit_a = amt_val
        
        data.append([
            str(i),
            e['date'],
            e['consumer_name'][:16] if len(e.get('consumer_name', '')) > 16 else e.get('consumer_name', ''),
            e.get('address', '')[:14] if len(e.get('address', '')) > 14 else e.get('address', ''),
            e.get('consumer_no', ''),
            e.get('memo_no', ''),
            conn_type[:8].replace('_', ' ').title(),
            format_inr(e.get('amount', 0)),
            format_inr(cash_a) if cash_a > 0 else '-',
            format_inr(online_a) if online_a > 0 else '-',
            format_inr(credit_a) if credit_a > 0 else '-',
            str(cyl) if not is_refill else '-',
            str(cyl) if is_refill else '-'
        ])
        total_amount += e.get('amount', 0)
    
    # Calculate payment mode totals for PDF
    pdf_cash_total = sum(e.get('cash_amount', 0) or (e.get('amount', 0) if e.get('payment_mode') == 'cash' and not e.get('cash_amount') else 0) for e in entries)
    pdf_online_total = sum(e.get('online_amount', 0) or (e.get('amount', 0) if e.get('payment_mode') == 'online' and not e.get('online_amount') else 0) for e in entries)
    pdf_credit_total = sum(e.get('credit_amount', 0) or (e.get('amount', 0) if e.get('payment_mode') == 'pending' and not e.get('credit_amount') else 0) for e in entries)
    
    # Add cylinder total row
    data.append(['', '', '', '', '', '', 'CYL TOTAL:', format_inr(total_amount),
                 format_inr(pdf_cash_total), format_inr(pdf_online_total), format_inr(pdf_credit_total),
                 str(total_new_cyl), str(total_refill_cyl)])
    
    # Add accessory sales section
    acc_total_amount = 0
    acc_cash_total = 0
    acc_online_total = 0
    acc_credit_total = 0
    if acc_sales:
        data.append(['', '', '', '', '', '', '--- ACCESSORY SALES ---', '', '', '', '', '', ''])
        for j, s in enumerate(acc_sales, 1):
            items_desc = ', '.join([f"{i.get('accessory_name', '')} x{i.get('quantity', 0)}" for i in s.get('items', [])])
            amt = s.get('grand_total', 0)
            acc_pm = s.get('payment_mode', 'cash')
            acc_c = amt if acc_pm == 'cash' else 0
            acc_o = amt if acc_pm == 'online' else 0
            acc_cr = amt if acc_pm == 'pending' else 0
            acc_cash_total += acc_c
            acc_online_total += acc_o
            acc_credit_total += acc_cr
            data.append([
                str(len(entries) + j),
                s.get('date', ''),
                (s.get('customer_name', '')[:16] if len(s.get('customer_name', '')) > 16 else s.get('customer_name', '')),
                (s.get('customer_address', '')[:14] if len(s.get('customer_address', '')) > 14 else s.get('customer_address', '')),
                s.get('customer_phone', ''),
                s.get('memo_no', ''),
                'Accessory',
                format_inr(amt),
                format_inr(acc_c) if acc_c > 0 else '-',
                format_inr(acc_o) if acc_o > 0 else '-',
                format_inr(acc_cr) if acc_cr > 0 else '-',
                '-',
                '-'
            ])
            acc_total_amount += amt
        data.append(['', '', '', '', '', '', 'ACC TOTAL:', format_inr(acc_total_amount),
                     format_inr(acc_cash_total), format_inr(acc_online_total), format_inr(acc_credit_total), '', ''])
    
    # Grand total row
    grand_total = total_amount + acc_total_amount
    grand_cash = pdf_cash_total + acc_cash_total
    grand_online = pdf_online_total + acc_online_total
    grand_credit = pdf_credit_total + acc_credit_total
    data.append(['', '', '', '', '', '', 'GRAND TOTAL:', format_inr(grand_total), 
                 format_inr(grand_cash), format_inr(grand_online), format_inr(grand_credit),
                 str(total_new_cyl), str(total_refill_cyl)])
    
    # Add category breakdown row
    data.append(['', '', 'Dom New:', str(dom_new_cyl), 'Com New:', str(com_new_cyl),
                 'Dom Refill:', str(dom_refill_cyl), 'Com Refill:', str(com_refill_cyl), '', '', '', '', ''])
    
    # Create table - fit A4 landscape (13 columns with Cash/Online/Credit)
    col_widths = [18, 42, 62, 52, 42, 36, 40, 44, 38, 38, 38, 32, 32]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    
    # Determine style rows
    last_row = len(data) - 1
    style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16a34a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BACKGROUND', (0, last_row), (-1, last_row), colors.HexColor('#ede9fe')),
        ('FONTNAME', (0, last_row), (-1, last_row), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8fafc')])
    ]
    
    # Style the cylinder total and accessory section rows
    cyl_total_row = len(entries) + 1
    style_commands.append(('BACKGROUND', (0, cyl_total_row), (-1, cyl_total_row), colors.HexColor('#f0fdf4')))
    style_commands.append(('FONTNAME', (0, cyl_total_row), (-1, cyl_total_row), 'Helvetica-Bold'))
    
    if acc_sales:
        acc_header_row = cyl_total_row + 1
        style_commands.append(('BACKGROUND', (0, acc_header_row), (-1, acc_header_row), colors.HexColor('#fff7ed')))
        style_commands.append(('FONTNAME', (0, acc_header_row), (-1, acc_header_row), 'Helvetica-Bold'))
        acc_total_row = last_row - 1
        style_commands.append(('BACKGROUND', (0, acc_total_row), (-1, acc_total_row), colors.HexColor('#fff7ed')))
        style_commands.append(('FONTNAME', (0, acc_total_row), (-1, acc_total_row), 'Helvetica-Bold'))
    
    table.setStyle(TableStyle(style_commands))
    
    elements.append(table)
    doc.build(elements)
    
    date_str = datetime.now().strftime('%d%m%y')
    filename = f"Sales_Report_{warehouse_name.replace(' ', '_')}_{date_str}.pdf"
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/export/sales-excel")
async def export_sales_excel(
    warehouse_id: str = None,
    start_date: str = None,
    end_date: str = None,
    payment_mode: str = None,
    connection_type: str = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export sales entries to Excel"""
    user = await get_current_user(credentials)
    
    query = {}
    
    if user['role'] == 'admin':
        if warehouse_id:
            query['warehouse_id'] = warehouse_id
    else:
        query['warehouse_id'] = user.get('warehouse_id')
    
    if start_date:
        query['date'] = query.get('date', {})
        query['date']['$gte'] = start_date
    if end_date:
        if 'date' not in query:
            query['date'] = {}
        query['date']['$lte'] = end_date
    
    if payment_mode and payment_mode != 'all':
        query['payment_mode'] = payment_mode
    
    if connection_type and connection_type != 'all':
        query['connection_type'] = connection_type
    
    entries = await db.sales_entries.find(query, {'_id': 0}).sort('date', 1).to_list(5000)
    
    # Also fetch accessory sales with same filters
    acc_query_excel = {}
    if query.get('warehouse_id'):
        acc_query_excel['warehouse_id'] = query['warehouse_id']
    if start_date:
        acc_query_excel['date'] = acc_query_excel.get('date', {})
        acc_query_excel['date']['$gte'] = start_date
    if end_date:
        if 'date' not in acc_query_excel:
            acc_query_excel['date'] = {}
        acc_query_excel['date']['$lte'] = end_date
    if payment_mode and payment_mode != 'all':
        acc_query_excel['payment_mode'] = payment_mode
    
    acc_sales_excel = []
    if not connection_type or connection_type == 'all':
        acc_sales_excel = await db.accessory_sales.find(acc_query_excel, {'_id': 0}).sort('date', 1).to_list(5000)
    
    # Get warehouse name
    warehouse_name = "All_Warehouses"
    if query.get('warehouse_id'):
        warehouse = await db.warehouses.find_one({'id': query['warehouse_id']}, {'_id': 0})
        warehouse_name = warehouse['name'].replace(' ', '_') if warehouse else 'Unknown'
    
    # Create Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Sales Data"
    
    # Headers with clear form heads - include Memo No, Cylinder Nos and Refills
    headers = ['SL No.', 'Date', 'Consumer Name', 'Address', 'Consumer No.', 'Memo No.', 'Type', 'Amount (Rs.)', 'Cash (Rs.)', 'Online (Rs.)', 'Credit (Rs.)', 'New Conn Cyl', 'Refill Cyl', 'Remarks']
    ws.append(headers)
    
    # Style headers
    header_fill = PatternFill(start_color="16a34a", end_color="16a34a", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')
    
    total_amount = 0
    total_new_cyl = 0
    total_refill_cyl = 0
    dom_new_cyl = 0
    com_new_cyl = 0
    dom_refill_cyl = 0
    com_refill_cyl = 0
    
    def _get_new_cyl_excel(entry):
        cn = _count_cylinders(entry.get('cylinder_nos', ''))
        if cn > 0: return cn
        nr = int(entry.get('no_of_refills', 0) or 0)
        return nr if nr > 0 else 1
    
    for i, e in enumerate(entries, 1):
        conn_type = e.get('connection_type', 'domestic')
        is_refill = 'refill' in conn_type.lower()
        
        if is_refill:
            cyl = int(e.get('no_of_refills', 0) or 0)
            total_refill_cyl += cyl
            if conn_type == 'domestic_refill': dom_refill_cyl += cyl
            else: com_refill_cyl += cyl
        else:
            cyl = _get_new_cyl_excel(e)
            total_new_cyl += cyl
            if conn_type == 'domestic': dom_new_cyl += cyl
            else: com_new_cyl += cyl
        
        # Get split amounts with backward compat
        cash_a = e.get('cash_amount', 0) or 0
        online_a = e.get('online_amount', 0) or 0
        credit_a = e.get('credit_amount', 0) or 0
        if cash_a == 0 and online_a == 0 and credit_a == 0:
            pm = e.get('payment_mode', 'cash')
            amt_val = e.get('amount', 0) or 0
            if pm == 'cash': cash_a = amt_val
            elif pm == 'online': online_a = amt_val
            elif pm == 'pending': credit_a = amt_val
        
        ws.append([
            i,
            e['date'],
            e.get('consumer_name', ''),
            e.get('address', ''),
            e.get('consumer_no', ''),
            e.get('memo_no', ''),
            conn_type.replace('_', ' ').title(),
            format_inr(e.get('amount', 0)),
            format_inr(cash_a) if cash_a > 0 else '-',
            format_inr(online_a) if online_a > 0 else '-',
            format_inr(credit_a) if credit_a > 0 else '-',
            cyl if not is_refill else '-',
            cyl if is_refill else '-',
            e.get('remarks', '')
        ])
        total_amount += e.get('amount', 0)
    
    # Add cylinder total row
    cyl_total_row = len(entries) + 2
    # Calculate cash/online/credit totals for cylinder entries
    excel_cash_total = sum(
        (e.get('cash_amount', 0) or 0) or (e.get('amount', 0) if e.get('payment_mode') == 'cash' and not e.get('cash_amount') else 0)
        for e in entries
    )
    excel_online_total = sum(
        (e.get('online_amount', 0) or 0) or (e.get('amount', 0) if e.get('payment_mode') == 'online' and not e.get('online_amount') else 0)
        for e in entries
    )
    excel_credit_total = sum(
        (e.get('credit_amount', 0) or 0) or (e.get('amount', 0) if e.get('payment_mode') == 'pending' and not e.get('credit_amount') else 0)
        for e in entries
    )
    ws.append(['', '', '', '', '', '', 'CYL TOTAL:', format_inr(total_amount),
               format_inr(excel_cash_total), format_inr(excel_online_total), format_inr(excel_credit_total),
               total_new_cyl, total_refill_cyl, ''])
    
    # Style cylinder total row
    total_fill = PatternFill(start_color="f0fdf4", end_color="f0fdf4", fill_type="solid")
    total_font = Font(bold=True)
    for cell in ws[cyl_total_row]:
        cell.fill = total_fill
        cell.font = total_font
    
    # Add accessory sales section
    acc_total_amount_excel = 0
    acc_cash_total_excel = 0
    acc_online_total_excel = 0
    acc_credit_total_excel = 0
    if acc_sales_excel:
        # Section header
        acc_header_row_num = cyl_total_row + 1
        ws.append(['', '', '', '', '', '', '--- ACCESSORY SALES ---', '', '', '', '', '', '', ''])
        acc_header_fill = PatternFill(start_color="fff7ed", end_color="fff7ed", fill_type="solid")
        for cell in ws[acc_header_row_num]:
            cell.fill = acc_header_fill
            cell.font = Font(bold=True)
        
        for j, s in enumerate(acc_sales_excel, 1):
            items_desc = ', '.join([f"{i.get('accessory_name', '')} x{i.get('quantity', 0)}" for i in s.get('items', [])])
            amt = s.get('grand_total', 0)
            acc_pm = s.get('payment_mode', 'cash')
            acc_c = amt if acc_pm == 'cash' else 0
            acc_o = amt if acc_pm == 'online' else 0
            acc_cr = amt if acc_pm == 'pending' else 0
            acc_cash_total_excel += acc_c
            acc_online_total_excel += acc_o
            acc_credit_total_excel += acc_cr
            ws.append([
                len(entries) + j,
                s.get('date', ''),
                s.get('customer_name', ''),
                s.get('customer_address', ''),
                s.get('customer_phone', ''),
                s.get('memo_no', ''),
                'Accessory',
                format_inr(amt),
                format_inr(acc_c) if acc_c > 0 else '-',
                format_inr(acc_o) if acc_o > 0 else '-',
                format_inr(acc_cr) if acc_cr > 0 else '-',
                '-',
                '-',
                items_desc
            ])
            acc_total_amount_excel += amt
        
        # Accessory total row
        acc_total_row_num = acc_header_row_num + len(acc_sales_excel) + 1
        ws.append(['', '', '', '', '', '', 'ACC TOTAL:', format_inr(acc_total_amount_excel),
                   format_inr(acc_cash_total_excel), format_inr(acc_online_total_excel), format_inr(acc_credit_total_excel),
                   '', '', ''])
        for cell in ws[acc_total_row_num]:
            cell.fill = acc_header_fill
            cell.font = Font(bold=True)
    
    # Grand total row
    grand_total_row_num = ws.max_row + 1
    grand_total_excel = total_amount + acc_total_amount_excel
    grand_cash_excel = excel_cash_total + acc_cash_total_excel
    grand_online_excel = excel_online_total + acc_online_total_excel
    grand_credit_excel = excel_credit_total + acc_credit_total_excel
    ws.append(['', '', '', '', '', '', 'GRAND TOTAL:', format_inr(grand_total_excel),
               format_inr(grand_cash_excel), format_inr(grand_online_excel), format_inr(grand_credit_excel),
               total_new_cyl, total_refill_cyl, ''])
    grand_fill = PatternFill(start_color="ede9fe", end_color="ede9fe", fill_type="solid")
    for cell in ws[grand_total_row_num]:
        cell.fill = grand_fill
        cell.font = Font(bold=True)
    
    # Category breakdown row
    cat_row = ws.max_row + 1
    ws.append(['', '', 'Dom New Cyl:', dom_new_cyl, 'Com New Cyl:', com_new_cyl,
               'Dom Refill Cyl:', dom_refill_cyl, 'Com Refill Cyl:', com_refill_cyl, '', '', '', ''])
    cat_fill = PatternFill(start_color="e8f5e9", end_color="e8f5e9", fill_type="solid")
    for cell in ws[cat_row]:
        cell.fill = cat_fill
        cell.font = Font(bold=True)
    
    # Adjust column widths
    column_widths = [8, 12, 25, 18, 14, 12, 14, 14, 12, 12, 12, 12, 12, 18]
    for i, width in enumerate(column_widths, 1):
        col_letter = chr(64 + i) if i <= 26 else chr(64 + (i - 1) // 26) + chr(65 + (i - 1) % 26)
        ws.column_dimensions[col_letter].width = width
    
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    date_str = datetime.now().strftime('%d%m%y')
    filename = f"Sales_Report_{warehouse_name}_{date_str}.xlsx"
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ============ SALES SUMMARY REPORTS ============

@router.get("/export/sales-summary-pdf")
async def export_sales_summary_pdf(
    warehouse_id: str = None,
    start_date: str = None,
    end_date: str = None,
    group_by: str = "daily",  # daily, weekly, monthly
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export sales summary report to PDF with period-based totals"""
    user = await get_current_user(credentials)
    
    query = {}
    
    if user['role'] == 'admin':
        if warehouse_id:
            query['warehouse_id'] = warehouse_id
    else:
        query['warehouse_id'] = user.get('warehouse_id')
    
    if start_date:
        query['date'] = query.get('date', {})
        query['date']['$gte'] = start_date
    if end_date:
        if 'date' not in query:
            query['date'] = {}
        query['date']['$lte'] = end_date
    
    entries = await db.sales_entries.find(query, {'_id': 0}).sort('date', 1).to_list(10000)
    
    # Get warehouse name
    warehouse_name = "All Warehouses"
    if query.get('warehouse_id'):
        warehouse = await db.warehouses.find_one({'id': query['warehouse_id']}, {'_id': 0})
        warehouse_name = warehouse['name'] if warehouse else 'Unknown'
    
    # Group entries by period
    from collections import defaultdict
    from datetime import datetime as dt
    
    summary_data = defaultdict(lambda: {
        'cash_amount': 0, 'cash_entries': 0,
        'online_amount': 0, 'online_entries': 0,
        'pending_amount': 0, 'pending_entries': 0,
        'total_amount': 0, 'total_entries': 0, 'total_refills': 0,
        'domestic_new': 0, 'domestic_refill': 0,
        'commercial_new': 0, 'commercial_refill': 0
    })
    
    for entry in entries:
        entry_date = entry.get('date', '')
        if not entry_date:
            continue
            
        try:
            date_obj = dt.strptime(entry_date, '%Y-%m-%d')
        except:
            continue
        
        # Determine period key based on group_by
        if group_by == 'daily':
            period_key = entry_date
        elif group_by == 'weekly':
            # Get ISO week number
            week_num = date_obj.isocalendar()[1]
            year = date_obj.year
            period_key = f"{year}-W{week_num:02d}"
        elif group_by == 'monthly':
            period_key = date_obj.strftime('%Y-%m')
        else:
            period_key = entry_date
        
        amount = entry.get('amount', 0) or 0
        refills = entry.get('no_of_refills', 0) or 0
        payment_mode = entry.get('payment_mode', 'cash')
        connection_type = entry.get('connection_type', '')
        
        summary_data[period_key]['total_amount'] += amount
        summary_data[period_key]['total_entries'] += 1
        summary_data[period_key]['total_refills'] += refills
        
        # Payment mode breakdown using split amounts with backward compat
        cash_a = entry.get('cash_amount', 0) or 0
        online_a = entry.get('online_amount', 0) or 0
        credit_a = entry.get('credit_amount', 0) or 0
        if cash_a == 0 and online_a == 0 and credit_a == 0:
            if payment_mode == 'cash': cash_a = amount
            elif payment_mode == 'online': online_a = amount
            elif payment_mode == 'pending': credit_a = amount
        summary_data[period_key]['cash_amount'] += cash_a
        summary_data[period_key]['online_amount'] += online_a
        summary_data[period_key]['pending_amount'] += credit_a
        if cash_a > 0: summary_data[period_key]['cash_entries'] += 1
        if online_a > 0: summary_data[period_key]['online_entries'] += 1
        if credit_a > 0: summary_data[period_key]['pending_entries'] += 1
        
        # Connection type breakdown
        if connection_type == 'domestic':
            summary_data[period_key]['domestic_new'] += 1
        elif connection_type == 'domestic_refill':
            summary_data[period_key]['domestic_refill'] += 1
        elif connection_type == 'commercial':
            summary_data[period_key]['commercial_new'] += 1
        elif connection_type == 'commercial_refill':
            summary_data[period_key]['commercial_refill'] += 1
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    group_label = {'daily': 'Daily', 'weekly': 'Weekly', 'monthly': 'Monthly'}.get(group_by, 'Daily')
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#16a34a'))
    elements.append(Paragraph(f"K3 GAS SERVICE - {group_label} Sales Summary", title_style))
    elements.append(Paragraph(f"Warehouse: {warehouse_name}", ParagraphStyle('Subtitle', parent=styles['Normal'], alignment=1)))
    
    date_range = ""
    if start_date and end_date:
        date_range = f"Period: {start_date} to {end_date}"
    elif start_date:
        date_range = f"From: {start_date}"
    elif end_date:
        date_range = f"Until: {end_date}"
    
    if date_range:
        elements.append(Paragraph(date_range, ParagraphStyle('DateRange', parent=styles['Normal'], alignment=1)))
    
    elements.append(Spacer(1, 0.25*inch))
    
    # Summary Table
    headers = ['Period', 'Total (₹)', 'Entries', 'Refills', 'Cash (₹)', 'Online (₹)', 'Pending (₹)', 'Dom. New', 'Dom. Refill', 'Comm. New', 'Comm. Refill']
    data = [headers]
    
    # Grand totals
    grand_total = {'amount': 0, 'entries': 0, 'refills': 0, 'cash': 0, 'online': 0, 'pending': 0, 'dn': 0, 'dr': 0, 'cn': 0, 'cr': 0}
    
    for period in sorted(summary_data.keys()):
        s = summary_data[period]
        data.append([
            period,
            format_inr(s['total_amount']),
            str(s['total_entries']),
            str(s['total_refills']),
            format_inr(s['cash_amount']),
            format_inr(s['online_amount']),
            format_inr(s['pending_amount']),
            str(s['domestic_new']),
            str(s['domestic_refill']),
            str(s['commercial_new']),
            str(s['commercial_refill'])
        ])
        grand_total['amount'] += s['total_amount']
        grand_total['entries'] += s['total_entries']
        grand_total['refills'] += s['total_refills']
        grand_total['cash'] += s['cash_amount']
        grand_total['online'] += s['online_amount']
        grand_total['pending'] += s['pending_amount']
        grand_total['dn'] += s['domestic_new']
        grand_total['dr'] += s['domestic_refill']
        grand_total['cn'] += s['commercial_new']
        grand_total['cr'] += s['commercial_refill']
    
    # Add grand total row
    data.append([
        'GRAND TOTAL',
        format_inr(grand_total['amount']),
        str(grand_total['entries']),
        str(grand_total['refills']),
        format_inr(grand_total['cash']),
        format_inr(grand_total['online']),
        format_inr(grand_total['pending']),
        str(grand_total['dn']),
        str(grand_total['dr']),
        str(grand_total['cn']),
        str(grand_total['cr'])
    ])
    
    # Create table with styling
    col_widths = [0.9*inch, 0.8*inch, 0.6*inch, 0.6*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.6*inch, 0.7*inch, 0.6*inch, 0.7*inch]
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16a34a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#dcfce7')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8fafc')])
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Footer note
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%d-%m-%Y %H:%M')}", footer_style))
    
    doc.build(elements)
    
    date_str = datetime.now().strftime('%d%m%y')
    filename = f"Sales_Summary_{group_label}_{warehouse_name.replace(' ', '_')}_{date_str}.pdf"
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/sales-summary-excel")
async def export_sales_summary_excel(
    warehouse_id: str = None,
    start_date: str = None,
    end_date: str = None,
    group_by: str = "daily",  # daily, weekly, monthly
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export sales summary report to Excel with period-based totals"""
    user = await get_current_user(credentials)
    
    query = {}
    
    if user['role'] == 'admin':
        if warehouse_id:
            query['warehouse_id'] = warehouse_id
    else:
        query['warehouse_id'] = user.get('warehouse_id')
    
    if start_date:
        query['date'] = query.get('date', {})
        query['date']['$gte'] = start_date
    if end_date:
        if 'date' not in query:
            query['date'] = {}
        query['date']['$lte'] = end_date
    
    entries = await db.sales_entries.find(query, {'_id': 0}).sort('date', 1).to_list(10000)
    
    # Get warehouse name
    warehouse_name = "All_Warehouses"
    if query.get('warehouse_id'):
        warehouse = await db.warehouses.find_one({'id': query['warehouse_id']}, {'_id': 0})
        warehouse_name = warehouse['name'].replace(' ', '_') if warehouse else 'Unknown'
    
    # Group entries by period
    from collections import defaultdict
    from datetime import datetime as dt
    
    summary_data = defaultdict(lambda: {
        'cash_amount': 0, 'cash_entries': 0,
        'online_amount': 0, 'online_entries': 0,
        'pending_amount': 0, 'pending_entries': 0,
        'total_amount': 0, 'total_entries': 0, 'total_refills': 0,
        'domestic_new': 0, 'domestic_refill': 0,
        'commercial_new': 0, 'commercial_refill': 0
    })
    
    for entry in entries:
        entry_date = entry.get('date', '')
        if not entry_date:
            continue
            
        try:
            date_obj = dt.strptime(entry_date, '%Y-%m-%d')
        except:
            continue
        
        # Determine period key based on group_by
        if group_by == 'daily':
            period_key = entry_date
        elif group_by == 'weekly':
            week_num = date_obj.isocalendar()[1]
            year = date_obj.year
            period_key = f"{year}-W{week_num:02d}"
        elif group_by == 'monthly':
            period_key = date_obj.strftime('%Y-%m')
        else:
            period_key = entry_date
        
        amount = entry.get('amount', 0) or 0
        refills = entry.get('no_of_refills', 0) or 0
        payment_mode = entry.get('payment_mode', 'cash')
        connection_type = entry.get('connection_type', '')
        
        summary_data[period_key]['total_amount'] += amount
        summary_data[period_key]['total_entries'] += 1
        summary_data[period_key]['total_refills'] += refills
        
        # Payment mode breakdown using split amounts with backward compat
        cash_a = entry.get('cash_amount', 0) or 0
        online_a = entry.get('online_amount', 0) or 0
        credit_a = entry.get('credit_amount', 0) or 0
        if cash_a == 0 and online_a == 0 and credit_a == 0:
            if payment_mode == 'cash': cash_a = amount
            elif payment_mode == 'online': online_a = amount
            elif payment_mode == 'pending': credit_a = amount
        summary_data[period_key]['cash_amount'] += cash_a
        summary_data[period_key]['online_amount'] += online_a
        summary_data[period_key]['pending_amount'] += credit_a
        if cash_a > 0: summary_data[period_key]['cash_entries'] += 1
        if online_a > 0: summary_data[period_key]['online_entries'] += 1
        if credit_a > 0: summary_data[period_key]['pending_entries'] += 1
        
        if connection_type == 'domestic':
            summary_data[period_key]['domestic_new'] += 1
        elif connection_type == 'domestic_refill':
            summary_data[period_key]['domestic_refill'] += 1
        elif connection_type == 'commercial':
            summary_data[period_key]['commercial_new'] += 1
        elif connection_type == 'commercial_refill':
            summary_data[period_key]['commercial_refill'] += 1
    
    # Create Excel
    wb = Workbook()
    ws = wb.active
    group_label = {'daily': 'Daily', 'weekly': 'Weekly', 'monthly': 'Monthly'}.get(group_by, 'Daily')
    ws.title = f"{group_label} Summary"
    
    # Title row
    ws.merge_cells('A1:K1')
    ws['A1'] = f"K3 GAS SERVICE - {group_label} Sales Summary Report"
    ws['A1'].font = Font(bold=True, size=14, color="16a34a")
    ws['A1'].alignment = Alignment(horizontal='center')
    
    ws.merge_cells('A2:K2')
    ws['A2'] = f"Warehouse: {warehouse_name.replace('_', ' ')}"
    ws['A2'].alignment = Alignment(horizontal='center')
    
    # Headers
    headers = ['Period', 'Total Amount (₹)', 'Total Entries', 'Total Refills', 
               'Cash (₹)', 'Online (₹)', 'Pending (₹)', 
               'Domestic New', 'Domestic Refill', 'Commercial New', 'Commercial Refill']
    ws.append([])  # Empty row
    ws.append(headers)
    
    # Style headers
    header_fill = PatternFill(start_color="16a34a", end_color="16a34a", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    for cell in ws[4]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')
    
    # Grand totals
    grand_total = {'amount': 0, 'entries': 0, 'refills': 0, 'cash': 0, 'online': 0, 'pending': 0, 'dn': 0, 'dr': 0, 'cn': 0, 'cr': 0}
    
    for period in sorted(summary_data.keys()):
        s = summary_data[period]
        ws.append([
            period,
            format_inr(s['total_amount']),
            s['total_entries'],
            s['total_refills'],
            format_inr(s['cash_amount']),
            format_inr(s['online_amount']),
            format_inr(s['pending_amount']),
            s['domestic_new'],
            s['domestic_refill'],
            s['commercial_new'],
            s['commercial_refill']
        ])
        grand_total['amount'] += s['total_amount']
        grand_total['entries'] += s['total_entries']
        grand_total['refills'] += s['total_refills']
        grand_total['cash'] += s['cash_amount']
        grand_total['online'] += s['online_amount']
        grand_total['pending'] += s['pending_amount']
        grand_total['dn'] += s['domestic_new']
        grand_total['dr'] += s['domestic_refill']
        grand_total['cn'] += s['commercial_new']
        grand_total['cr'] += s['commercial_refill']
    
    # Grand total row
    total_row_num = ws.max_row + 1
    ws.append([
        'GRAND TOTAL',
        format_inr(grand_total['amount']),
        grand_total['entries'],
        grand_total['refills'],
        format_inr(grand_total['cash']),
        format_inr(grand_total['online']),
        format_inr(grand_total['pending']),
        grand_total['dn'],
        grand_total['dr'],
        grand_total['cn'],
        grand_total['cr']
    ])
    
    # Style total row
    total_fill = PatternFill(start_color="dcfce7", end_color="dcfce7", fill_type="solid")
    total_font = Font(bold=True)
    for cell in ws[total_row_num]:
        cell.fill = total_fill
        cell.font = total_font
    
    # Adjust column widths
    column_widths = [14, 16, 14, 14, 14, 14, 14, 14, 16, 16, 18]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[chr(64 + i)].width = width
    
    # Add borders to data area
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    for row in ws.iter_rows(min_row=4, max_row=ws.max_row, min_col=1, max_col=11):
        for cell in row:
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center')
    
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    date_str = datetime.now().strftime('%d%m%y')
    filename = f"Sales_Summary_{group_label}_{warehouse_name}_{date_str}.xlsx"
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

