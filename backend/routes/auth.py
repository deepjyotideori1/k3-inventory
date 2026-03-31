from fastapi import APIRouter, HTTPException, Depends
from database import db
from deps import get_current_user, require_admin, security
from helpers import hash_password, verify_password, create_token
from models import (
    UserLogin, UserCreate, UserResponse, LoginResponse,
    ResetPasswordRequest, PasswordChangeRequest,
    SettingsResponse, SettingsUpdate
)
from typing import List
from datetime import datetime, timezone
import uuid

router = APIRouter()

# ============ AUTH ROUTES ============

@router.post("/auth/login", response_model=LoginResponse)
async def login(data: UserLogin):
    # Check maintenance mode
    settings = await db.settings.find_one({'key': 'app_settings'}, {'_id': 0})
    
    user = await db.users.find_one({'email': data.email}, {'_id': 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(data.password, user['password']):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Check maintenance mode for non-admin users
    if settings and settings.get('maintenance_mode') and user['role'] != 'admin':
        raise HTTPException(status_code=503, detail=settings.get('maintenance_message', 'System under maintenance'))
    
    token = create_token(user['id'], user['email'], user['role'])
    
    # Get warehouse name if applicable
    warehouse_name = None
    if user.get('warehouse_id'):
        warehouse = await db.warehouses.find_one({'id': user['warehouse_id']}, {'_id': 0})
        if warehouse:
            warehouse_name = warehouse['name']
    
    return LoginResponse(
        token=token,
        user=UserResponse(
            id=user['id'],
            email=user['email'],
            name=user['name'],
            role=user['role'],
            warehouse_id=user.get('warehouse_id'),
            warehouse_name=warehouse_name,
            created_at=user['created_at']
        )
    )

@router.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    warehouse_name = None
    if user.get('warehouse_id'):
        warehouse = await db.warehouses.find_one({'id': user['warehouse_id']}, {'_id': 0})
        if warehouse:
            warehouse_name = warehouse['name']
    
    return UserResponse(
        id=user['id'],
        email=user['email'],
        name=user['name'],
        role=user['role'],
        warehouse_id=user.get('warehouse_id'),
        warehouse_name=warehouse_name,
        created_at=user['created_at']
    )

@router.post("/auth/change-password")
async def change_password(data: PasswordChangeRequest, user: dict = Depends(get_current_user)):
    if not verify_password(data.current_password, user['password']):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    new_hash = hash_password(data.new_password)
    await db.users.update_one({'id': user['id']}, {'$set': {'password': new_hash}})
    
    return {"message": "Password changed successfully"}

# ============ SETTINGS ROUTES ============

@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    settings = await db.settings.find_one({'key': 'app_settings'}, {'_id': 0})
    if not settings:
        return SettingsResponse(maintenance_mode=False, maintenance_message='', app_version='1.0.0')
    return SettingsResponse(
        maintenance_mode=settings.get('maintenance_mode', False),
        maintenance_message=settings.get('maintenance_message', ''),
        app_version=settings.get('app_version', '1.0.0')
    )

@router.put("/settings", response_model=SettingsResponse)
async def update_settings(data: SettingsUpdate, user: dict = Depends(require_admin)):
    update_data = {}
    if data.maintenance_mode is not None:
        update_data['maintenance_mode'] = data.maintenance_mode
    if data.maintenance_message is not None:
        update_data['maintenance_message'] = data.maintenance_message
    
    await db.settings.update_one({'key': 'app_settings'}, {'$set': update_data})
    
    settings = await db.settings.find_one({'key': 'app_settings'}, {'_id': 0})
    return SettingsResponse(
        maintenance_mode=settings.get('maintenance_mode', False),
        maintenance_message=settings.get('maintenance_message', ''),
        app_version=settings.get('app_version', '1.0.0')
    )

# ============ USER MANAGEMENT ROUTES ============

@router.get("/users", response_model=List[UserResponse])
async def get_users(user: dict = Depends(require_admin)):
    # Batch fetch warehouses to avoid N+1 queries
    warehouses_list = await db.warehouses.find({}, {'_id': 0}).to_list(1000)
    warehouses_dict = {w['id']: w for w in warehouses_list}
    
    users = await db.users.find({}, {'_id': 0, 'password': 0}).to_list(1000)
    result = []
    for u in users:
        warehouse_name = None
        if u.get('warehouse_id') and u['warehouse_id'] in warehouses_dict:
            warehouse_name = warehouses_dict[u['warehouse_id']]['name']
        result.append(UserResponse(
            id=u['id'],
            email=u['email'],
            name=u['name'],
            role=u['role'],
            warehouse_id=u.get('warehouse_id'),
            warehouse_name=warehouse_name,
            created_at=u['created_at'],
            visible_password=u.get('visible_password')
        ))
    return result

@router.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate, user: dict = Depends(require_admin)):
    existing = await db.users.find_one({'email': data.email}, {'_id': 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Validate warehouse assignment for sales_executive
    if data.role == 'sales_executive':
        if not data.warehouse_id:
            raise HTTPException(status_code=400, detail="Sales Executive must be assigned to a warehouse")
        warehouse = await db.warehouses.find_one({'id': data.warehouse_id}, {'_id': 0})
        if not warehouse:
            raise HTTPException(status_code=400, detail="Warehouse not found")
        if warehouse.get('is_plant'):
            raise HTTPException(status_code=400, detail="Sales Executive cannot be assigned to Plant Hollongi")
    
    # Validate warehouse assignment for warehouse_manager
    if data.role == 'warehouse_manager' and not data.warehouse_id:
        raise HTTPException(status_code=400, detail="Warehouse Manager must be assigned to a warehouse")
    
    new_user = {
        'id': str(uuid.uuid4()),
        'email': data.email,
        'password': hash_password(data.password),
        'visible_password': data.password,  # Store visible password for admin reference
        'name': data.name,
        'role': data.role,
        'warehouse_id': data.warehouse_id,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(new_user)
    
    warehouse_name = None
    if data.warehouse_id:
        warehouse = await db.warehouses.find_one({'id': data.warehouse_id}, {'_id': 0})
        if warehouse:
            warehouse_name = warehouse['name']
    
    return UserResponse(
        id=new_user['id'],
        email=new_user['email'],
        name=new_user['name'],
        role=new_user['role'],
        warehouse_id=new_user.get('warehouse_id'),
        warehouse_name=warehouse_name,
        created_at=new_user['created_at'],
        visible_password=new_user['visible_password']
    )

@router.delete("/users/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(require_admin)):
    result = await db.users.delete_one({'id': user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}

@router.post("/users/{user_id}/reset-password")
async def reset_user_password(user_id: str, data: ResetPasswordRequest = None, user: dict = Depends(require_admin)):
    """Reset a user's password - Admin only"""
    target_user = await db.users.find_one({'id': user_id}, {'_id': 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate new password if not provided
    if data and data.new_password:
        new_password = data.new_password
    else:
        # Auto-generate password based on user's name
        name_part = target_user['name'].split()[0] if target_user['name'] else 'User'
        new_password = f"{name_part}@123"
    
    # Hash and update password
    hashed = hash_password(new_password)
    await db.users.update_one(
        {'id': user_id},
        {'$set': {
            'password': hashed,
            'visible_password': new_password,
            'password_reset_at': datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {
        "message": "Password reset successfully",
        "new_password": new_password,
        "user_email": target_user['email']
    }

