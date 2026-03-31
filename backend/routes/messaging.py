from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials
from database import db
from deps import get_current_user, security
from models import MessagingSettings, BulkMessageCreate, MessageLogResponse
from typing import List, Optional
from datetime import datetime, timezone
import uuid

router = APIRouter()

@router.get("/messaging/settings")
async def get_messaging_settings(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get messaging API settings (admin only)"""
    user = await get_current_user(credentials)
    
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    settings = await db.messaging_settings.find_one({'type': 'messaging'})
    
    if not settings:
        return {
            'provider': '',
            'sms_configured': False,
            'whatsapp_configured': False,
            'sms_sender_id': '',
            'whatsapp_phone_number': ''
        }
    
    return {
        'provider': settings.get('provider', ''),
        'sms_configured': bool(settings.get('sms_api_key')),
        'whatsapp_configured': bool(settings.get('whatsapp_api_key')),
        'sms_sender_id': settings.get('sms_sender_id', ''),
        'whatsapp_phone_number': settings.get('whatsapp_phone_number', ''),
        'sms_api_key': '***' if settings.get('sms_api_key') else '',
        'whatsapp_api_key': '***' if settings.get('whatsapp_api_key') else ''
    }

@router.post("/messaging/settings")
async def update_messaging_settings(
    settings: MessagingSettings,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update messaging API settings (admin only)"""
    user = await get_current_user(credentials)
    
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    existing = await db.messaging_settings.find_one({'type': 'messaging'})
    
    update_data = {
        'type': 'messaging',
        'provider': settings.provider,
        'sms_sender_id': settings.sms_sender_id,
        'whatsapp_phone_number': settings.whatsapp_phone_number,
        'whatsapp_business_id': settings.whatsapp_business_id,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'updated_by': user['id']
    }
    
    # Only update API keys if provided (not empty)
    if settings.sms_api_key:
        update_data['sms_api_key'] = settings.sms_api_key
    if settings.sms_api_secret:
        update_data['sms_api_secret'] = settings.sms_api_secret
    if settings.whatsapp_api_key:
        update_data['whatsapp_api_key'] = settings.whatsapp_api_key
    if settings.whatsapp_api_secret:
        update_data['whatsapp_api_secret'] = settings.whatsapp_api_secret
    
    if existing:
        await db.messaging_settings.update_one({'type': 'messaging'}, {'$set': update_data})
    else:
        update_data['created_at'] = datetime.now(timezone.utc).isoformat()
        await db.messaging_settings.insert_one(update_data)
    
    return {
        'message': 'Messaging settings updated successfully',
        'provider': settings.provider,
        'sms_configured': bool(settings.sms_api_key or (existing and existing.get('sms_api_key'))),
        'whatsapp_configured': bool(settings.whatsapp_api_key or (existing and existing.get('whatsapp_api_key')))
    }

@router.get("/messaging/recipients/count")
async def get_recipient_count(
    recipient_filter: str = "all",
    warehouse_id: Optional[str] = None,
    category: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get count of recipients based on filter"""
    user = await get_current_user(credentials)
    
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {}
    
    if recipient_filter == 'warehouse' and warehouse_id:
        query['warehouse_id'] = warehouse_id
    elif recipient_filter == 'category' and category:
        query['connection_type'] = category
    
    # Get customers and filter to those with valid phone numbers (exactly 10 digits)
    customers = await db.customers.find(query).to_list(10000)
    
    # Filter to those with phone numbers (matching send endpoint logic)
    valid_recipients = []
    for c in customers:
        phone = c.get('mobile_number') or c.get('phone') or ''
        if phone and len(phone) == 10:
            valid_recipients.append(c)
    
    total_count = len(valid_recipients)
    
    # Get warehouse breakdown
    warehouse_counts = {}
    for c in valid_recipients:
        wid = c.get('warehouse_id')
        if wid:
            warehouse_counts[wid] = warehouse_counts.get(wid, 0) + 1
    
    # Get warehouse names
    warehouse_ids = list(warehouse_counts.keys())
    warehouses = await db.warehouses.find({'id': {'$in': warehouse_ids}}).to_list(100)
    warehouse_map = {w['id']: w['name'] for w in warehouses}
    
    breakdown = []
    for wid, count in warehouse_counts.items():
        breakdown.append({
            'warehouse_id': wid,
            'warehouse_name': warehouse_map.get(wid, 'Unknown'),
            'count': count
        })
    
    return {
        'total_recipients': total_count,
        'breakdown_by_warehouse': breakdown
    }

async def send_sms_message(phone: str, message: str, settings: dict) -> dict:
    """
    Placeholder function for SMS sending.
    Replace with actual SMS provider integration.
    
    Supported providers structure:
    - Twilio: Uses twilio-python SDK
    - MSG91: Uses requests to MSG91 API
    - Other: Implement as needed
    """
    provider = settings.get('provider', '')
    
    if not provider or not settings.get('sms_api_key'):
        return {'success': False, 'error': 'SMS not configured'}
    
    # TODO: Implement actual SMS sending based on provider
    # Example structure for different providers:
    
    # if provider == 'twilio':
    #     from twilio.rest import Client
    #     client = Client(settings['sms_api_key'], settings['sms_api_secret'])
    #     message = client.messages.create(
    #         body=message,
    #         from_=settings['sms_sender_id'],
    #         to=phone
    #     )
    #     return {'success': True, 'message_id': message.sid}
    
    # if provider == 'msg91':
    #     import requests
    #     response = requests.post(
    #         'https://api.msg91.com/api/v5/flow/',
    #         headers={'authkey': settings['sms_api_key']},
    #         json={'mobiles': phone, 'message': message}
    #     )
    #     return {'success': response.ok, 'response': response.json()}
    
    # For now, return simulated success
    return {
        'success': True,
        'simulated': True,
        'message': f'SMS to {phone} would be sent (API not configured)'
    }

async def send_whatsapp_message(phone: str, message: str, settings: dict) -> dict:
    """
    Placeholder function for WhatsApp sending.
    Replace with actual WhatsApp Business API integration.
    
    Supported providers structure:
    - Twilio WhatsApp: Uses twilio-python SDK
    - Meta WhatsApp Business API: Direct API calls
    - 360dialog: Uses 360dialog API
    """
    provider = settings.get('provider', '')
    
    if not settings.get('whatsapp_api_key'):
        return {'success': False, 'error': 'WhatsApp not configured'}
    
    # TODO: Implement actual WhatsApp sending based on provider
    # Example structure:
    
    # if provider == 'twilio':
    #     from twilio.rest import Client
    #     client = Client(settings['whatsapp_api_key'], settings['whatsapp_api_secret'])
    #     message = client.messages.create(
    #         body=message,
    #         from_=f"whatsapp:{settings['whatsapp_phone_number']}",
    #         to=f"whatsapp:{phone}"
    #     )
    #     return {'success': True, 'message_id': message.sid}
    
    # if provider == 'meta':
    #     import requests
    #     response = requests.post(
    #         f"https://graph.facebook.com/v17.0/{settings['whatsapp_business_id']}/messages",
    #         headers={'Authorization': f"Bearer {settings['whatsapp_api_key']}"},
    #         json={'messaging_product': 'whatsapp', 'to': phone, 'type': 'text', 'text': {'body': message}}
    #     )
    #     return {'success': response.ok, 'response': response.json()}
    
    # For now, return simulated success
    return {
        'success': True,
        'simulated': True,
        'message': f'WhatsApp to {phone} would be sent (API not configured)'
    }

@router.post("/messaging/send")
async def send_bulk_message(
    message_data: BulkMessageCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Send bulk SMS/WhatsApp message to customers (admin only)"""
    user = await get_current_user(credentials)
    
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if not message_data.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    if message_data.channel not in ['sms', 'whatsapp', 'both']:
        raise HTTPException(status_code=400, detail="Invalid channel. Must be 'sms', 'whatsapp', or 'both'")
    
    # Get messaging settings
    settings = await db.messaging_settings.find_one({'type': 'messaging'})
    if not settings:
        settings = {}
    
    # Check if required channel is configured
    if message_data.channel in ['sms', 'both'] and not settings.get('sms_api_key'):
        # Allow sending but mark as simulated
        pass
    if message_data.channel in ['whatsapp', 'both'] and not settings.get('whatsapp_api_key'):
        # Allow sending but mark as simulated
        pass
    
    # Build customer query
    query = {}
    if message_data.recipient_filter == 'warehouse' and message_data.warehouse_id:
        query['warehouse_id'] = message_data.warehouse_id
    elif message_data.recipient_filter == 'category' and message_data.category:
        query['connection_type'] = message_data.category
    
    # Get customers with phone numbers
    customers = await db.customers.find(query).to_list(10000)
    
    # Filter to those with phone numbers (exactly 10 digits)
    recipients = []
    for c in customers:
        phone = c.get('mobile_number') or c.get('phone') or ''
        if phone and len(phone) == 10:
            recipients.append({
                'id': c['id'],
                'name': c['customer_name'],
                'phone': phone,
                'warehouse_id': c.get('warehouse_id')
            })
    
    if not recipients:
        raise HTTPException(status_code=400, detail="No recipients found with valid phone numbers")
    
    # Create message log entry
    message_log = {
        'id': str(uuid.uuid4()),
        'channel': message_data.channel,
        'message': message_data.message,
        'recipient_filter': message_data.recipient_filter,
        'warehouse_id': message_data.warehouse_id,
        'category': message_data.category,
        'recipient_count': len(recipients),
        'successful_count': 0,
        'failed_count': 0,
        'status': 'processing',
        'results': [],
        'created_at': datetime.now(timezone.utc).isoformat(),
        'created_by': user['id']
    }
    
    await db.message_logs.insert_one(message_log)
    
    # Send messages
    successful = 0
    failed = 0
    results = []
    
    for recipient in recipients:
        phone = recipient['phone']
        result = {'recipient': recipient['name'], 'phone': phone, 'sms': None, 'whatsapp': None}
        
        if message_data.channel in ['sms', 'both']:
            sms_result = await send_sms_message(phone, message_data.message, settings)
            result['sms'] = sms_result
            if sms_result.get('success'):
                successful += 1
            else:
                failed += 1
        
        if message_data.channel in ['whatsapp', 'both']:
            wa_result = await send_whatsapp_message(phone, message_data.message, settings)
            result['whatsapp'] = wa_result
            if message_data.channel == 'whatsapp':
                if wa_result.get('success'):
                    successful += 1
                else:
                    failed += 1
        
        results.append(result)
    
    # Update message log
    await db.message_logs.update_one(
        {'id': message_log['id']},
        {'$set': {
            'successful_count': successful,
            'failed_count': failed,
            'status': 'completed',
            'results': results[:100],  # Store first 100 results for reference
            'completed_at': datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Check if it was simulated
    is_simulated = not settings.get('sms_api_key') and not settings.get('whatsapp_api_key')
    
    return {
        'message_log_id': message_log['id'],
        'channel': message_data.channel,
        'recipient_count': len(recipients),
        'successful_count': successful,
        'failed_count': failed,
        'status': 'completed',
        'simulated': is_simulated,
        'note': 'Messages simulated - configure API credentials in Settings to send real messages' if is_simulated else None
    }

@router.get("/messaging/logs")
async def get_message_logs(
    limit: int = 50,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get message sending history (admin only)"""
    user = await get_current_user(credentials)
    
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    logs = await db.message_logs.find().sort('created_at', -1).limit(limit).to_list(limit)
    
    result = []
    for log in logs:
        result.append({
            'id': log['id'],
            'channel': log['channel'],
            'message': log['message'][:100] + '...' if len(log.get('message', '')) > 100 else log.get('message', ''),
            'recipient_filter': log.get('recipient_filter', 'all'),
            'recipient_count': log.get('recipient_count', 0),
            'successful_count': log.get('successful_count', 0),
            'failed_count': log.get('failed_count', 0),
            'status': log.get('status', 'unknown'),
            'created_at': log.get('created_at', '')
        })
    
    return result

@router.get("/messaging/logs/{log_id}")
async def get_message_log_detail(
    log_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get detailed message log (admin only)"""
    user = await get_current_user(credentials)
    
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    log = await db.message_logs.find_one({'id': log_id})
    
    if not log:
        raise HTTPException(status_code=404, detail="Message log not found")
    
    return {
        'id': log['id'],
        'channel': log['channel'],
        'message': log.get('message', ''),
        'recipient_filter': log.get('recipient_filter', 'all'),
        'warehouse_id': log.get('warehouse_id'),
        'category': log.get('category'),
        'recipient_count': log.get('recipient_count', 0),
        'successful_count': log.get('successful_count', 0),
        'failed_count': log.get('failed_count', 0),
        'status': log.get('status', 'unknown'),
        'results': log.get('results', []),
        'created_at': log.get('created_at', ''),
        'completed_at': log.get('completed_at')
    }
