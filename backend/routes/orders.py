from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from database import db
from deps import get_current_user, require_admin, security
from helpers import format_inr
from models import OrderCreate, OrderUpdate, OrderStatusUpdate
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

router = APIRouter()

async def get_next_order_number(warehouse_id: str) -> str:
    """Generate next order number for a warehouse with warehouse-specific prefix"""
    # Get warehouse to determine prefix
    warehouse = await db.warehouses.find_one({'id': warehouse_id})
    
    # Assign different prefixes based on warehouse name
    prefix_map = {
        'Jullang': 'J',
        'Naharlagun': 'N',
        'Doimukh': 'D',
    }
    
    warehouse_name = warehouse['name'] if warehouse else 'Unknown'
    prefix = prefix_map.get(warehouse_name, 'A')  # Default to 'A' if not found
    
    # Find the highest order number for this warehouse
    latest_order = await db.orders.find_one(
        {'warehouse_id': warehouse_id},
        sort=[('order_sequence', -1)]
    )
    
    if latest_order and 'order_sequence' in latest_order:
        next_seq = latest_order['order_sequence'] + 1
    else:
        next_seq = 1
    
    return f"{prefix}{next_seq}", next_seq

@router.get("/orders")
async def get_orders(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    payment_mode: Optional[str] = None,
    connection_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get orders for the user's warehouse (or all for admin)"""
    user = await get_current_user(credentials)
    
    query = {}
    
    # Filter by warehouse for non-admin users
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id')
    
    # Date filters
    if start_date:
        query['order_date'] = query.get('order_date', {})
        query['order_date']['$gte'] = start_date
    if end_date:
        if 'order_date' not in query:
            query['order_date'] = {}
        query['order_date']['$lte'] = end_date
    
    # Payment mode filter
    if payment_mode and payment_mode != 'all':
        query['payment_mode'] = payment_mode
    
    # Connection type filter
    if connection_type and connection_type != 'all':
        query['connection_type'] = connection_type
    
    # Status filter
    if status and status != 'all':
        query['status'] = status
    
    # Search
    if search:
        query['$or'] = [
            {'customer_name': {'$regex': search, '$options': 'i'}},
            {'mobile_number': {'$regex': search, '$options': 'i'}},
            {'order_no': {'$regex': search, '$options': 'i'}},
            {'address_landmark': {'$regex': search, '$options': 'i'}}
        ]
    
    orders = await db.orders.find(query).sort('order_date', -1).to_list(1000)
    
    # Get warehouse names
    warehouse_ids = list(set(o.get('warehouse_id') for o in orders if o.get('warehouse_id')))
    warehouses = await db.warehouses.find({'id': {'$in': warehouse_ids}}).to_list(100)
    warehouse_map = {w['id']: w['name'] for w in warehouses}
    
    result = []
    for o in orders:
        result.append({
            'id': o['id'],
            'warehouse_id': o.get('warehouse_id', ''),
            'warehouse_name': warehouse_map.get(o.get('warehouse_id', ''), 'Unknown'),
            'order_date': o['order_date'],
            'order_no': o['order_no'],
            'order_sequence': o.get('order_sequence', 0),
            'customer_id': o.get('customer_id'),
            'customer_name': o['customer_name'],
            'mobile_number': o.get('mobile_number', ''),
            'address_landmark': o.get('address_landmark', ''),
            'connection_type': o['connection_type'],
            'cylinder_nos': o.get('cylinder_nos', ''),
            'payment_mode': o['payment_mode'],
            'status': o.get('status', 'pending'),
            'remarks': o.get('remarks', ''),
            'created_by': o.get('created_by', ''),
            'created_at': o.get('created_at', ''),
            'delivered_at': o.get('delivered_at'),
            'cancelled_at': o.get('cancelled_at'),
            'cancellation_reason': o.get('cancellation_reason', '')
        })
    
    return result

@router.post("/orders")
async def create_order(
    order: OrderCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create a new order"""
    user = await get_current_user(credentials)
    
    warehouse_id = user.get('warehouse_id')
    if user['role'] == 'admin':
        raise HTTPException(status_code=400, detail="Admin must use warehouse-specific endpoint")
    
    if not warehouse_id:
        raise HTTPException(status_code=400, detail="User has no assigned warehouse")
    
    # Check if this is Plant Hollongi (orders not allowed)
    warehouse = await db.warehouses.find_one({'id': warehouse_id})
    if warehouse and warehouse.get('is_plant'):
        raise HTTPException(status_code=403, detail="Orders are not available for Plant Hollongi")
    
    # Generate order number
    order_no, order_seq = await get_next_order_number(warehouse_id)
    
    order_doc = {
        'id': str(uuid.uuid4()),
        'warehouse_id': warehouse_id,
        'order_date': order.order_date,
        'order_no': order_no,
        'order_sequence': order_seq,
        'customer_id': order.customer_id,
        'customer_name': order.customer_name,
        'mobile_number': order.mobile_number,
        'address_landmark': order.address_landmark,
        'connection_type': order.connection_type,
        'cylinder_nos': order.cylinder_nos,
        'payment_mode': order.payment_mode,
        'status': 'pending',
        'remarks': order.remarks,
        'created_by': user['id'],
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.orders.insert_one(order_doc)
    
    warehouse_name = warehouse['name'] if warehouse else 'Unknown'
    
    return {
        'id': order_doc['id'],
        'warehouse_id': order_doc['warehouse_id'],
        'warehouse_name': warehouse_name,
        'order_date': order_doc['order_date'],
        'order_no': order_doc['order_no'],
        'order_sequence': order_doc['order_sequence'],
        'customer_id': order_doc['customer_id'],
        'customer_name': order_doc['customer_name'],
        'mobile_number': order_doc['mobile_number'],
        'address_landmark': order_doc['address_landmark'],
        'connection_type': order_doc['connection_type'],
        'cylinder_nos': order_doc['cylinder_nos'],
        'payment_mode': order_doc['payment_mode'],
        'status': order_doc['status'],
        'remarks': order_doc['remarks'],
        'created_by': order_doc['created_by'],
        'created_at': order_doc['created_at'],
        'delivered_at': None
    }

@router.post("/orders/warehouse/{warehouse_id}")
async def create_order_for_warehouse(
    warehouse_id: str,
    order: OrderCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create an order for a specific warehouse (admin only)"""
    user = await get_current_user(credentials)
    
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admin can create orders for other warehouses")
    
    # Verify warehouse exists and is not Plant Hollongi
    warehouse = await db.warehouses.find_one({'id': warehouse_id})
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    if warehouse.get('is_plant'):
        raise HTTPException(status_code=403, detail="Orders are not available for Plant Hollongi")
    
    # Generate order number
    order_no, order_seq = await get_next_order_number(warehouse_id)
    
    order_doc = {
        'id': str(uuid.uuid4()),
        'warehouse_id': warehouse_id,
        'order_date': order.order_date,
        'order_no': order_no,
        'order_sequence': order_seq,
        'customer_id': order.customer_id,
        'customer_name': order.customer_name,
        'mobile_number': order.mobile_number,
        'address_landmark': order.address_landmark,
        'connection_type': order.connection_type,
        'cylinder_nos': order.cylinder_nos,
        'payment_mode': order.payment_mode,
        'status': 'pending',
        'remarks': order.remarks,
        'created_by': user['id'],
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.orders.insert_one(order_doc)
    
    return {
        'id': order_doc['id'],
        'warehouse_id': order_doc['warehouse_id'],
        'warehouse_name': warehouse['name'],
        'order_date': order_doc['order_date'],
        'order_no': order_doc['order_no'],
        'order_sequence': order_doc['order_sequence'],
        'customer_id': order_doc['customer_id'],
        'customer_name': order_doc['customer_name'],
        'mobile_number': order_doc['mobile_number'],
        'address_landmark': order_doc['address_landmark'],
        'connection_type': order_doc['connection_type'],
        'cylinder_nos': order_doc['cylinder_nos'],
        'payment_mode': order_doc['payment_mode'],
        'status': order_doc['status'],
        'remarks': order_doc['remarks'],
        'created_by': order_doc['created_by'],
        'created_at': order_doc['created_at'],
        'delivered_at': None
    }

@router.get("/orders/{order_id}")
async def get_order(
    order_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get a single order by ID"""
    user = await get_current_user(credentials)
    
    order = await db.orders.find_one({'id': order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check access
    if user['role'] != 'admin' and order.get('warehouse_id') != user.get('warehouse_id'):
        raise HTTPException(status_code=403, detail="Access denied")
    
    warehouse = await db.warehouses.find_one({'id': order.get('warehouse_id')})
    
    return {
        'id': order['id'],
        'warehouse_id': order.get('warehouse_id', ''),
        'warehouse_name': warehouse['name'] if warehouse else 'Unknown',
        'order_date': order['order_date'],
        'order_no': order['order_no'],
        'order_sequence': order.get('order_sequence', 0),
        'customer_id': order.get('customer_id'),
        'customer_name': order['customer_name'],
        'mobile_number': order.get('mobile_number', ''),
        'address_landmark': order.get('address_landmark', ''),
        'connection_type': order['connection_type'],
        'cylinder_nos': order.get('cylinder_nos', ''),
        'payment_mode': order['payment_mode'],
        'status': order.get('status', 'pending'),
        'remarks': order.get('remarks', ''),
        'created_by': order.get('created_by', ''),
        'created_at': order.get('created_at', ''),
        'delivered_at': order.get('delivered_at')
    }

@router.put("/orders/{order_id}")
async def update_order(
    order_id: str,
    order: OrderUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update an order - all users can edit all fields. Cancelled orders are read-only."""
    user = await get_current_user(credentials)
    
    existing = await db.orders.find_one({'id': order_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Block edits on cancelled orders
    if existing.get('status') == 'cancelled':
        raise HTTPException(status_code=400, detail="Cancelled orders cannot be edited")
    
    update_data = {}
    if order.order_date is not None:
        update_data['order_date'] = order.order_date
    if order.customer_name is not None:
        update_data['customer_name'] = order.customer_name
    if order.mobile_number is not None:
        update_data['mobile_number'] = order.mobile_number
    if order.address_landmark is not None:
        update_data['address_landmark'] = order.address_landmark
    if order.connection_type is not None:
        update_data['connection_type'] = order.connection_type
    if order.payment_mode is not None:
        update_data['payment_mode'] = order.payment_mode
    if order.remarks is not None:
        update_data['remarks'] = order.remarks
    if order.status is not None:
        update_data['status'] = order.status
        if order.status == 'delivered':
            update_data['delivered_at'] = datetime.now(timezone.utc).isoformat()
    
    update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
    
    await db.orders.update_one({'id': order_id}, {'$set': update_data})
    
    updated = await db.orders.find_one({'id': order_id})
    warehouse = await db.warehouses.find_one({'id': updated.get('warehouse_id')})
    
    return {
        'id': updated['id'],
        'warehouse_id': updated.get('warehouse_id', ''),
        'warehouse_name': warehouse['name'] if warehouse else 'Unknown',
        'order_date': updated['order_date'],
        'order_no': updated['order_no'],
        'order_sequence': updated.get('order_sequence', 0),
        'customer_id': updated.get('customer_id'),
        'customer_name': updated['customer_name'],
        'mobile_number': updated.get('mobile_number', ''),
        'address_landmark': updated.get('address_landmark', ''),
        'connection_type': updated['connection_type'],
        'payment_mode': updated['payment_mode'],
        'status': updated.get('status', 'pending'),
        'remarks': updated.get('remarks', ''),
        'created_by': updated.get('created_by', ''),
        'created_at': updated.get('created_at', ''),
        'updated_at': updated.get('updated_at'),
        'delivered_at': updated.get('delivered_at')
    }

@router.patch("/orders/{order_id}/status")
async def update_order_status(
    order_id: str,
    status_update: OrderStatusUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update order status (Pending / Delivered / Cancelled)"""
    user = await get_current_user(credentials)
    
    existing = await db.orders.find_one({'id': order_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check warehouse access
    if user['role'] != 'admin' and existing.get('warehouse_id') != user.get('warehouse_id'):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if status_update.status not in ['pending', 'delivered', 'cancelled']:
        raise HTTPException(status_code=400, detail="Invalid status. Must be 'pending', 'delivered', or 'cancelled'")
    
    # Prevent changes to cancelled orders (except by admin reverting)
    if existing.get('status') == 'cancelled' and user['role'] != 'admin':
        raise HTTPException(status_code=400, detail="Cancelled orders cannot be modified")
    
    update_data = {
        'status': status_update.status,
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    if status_update.status == 'delivered':
        update_data['delivered_at'] = datetime.now(timezone.utc).isoformat()
        update_data['cancelled_at'] = None
        update_data['cancellation_reason'] = None
    elif status_update.status == 'cancelled':
        update_data['cancelled_at'] = datetime.now(timezone.utc).isoformat()
        update_data['cancellation_reason'] = status_update.cancellation_reason or ''
        update_data['delivered_at'] = None
    elif status_update.status == 'pending':
        update_data['delivered_at'] = None
        update_data['cancelled_at'] = None
        update_data['cancellation_reason'] = None
    
    await db.orders.update_one({'id': order_id}, {'$set': update_data})
    
    updated = await db.orders.find_one({'id': order_id})
    warehouse = await db.warehouses.find_one({'id': updated.get('warehouse_id')})
    
    return {
        'id': updated['id'],
        'warehouse_id': updated.get('warehouse_id', ''),
        'warehouse_name': warehouse['name'] if warehouse else 'Unknown',
        'order_no': updated['order_no'],
        'status': updated['status'],
        'delivered_at': updated.get('delivered_at'),
        'cancelled_at': updated.get('cancelled_at'),
        'cancellation_reason': updated.get('cancellation_reason'),
        'message': f"Order {updated['order_no']} marked as {status_update.status}"
    }

@router.delete("/orders/{order_id}")
async def delete_order(
    order_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Delete an order (admin only)"""
    user = await get_current_user(credentials)
    
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admin can delete orders")
    
    result = await db.orders.delete_one({'id': order_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {"message": "Order deleted successfully"}

@router.get("/admin/order-analysis")
async def get_order_analysis(
    warehouse_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Admin order analysis - grouped by date with warehouse breakdown"""
    user = await get_current_user(credentials)
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {}
    if warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    if start_date:
        query['order_date'] = query.get('order_date', {})
        query['order_date']['$gte'] = start_date
    if end_date:
        if 'order_date' not in query:
            query['order_date'] = {}
        query['order_date']['$lte'] = end_date
    if status and status != 'all':
        query['status'] = status
    if search:
        query['$or'] = [
            {'customer_name': {'$regex': search, '$options': 'i'}},
            {'mobile_number': {'$regex': search, '$options': 'i'}},
            {'order_no': {'$regex': search, '$options': 'i'}}
        ]
    
    orders = await db.orders.find(query).sort('order_date', -1).to_list(5000)
    
    # Get warehouse names
    wh_ids = list(set(o.get('warehouse_id') for o in orders if o.get('warehouse_id')))
    warehouses = await db.warehouses.find({'id': {'$in': wh_ids}}).to_list(100)
    wh_map = {w['id']: w['name'] for w in warehouses}
    
    # Group by date
    date_groups = {}
    wh_breakdown = {}
    total_quantity = 0
    
    for o in orders:
        date = o.get('order_date', 'Unknown')
        wh_name = wh_map.get(o.get('warehouse_id', ''), 'Unknown')
        
        conn_type = o.get('connection_type', '')
        qty = 1
        if 'refill' in conn_type.lower():
            qty = o.get('no_of_cylinders', 1) or 1
        
        product = conn_type.replace('_', ' ').title()
        if o.get('cylinder_nos'):
            product += f" (Cyl: {o['cylinder_nos']})"
        
        entry = {
            'id': o['id'],
            'order_no': o.get('order_no', ''),
            'customer_name': o.get('customer_name', ''),
            'mobile_number': o.get('mobile_number', ''),
            'address': o.get('address_landmark', ''),
            'product': product,
            'connection_type': conn_type,
            'quantity': qty,
            'status': o.get('status', 'pending'),
            'payment_mode': o.get('payment_mode', ''),
            'warehouse_id': o.get('warehouse_id', ''),
            'warehouse_name': wh_name,
            'delivered_at': o.get('delivered_at'),
            'remarks': o.get('remarks', '')
        }
        
        if date not in date_groups:
            date_groups[date] = []
        date_groups[date].append(entry)
        
        wh_breakdown[wh_name] = wh_breakdown.get(wh_name, 0) + 1
        total_quantity += qty
    
    # Build sorted date groups
    grouped = [{'date': d, 'orders': date_groups[d], 'count': len(date_groups[d])} for d in sorted(date_groups.keys(), reverse=True)]
    
    total_pending = sum(1 for o in orders if o.get('status', 'pending') == 'pending')
    total_delivered = sum(1 for o in orders if o.get('status') == 'delivered')
    total_cancelled = sum(1 for o in orders if o.get('status') == 'cancelled')
    
    return {
        'groups': grouped,
        'summary': {
            'total_orders': len(orders),
            'total_quantity': total_quantity,
            'total_pending': total_pending,
            'total_delivered': total_delivered,
            'total_cancelled': total_cancelled,
            'warehouse_breakdown': wh_breakdown,
            'date_range': {
                'start': min((o.get('order_date', '') for o in orders), default=''),
                'end': max((o.get('order_date', '') for o in orders), default='')
            }
        }
    }

@router.get("/export/order-analysis-pdf")
async def export_order_analysis_pdf(
    warehouse_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export order analysis as PDF grouped by date"""
    user = await get_current_user(credentials)
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {}
    if warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    if start_date:
        query['order_date'] = query.get('order_date', {})
        query['order_date']['$gte'] = start_date
    if end_date:
        if 'order_date' not in query:
            query['order_date'] = {}
        query['order_date']['$lte'] = end_date
    if status and status != 'all':
        query['status'] = status
    
    orders = await db.orders.find(query).sort('order_date', -1).to_list(5000)
    wh_ids = list(set(o.get('warehouse_id') for o in orders if o.get('warehouse_id')))
    warehouses_list = await db.warehouses.find({'id': {'$in': wh_ids}}).to_list(100)
    wh_map = {w['id']: w['name'] for w in warehouses_list}
    
    # Determine warehouse label
    wh_label = "All Warehouses"
    if warehouse_id and warehouse_id != 'all':
        wh_label = wh_map.get(warehouse_id, warehouse_id)
    
    today_display = datetime.now(timezone.utc).strftime('%d-%m-%Y')
    
    # Group by date
    date_groups = {}
    wh_breakdown = {}
    total_qty = 0
    for o in orders:
        date = o.get('order_date', 'Unknown')
        wh_name = wh_map.get(o.get('warehouse_id', ''), 'Unknown')
        wh_breakdown[wh_name] = wh_breakdown.get(wh_name, 0) + 1
        conn_type = o.get('connection_type', '')
        qty = 1 if 'refill' not in conn_type.lower() else (o.get('no_of_cylinders', 1) or 1)
        total_qty += qty
        if date not in date_groups:
            date_groups[date] = []
        date_groups[date].append(o)
    
    total_pending = sum(1 for o in orders if o.get('status', 'pending') == 'pending')
    total_delivered = sum(1 for o in orders if o.get('status') == 'delivered')
    
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), topMargin=20, bottomMargin=20, leftMargin=20, rightMargin=20)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=16, spaceAfter=4, textColor=colors.HexColor('#15803d'))
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=9, textColor=colors.grey, spaceAfter=4)
    date_header_style = ParagraphStyle('DateHeader', parent=styles['Heading2'], fontSize=10, textColor=colors.HexColor('#1e40af'), spaceBefore=10, spaceAfter=4)
    
    elements.append(Paragraph("K3 GAS SERVICE - Order Analysis Report", title_style))
    wh_breakdown_str = " | ".join([f"{k}: {v}" for k, v in wh_breakdown.items()])
    elements.append(Paragraph(f"Warehouse: {wh_label} | Generated: {today_display} | Total Orders: {len(orders)} | Qty: {total_qty} | Pending: {total_pending} | Delivered: {total_delivered}", subtitle_style))
    if wh_breakdown_str:
        elements.append(Paragraph(f"Breakdown: {wh_breakdown_str}", subtitle_style))
    elements.append(Spacer(1, 8))
    
    for date in sorted(date_groups.keys(), reverse=True):
        grp = date_groups[date]
        try:
            display_date = datetime.strptime(date, '%Y-%m-%d').strftime('%d-%m-%Y')
        except:
            display_date = date
        elements.append(Paragraph(f"{display_date} ({len(grp)} orders)", date_header_style))
        
        data = [['SL', 'Order No', 'Customer', 'Product', 'Qty', 'Status', 'Payment', 'Warehouse', 'Delivery']]
        for i, o in enumerate(grp, 1):
            conn = o.get('connection_type', '').replace('_', ' ').title()
            if o.get('cylinder_nos'):
                conn += f" ({o['cylinder_nos']})"
            qty = 1 if 'refill' not in o.get('connection_type', '').lower() else (o.get('no_of_cylinders', 1) or 1)
            delivered = ''
            if o.get('delivered_at'):
                try:
                    delivered = datetime.strptime(o['delivered_at'][:10], '%Y-%m-%d').strftime('%d-%m-%Y')
                except:
                    delivered = str(o['delivered_at'])[:10]
            data.append([
                str(i),
                o.get('order_no', ''),
                o.get('customer_name', '')[:18],
                conn[:20],
                str(qty),
                o.get('status', 'pending').title(),
                o.get('payment_mode', '')[:6].title(),
                wh_map.get(o.get('warehouse_id', ''), '')[:12],
                delivered
            ])
        
        col_widths = [22, 60, 105, 115, 30, 55, 50, 70, 60]
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 3),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4ff')])
        ]))
        elements.append(table)
        elements.append(Spacer(1, 6))
    
    doc.build(elements)
    output.seek(0)
    return StreamingResponse(output, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=order_analysis_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.pdf"})

@router.get("/export/order-analysis-excel")
async def export_order_analysis_excel(
    warehouse_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export order analysis as Excel grouped by date"""
    user = await get_current_user(credentials)
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {}
    if warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    if start_date:
        query['order_date'] = query.get('order_date', {})
        query['order_date']['$gte'] = start_date
    if end_date:
        if 'order_date' not in query:
            query['order_date'] = {}
        query['order_date']['$lte'] = end_date
    if status and status != 'all':
        query['status'] = status
    
    orders = await db.orders.find(query).sort('order_date', -1).to_list(5000)
    wh_ids = list(set(o.get('warehouse_id') for o in orders if o.get('warehouse_id')))
    warehouses_list = await db.warehouses.find({'id': {'$in': wh_ids}}).to_list(100)
    wh_map = {w['id']: w['name'] for w in warehouses_list}
    
    wh_label = "All Warehouses"
    if warehouse_id and warehouse_id != 'all':
        wh_label = wh_map.get(warehouse_id, warehouse_id)
    
    today_display = datetime.now(timezone.utc).strftime('%d-%m-%Y')
    
    # Group by date
    date_groups = {}
    wh_breakdown = {}
    total_qty = 0
    for o in orders:
        date = o.get('order_date', 'Unknown')
        wh_name = wh_map.get(o.get('warehouse_id', ''), 'Unknown')
        wh_breakdown[wh_name] = wh_breakdown.get(wh_name, 0) + 1
        conn_type = o.get('connection_type', '')
        qty = 1 if 'refill' not in conn_type.lower() else (o.get('no_of_cylinders', 1) or 1)
        total_qty += qty
        if date not in date_groups:
            date_groups[date] = []
        date_groups[date].append(o)
    
    total_pending = sum(1 for o in orders if o.get('status', 'pending') == 'pending')
    total_delivered = sum(1 for o in orders if o.get('status') == 'delivered')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Order Analysis"
    
    ws.merge_cells('A1:I1')
    ws['A1'] = "K3 GAS SERVICE - Order Analysis Report"
    ws['A1'].font = Font(bold=True, size=14, color="15803d")
    ws.merge_cells('A2:I2')
    ws['A2'] = f"Warehouse: {wh_label} | Generated: {today_display} | Total: {len(orders)} | Qty: {total_qty} | Pending: {total_pending} | Delivered: {total_delivered}"
    ws['A2'].font = Font(size=9, color="666666")
    wh_breakdown_str = " | ".join([f"{k}: {v}" for k, v in wh_breakdown.items()])
    ws.merge_cells('A3:I3')
    ws['A3'] = f"Breakdown: {wh_breakdown_str}"
    ws['A3'].font = Font(size=9, color="666666")
    
    current_row = 5
    header_fill = PatternFill(start_color="1e40af", end_color="1e40af", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=10)
    date_fill = PatternFill(start_color="dbeafe", end_color="dbeafe", fill_type="solid")
    date_font = Font(bold=True, size=10, color="1e40af")
    
    for date in sorted(date_groups.keys(), reverse=True):
        grp = date_groups[date]
        try:
            display_date = datetime.strptime(date, '%Y-%m-%d').strftime('%d-%m-%Y')
        except:
            display_date = date
        
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=9)
        cell = ws.cell(row=current_row, column=1, value=f"{display_date} ({len(grp)} orders)")
        cell.fill = date_fill
        cell.font = date_font
        current_row += 1
        
        headers = ['SL', 'Order No', 'Customer', 'Product', 'Qty', 'Status', 'Payment', 'Warehouse', 'Delivery Date']
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=current_row, column=col, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
        current_row += 1
        
        for i, o in enumerate(grp, 1):
            conn = o.get('connection_type', '').replace('_', ' ').title()
            if o.get('cylinder_nos'):
                conn += f" ({o['cylinder_nos']})"
            qty = 1 if 'refill' not in o.get('connection_type', '').lower() else (o.get('no_of_cylinders', 1) or 1)
            delivered = ''
            if o.get('delivered_at'):
                try:
                    delivered = datetime.strptime(o['delivered_at'][:10], '%Y-%m-%d').strftime('%d-%m-%Y')
                except:
                    delivered = str(o['delivered_at'])[:10]
            ws.append([i, o.get('order_no', ''), o.get('customer_name', ''), conn, qty, o.get('status', 'pending').title(), o.get('payment_mode', '').title(), wh_map.get(o.get('warehouse_id', ''), ''), delivered])
            current_row += 1
        
        current_row += 1
    
    col_widths = [6, 14, 22, 24, 6, 12, 12, 16, 14]
    for idx, w in enumerate(col_widths, 1):
        ws.column_dimensions[chr(64 + idx)].width = w
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=order_analysis_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.xlsx"})


