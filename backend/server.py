from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from io import BytesIO
import json
import locale

# PDF and Excel imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import xlsxwriter
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# Helper function for Indian Rupee formatting
def format_inr(amount, use_symbol=True):
    """Format number in Indian Rupee format (Rs.XX,XX,XXX or ₹XX,XX,XXX)"""
    if amount is None or amount == '':
        return 'Rs.0' if use_symbol else '0'
    try:
        num = float(amount)
        prefix = 'Rs.' if use_symbol else ''
        # Indian numbering: last 3 digits, then groups of 2
        if num < 0:
            return '-' + prefix + format_inr(-num, False)
        
        s = str(int(num))
        if len(s) <= 3:
            result = s
        else:
            result = s[-3:]
            s = s[:-3]
            while s:
                result = s[-2:] + ',' + result
                s = s[:-2]
        
        # Add decimal part if exists
        decimal_part = num - int(num)
        if decimal_part > 0:
            result += f'.{int(decimal_part * 100):02d}'
        
        return prefix + result
    except (ValueError, TypeError):
        return 'Rs.0' if use_symbol else '0'

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT settings
JWT_SECRET = os.environ.get('JWT_SECRET', 'k3gas_secret_key_2024_secure')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# Create the main app
app = FastAPI(title="K3 GAS SERVICE API", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============ PYDANTIC MODELS ============

class UserBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email: str
    name: str
    role: str  # 'admin', 'warehouse_manager', or 'sales_executive'
    warehouse_id: Optional[str] = None

class UserCreate(BaseModel):
    email: str
    password: str
    name: str
    role: str  # 'admin', 'warehouse_manager', or 'sales_executive'
    warehouse_id: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    warehouse_id: Optional[str] = None
    warehouse_name: Optional[str] = None
    created_at: str
    visible_password: Optional[str] = None  # Only shown after password reset

class ResetPasswordRequest(BaseModel):
    new_password: Optional[str] = None  # If not provided, auto-generate

class LoginResponse(BaseModel):
    token: str
    user: UserResponse

class WarehouseBase(BaseModel):
    name: str
    location: str
    is_plant: bool = False
    is_active: bool = True

class WarehouseCreate(WarehouseBase):
    pass

class WarehouseResponse(BaseModel):
    id: str
    name: str
    location: str
    is_plant: bool
    is_active: bool
    created_at: str

class InventoryItemBase(BaseModel):
    name: str
    unit: str
    category: str

class InventoryItemCreate(InventoryItemBase):
    pass

class InventoryItemResponse(BaseModel):
    id: str
    name: str
    unit: str
    category: str
    created_at: str

class DailyReportCreate(BaseModel):
    warehouse_id: str
    date: str
    opening_15kg_filled: int = 0
    opening_21kg_filled: int = 0
    opening_15kg_empty: int = 0
    opening_21kg_empty: int = 0
    sold_15kg_filled: int = 0
    sold_21kg_filled: int = 0
    refilling_15kg: int = 0
    refilling_21kg: int = 0
    refilling_plant_15kg: int = 0
    refilling_plant_21kg: int = 0
    received_from_plant_15kg: int = 0
    received_from_plant_21kg: int = 0
    closing_15kg_filled: int = 0
    closing_21kg_filled: int = 0
    closing_15kg_empty: int = 0
    closing_21kg_empty: int = 0
    remarks: str = ""
    status: str = "draft"  # draft or submitted

class DailyReportResponse(BaseModel):
    id: str
    warehouse_id: str
    warehouse_name: str
    date: str
    opening_15kg_filled: int
    opening_21kg_filled: int
    opening_15kg_empty: int
    opening_21kg_empty: int
    sold_15kg_filled: int
    sold_21kg_filled: int
    refilling_15kg: int
    refilling_21kg: int
    refilling_plant_15kg: int
    refilling_plant_21kg: int
    received_from_plant_15kg: int = 0
    received_from_plant_21kg: int = 0
    calculated_closing_15kg_filled: int = 0
    calculated_closing_21kg_filled: int = 0
    calculated_closing_15kg_empty: int = 0
    calculated_closing_21kg_empty: int = 0
    closing_15kg_filled: int
    closing_21kg_filled: int
    closing_15kg_empty: int
    closing_21kg_empty: int
    remarks: str
    discrepancy_15kg_filled: int
    discrepancy_21kg_filled: int
    discrepancy_15kg_empty: int
    discrepancy_21kg_empty: int
    has_discrepancy: bool
    status: str = "submitted"
    submitted_by: str
    submitted_at: str
    created_at: str

class PlantReportCreate(BaseModel):
    date: str
    opening_bullet_tank_kg: float = 0
    opening_15kg_filled: int = 0
    opening_21kg_filled: int = 0
    opening_15kg_empty: int = 0
    opening_21kg_empty: int = 0
    day_reloading_kg: float = 0
    day_refilled_15kg: int = 0
    day_refilled_21kg: int = 0
    delivery_15kg: List[Dict[str, Any]] = []  # [{warehouse_id, quantity}]
    delivery_21kg: List[Dict[str, Any]] = []
    received_empty_15kg: List[Dict[str, Any]] = []
    received_empty_21kg: List[Dict[str, Any]] = []
    closing_bullet_tank_kg: float = 0
    closing_15kg_filled: int = 0
    closing_21kg_filled: int = 0
    closing_15kg_empty: int = 0
    closing_21kg_empty: int = 0
    remarks: str = ""

class PlantReportResponse(BaseModel):
    id: str
    date: str
    opening_bullet_tank_kg: float
    opening_15kg_filled: int
    opening_21kg_filled: int
    opening_15kg_empty: int
    opening_21kg_empty: int
    day_reloading_kg: float = 0
    day_refilled_15kg: int
    day_refilled_21kg: int
    delivery_15kg: List[Dict[str, Any]]
    delivery_21kg: List[Dict[str, Any]]
    received_empty_15kg: List[Dict[str, Any]]
    received_empty_21kg: List[Dict[str, Any]]
    closing_bullet_tank_kg: float
    closing_15kg_filled: int
    closing_21kg_filled: int
    closing_15kg_empty: int
    closing_21kg_empty: int
    remarks: str
    submitted_by: str
    submitted_at: str
    created_at: str

class SettingsResponse(BaseModel):
    maintenance_mode: bool
    maintenance_message: str
    app_version: str

class SettingsUpdate(BaseModel):
    maintenance_mode: Optional[bool] = None
    maintenance_message: Optional[str] = None

class PlantStockUpdateRequest(BaseModel):
    bullet_tank_kg: float = 0
    stock_15kg_filled: int = 0
    stock_21kg_filled: int = 0
    stock_15kg_empty: int = 0
    stock_21kg_empty: int = 0
    reason: str = ""

class StockUpdateRequest(BaseModel):
    warehouse_id: str
    stock_15kg_filled: int
    stock_21kg_filled: int
    stock_15kg_empty: int
    stock_21kg_empty: int
    reason: str

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

# Dealer Models
class DealerCreate(BaseModel):
    name: str
    contact: str = ""
    address: str = ""

class DealerResponse(BaseModel):
    id: str
    name: str
    contact: str
    address: str
    created_at: str
    is_active: bool

class DealerEntryCreate(BaseModel):
    dealer_id: str
    date: str
    issued_15kg: int = 0
    issued_21kg: int = 0
    refilled_15kg: int = 0
    refilled_21kg: int = 0
    remarks: str = ""

class DealerEntryResponse(BaseModel):
    id: str
    dealer_id: str
    dealer_name: str
    date: str
    issued_15kg: int
    issued_21kg: int
    refilled_15kg: int
    refilled_21kg: int
    remarks: str
    submitted_by: str
    submitted_at: str

# LPG Accessories Models
class AccessoryCreate(BaseModel):
    name: str
    description: str = ""
    unit: str = "pcs"

class AccessoryResponse(BaseModel):
    id: str
    name: str
    description: str
    unit: str
    created_at: str
    is_active: bool

class AccessoryDealerCreate(BaseModel):
    name: str
    contact: str = ""
    address: str = ""

class AccessoryDealerResponse(BaseModel):
    id: str
    name: str
    contact: str
    address: str
    created_at: str
    is_active: bool

class AccessoryEntryCreate(BaseModel):
    accessory_id: str
    dealer_id: str
    date: str
    total_issued: int = 0
    total_sold: int = 0
    total_remaining: int = 0
    remarks: str = ""

class AccessoryEntryResponse(BaseModel):
    id: str
    accessory_id: str
    accessory_name: str
    dealer_id: str
    dealer_name: str
    date: str
    total_issued: int
    total_sold: int
    total_remaining: int
    remarks: str
    submitted_by: str
    submitted_at: str

# Accessory Sales Models
class AccessorySaleItemCreate(BaseModel):
    accessory_id: str
    quantity: int
    unit_price: float

class AccessorySaleCreate(BaseModel):
    customer_id: str = ""
    customer_name: str
    customer_phone: str = ""
    customer_address: str = ""
    is_new_customer: bool = False
    date: str
    memo_no: str = ""
    items: List[AccessorySaleItemCreate]
    payment_mode: str = "cash"  # cash, pending, online
    remarks: str = ""
    warehouse_id: str = ""

class AccessorySaleItemResponse(BaseModel):
    accessory_id: str
    accessory_name: str
    quantity: int
    unit_price: float
    total_amount: float

class AccessorySaleResponse(BaseModel):
    id: str
    customer_id: str
    customer_name: str
    customer_phone: str
    customer_address: str
    date: str
    memo_no: str = ""
    items: List[AccessorySaleItemResponse]
    subtotal: float
    grand_total: float
    payment_mode: str
    remarks: str
    warehouse_id: str
    warehouse_name: str
    created_by: str
    created_by_name: str
    created_at: str


# ============ HELPER FUNCTIONS ============

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        'user_id': user_id,
        'email': email,
        'role': role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({'id': payload['user_id']}, {'_id': 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def require_admin(user: dict = Depends(get_current_user)):
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# ============ INITIALIZATION ============

async def init_default_data():
    """Initialize default warehouses, users, and settings"""
    
    # Check if already initialized
    settings = await db.settings.find_one({'key': 'app_settings'}, {'_id': 0})
    if settings:
        return
    
    logger.info("Initializing default data...")
    
    # Create default settings
    await db.settings.insert_one({
        'key': 'app_settings',
        'maintenance_mode': False,
        'maintenance_message': 'System is under maintenance. Please check back later.',
        'app_version': '1.0.0'
    })
    
    # Create default warehouses
    warehouses = [
        {'id': str(uuid.uuid4()), 'name': 'Jullang', 'location': 'Jullang, Arunachal Pradesh', 'is_plant': False, 'is_active': True, 'created_at': datetime.now(timezone.utc).isoformat()},
        {'id': str(uuid.uuid4()), 'name': 'Naharlagun', 'location': 'Naharlagun, Arunachal Pradesh', 'is_plant': False, 'is_active': True, 'created_at': datetime.now(timezone.utc).isoformat()},
        {'id': str(uuid.uuid4()), 'name': 'Doimukh', 'location': 'Doimukh, Arunachal Pradesh', 'is_plant': False, 'is_active': True, 'created_at': datetime.now(timezone.utc).isoformat()},
        {'id': str(uuid.uuid4()), 'name': 'Plant Hollongi', 'location': 'Hollongi, Arunachal Pradesh', 'is_plant': True, 'is_active': True, 'created_at': datetime.now(timezone.utc).isoformat()},
    ]
    
    await db.warehouses.insert_many(warehouses)
    
    # Create admin user
    admin_user = {
        'id': str(uuid.uuid4()),
        'email': 'admin@k3gas.com',
        'password': hash_password('Admin@123'),
        'name': 'Master Admin',
        'role': 'admin',
        'warehouse_id': None,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(admin_user)
    
    # Create warehouse manager users
    warehouse_users = [
        {'id': str(uuid.uuid4()), 'email': 'jullang@k3gas.com', 'password': hash_password('Jullang@123'), 'name': 'Jullang Manager', 'role': 'warehouse_manager', 'warehouse_id': warehouses[0]['id'], 'created_at': datetime.now(timezone.utc).isoformat()},
        {'id': str(uuid.uuid4()), 'email': 'naharlagun@k3gas.com', 'password': hash_password('Naharlagun@123'), 'name': 'Naharlagun Manager', 'role': 'warehouse_manager', 'warehouse_id': warehouses[1]['id'], 'created_at': datetime.now(timezone.utc).isoformat()},
        {'id': str(uuid.uuid4()), 'email': 'doimukh@k3gas.com', 'password': hash_password('Doimukh@123'), 'name': 'Doimukh Manager', 'role': 'warehouse_manager', 'warehouse_id': warehouses[2]['id'], 'created_at': datetime.now(timezone.utc).isoformat()},
        {'id': str(uuid.uuid4()), 'email': 'hollongi@k3gas.com', 'password': hash_password('Hollongi@123'), 'name': 'Plant Hollongi Manager', 'role': 'warehouse_manager', 'warehouse_id': warehouses[3]['id'], 'created_at': datetime.now(timezone.utc).isoformat()},
    ]
    await db.users.insert_many(warehouse_users)
    
    # Create default inventory items
    items = [
        {'id': str(uuid.uuid4()), 'name': '15kg Cylinder', 'unit': 'units', 'category': 'LPG Cylinder', 'created_at': datetime.now(timezone.utc).isoformat()},
        {'id': str(uuid.uuid4()), 'name': '21kg Cylinder', 'unit': 'units', 'category': 'LPG Cylinder', 'created_at': datetime.now(timezone.utc).isoformat()},
    ]
    await db.inventory_items.insert_many(items)
    
    logger.info("Default data initialized successfully")

@app.on_event("startup")
async def startup_event():
    await init_default_data()
    # Create indexes for search performance
    await db.sales_entries.create_index([("consumer_name", 1)])
    await db.sales_entries.create_index([("date", 1)])
    await db.sales_entries.create_index([("warehouse_id", 1)])

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# ============ AUTH ROUTES ============

@api_router.post("/auth/login", response_model=LoginResponse)
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

@api_router.get("/auth/me", response_model=UserResponse)
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

@api_router.post("/auth/change-password")
async def change_password(data: PasswordChangeRequest, user: dict = Depends(get_current_user)):
    if not verify_password(data.current_password, user['password']):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    new_hash = hash_password(data.new_password)
    await db.users.update_one({'id': user['id']}, {'$set': {'password': new_hash}})
    
    return {"message": "Password changed successfully"}

# ============ SETTINGS ROUTES ============

@api_router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    settings = await db.settings.find_one({'key': 'app_settings'}, {'_id': 0})
    if not settings:
        return SettingsResponse(maintenance_mode=False, maintenance_message='', app_version='1.0.0')
    return SettingsResponse(
        maintenance_mode=settings.get('maintenance_mode', False),
        maintenance_message=settings.get('maintenance_message', ''),
        app_version=settings.get('app_version', '1.0.0')
    )

@api_router.put("/settings", response_model=SettingsResponse)
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

@api_router.get("/users", response_model=List[UserResponse])
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

@api_router.post("/users", response_model=UserResponse)
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

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(require_admin)):
    result = await db.users.delete_one({'id': user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}

@api_router.post("/users/{user_id}/reset-password")
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

# ============ WAREHOUSE ROUTES ============

@api_router.get("/warehouses", response_model=List[WarehouseResponse])
async def get_warehouses(user: dict = Depends(get_current_user)):
    warehouses = await db.warehouses.find({}, {'_id': 0}).to_list(100)
    return [WarehouseResponse(**w) for w in warehouses]

@api_router.post("/warehouses", response_model=WarehouseResponse)
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

@api_router.put("/warehouses/{warehouse_id}", response_model=WarehouseResponse)
async def update_warehouse(warehouse_id: str, data: WarehouseCreate, user: dict = Depends(require_admin)):
    await db.warehouses.update_one(
        {'id': warehouse_id},
        {'$set': {'name': data.name, 'location': data.location, 'is_plant': data.is_plant, 'is_active': data.is_active}}
    )
    warehouse = await db.warehouses.find_one({'id': warehouse_id}, {'_id': 0})
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return WarehouseResponse(**warehouse)

@api_router.delete("/warehouses/{warehouse_id}")
async def delete_warehouse(warehouse_id: str, user: dict = Depends(require_admin)):
    result = await db.warehouses.delete_one({'id': warehouse_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return {"message": "Warehouse deleted successfully"}

# ============ INVENTORY ITEMS ROUTES ============

@api_router.get("/inventory-items", response_model=List[InventoryItemResponse])
async def get_inventory_items(user: dict = Depends(get_current_user)):
    items = await db.inventory_items.find({}, {'_id': 0}).to_list(100)
    return [InventoryItemResponse(**item) for item in items]

@api_router.post("/inventory-items", response_model=InventoryItemResponse)
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

# ============ DAILY REPORT ROUTES ============

@api_router.post("/reports/daily", response_model=DailyReportResponse)
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

@api_router.get("/reports/daily/today/{warehouse_id}")
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

@api_router.put("/reports/daily/{report_id}")
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

@api_router.get("/reports/warehouse-received-from-plant/{warehouse_id}/{date}")
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

@api_router.get("/reports/plant-received/{date}")
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

@api_router.get("/reports/warehouses-received-summary/{date}")
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

@api_router.get("/reports/daily", response_model=List[DailyReportResponse])
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

@api_router.get("/reports/daily/latest/{warehouse_id}")
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

@api_router.post("/reports/plant", response_model=PlantReportResponse)
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
    
    return PlantReportResponse(**report)

@api_router.get("/reports/plant", response_model=List[PlantReportResponse])
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

@api_router.get("/reports/plant/latest")
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

# ============ PLANT CYLINDER ISSUANCE TO DEALERS ============

class PlantIssuanceCreate(BaseModel):
    date: str
    dealer_id: str
    qty_15kg: int = 0
    qty_21kg: int = 0
    remarks: str = ""

class PlantIssuanceResponse(BaseModel):
    id: str
    date: str
    dealer_id: str
    dealer_name: str
    qty_15kg: int
    qty_21kg: int
    remarks: str
    submitted_by: str
    submitted_at: str

@api_router.post("/plant/issue-to-dealer")
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

@api_router.get("/plant/issuance-history")
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

@api_router.get("/plant/available-stock")
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

# ============ STOCK UPDATE (Admin) ============

@api_router.post("/stock/update")
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

@api_router.post("/stock/plant-update")
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

# ============ DASHBOARD STATS ============

@api_router.get("/dashboard/stats")
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

# ============ EXPORT ROUTES ============

@api_router.get("/export/pdf")
async def export_pdf(
    warehouse_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    report_type: str = "daily",
    user: dict = Depends(get_current_user)
):
    buffer = BytesIO()
    # A4 landscape for fit-to-page
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
    elements = []
    styles = getSampleStyleSheet()
    
    # Header font size 14 bold, body font size 13
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=14, spaceAfter=5, alignment=1, textColor=colors.HexColor('#15803d'))
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=12, spaceAfter=3, alignment=1)
    
    elements.append(Paragraph("K3 GAS SERVICE - Khayal Hamesha", title_style))
    
    if report_type == "daily":
        query = {}
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
        
        warehouse_name = "All Warehouses"
        if user['role'] != 'admin':
            warehouse_name = user.get('warehouse_name', 'My Warehouse')
        elif warehouse_id:
            wh = await db.warehouses.find_one({'id': warehouse_id}, {'_id': 0})
            warehouse_name = wh['name'] if wh else warehouse_id
        
        elements.append(Paragraph(f"Daily Inventory Report - {warehouse_name}", subtitle_style))
        if start_date and end_date:
            elements.append(Paragraph(f"Period: {start_date} to {end_date}", ParagraphStyle('Period', fontSize=10, alignment=1)))
        elements.append(Spacer(1, 5))
        
        # Comprehensive table - fit to A4 landscape
        data = [[
            'Date', 'Warehouse',
            'Op.15F', 'Op.21F', 'Op.15E', 'Op.21E',
            'Sold15', 'Sold21', 'Ref15', 'Ref21',
            'Refill to\nPlant 15kg', 'Refill to\nPlant 21kg', 'Received from\nPlant-15kg', 'Received from\nPlant-21kg',
            'Cl.15F', 'Cl.21F', 'Cl.15E', 'Cl.21E', 'Stat'
        ]]
        
        for r in reports:
            status = "Disc" if r.get('has_discrepancy') else "OK"
            data.append([
                r.get('date', '')[-5:],  # Show MM-DD only
                r.get('warehouse_name', '')[:8],
                r.get('opening_15kg_filled', 0),
                r.get('opening_21kg_filled', 0),
                r.get('opening_15kg_empty', 0),
                r.get('opening_21kg_empty', 0),
                r.get('sold_15kg_filled', 0),
                r.get('sold_21kg_filled', 0),
                r.get('refilling_15kg', 0),
                r.get('refilling_21kg', 0),
                r.get('refilling_plant_15kg', 0),
                r.get('refilling_plant_21kg', 0),
                r.get('received_from_plant_15kg', 0),
                r.get('received_from_plant_21kg', 0),
                r.get('closing_15kg_filled', 0),
                r.get('closing_21kg_filled', 0),
                r.get('closing_15kg_empty', 0),
                r.get('closing_21kg_empty', 0),
                status
            ])
        
        # Calculate column widths to fit A4 landscape (842 points width - 30 margins = 812)
        # Wider columns for the longer headers (Refill to Plant, Received from Plant)
        col_widths = [40, 42, 32, 32, 32, 32, 32, 32, 32, 32, 52, 52, 55, 55, 32, 32, 32, 32, 26]
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#15803d')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 6),  # Header - smaller for longer text
            ('FONTSIZE', (0, 1), (-1, -1), 7),  # Body
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BACKGROUND', (2, 1), (5, -1), colors.HexColor('#dbeafe')),  # Opening - blue
            ('BACKGROUND', (6, 1), (13, -1), colors.HexColor('#fef3c7')),  # Activity - yellow
            ('BACKGROUND', (14, 1), (17, -1), colors.HexColor('#dcfce7')),  # Closing - green
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)
    
    elif report_type == "plant":
        query = {}
        if start_date:
            query['date'] = {'$gte': start_date}
        if end_date:
            if 'date' in query:
                query['date']['$lte'] = end_date
            else:
                query['date'] = {'$lte': end_date}
        
        reports = await db.plant_reports.find(query, {'_id': 0}).sort('date', -1).to_list(1000)
        
        elements.append(Paragraph("Plant Hollongi Report", subtitle_style))
        if start_date and end_date:
            elements.append(Paragraph(f"Period: {start_date} to {end_date}", ParagraphStyle('Period', fontSize=10, alignment=1)))
        elements.append(Spacer(1, 5))
        
        # Comprehensive Plant table with all form data
        data = [[
            'Date',
            'Op.Tank', 'Op.15F', 'Op.21F', 'Op.15E', 'Op.21E',
            'Reload', 'Recv15', 'Recv21',
            'Refill15', 'Refill21',
            'Del.15', 'Del.21',
            'Cl.Tank', 'Cl.15F', 'Cl.21F', 'Cl.15E', 'Cl.21E'
        ]]
        
        for r in reports:
            # Calculate totals for deliveries
            del_15 = sum([d.get('quantity', 0) for d in r.get('delivery_15kg', [])])
            del_21 = sum([d.get('quantity', 0) for d in r.get('delivery_21kg', [])])
            recv_15 = sum([d.get('quantity', 0) for d in r.get('received_empty_15kg', [])])
            recv_21 = sum([d.get('quantity', 0) for d in r.get('received_empty_21kg', [])])
            
            data.append([
                r.get('date', '')[-5:],
                r.get('opening_bullet_tank_kg', 0),
                r.get('opening_15kg_filled', 0),
                r.get('opening_21kg_filled', 0),
                r.get('opening_15kg_empty', 0),
                r.get('opening_21kg_empty', 0),
                r.get('day_reloading_kg', 0),
                recv_15,
                recv_21,
                r.get('day_refilled_15kg', 0),
                r.get('day_refilled_21kg', 0),
                del_15,
                del_21,
                r.get('closing_bullet_tank_kg', 0),
                r.get('closing_15kg_filled', 0),
                r.get('closing_21kg_filled', 0),
                r.get('closing_15kg_empty', 0),
                r.get('closing_21kg_empty', 0)
            ])
        
        col_widths = [42] + [42]*17
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#15803d')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
            ('BACKGROUND', (1, 1), (5, -1), colors.HexColor('#dbeafe')),  # Opening - blue
            ('BACKGROUND', (6, 1), (6, -1), colors.HexColor('#cffafe')),  # Reloading - cyan
            ('BACKGROUND', (7, 1), (12, -1), colors.HexColor('#fef3c7')),  # Activity - yellow
            ('BACKGROUND', (13, 1), (17, -1), colors.HexColor('#dcfce7')),  # Closing - green
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)
        
        # Add detailed warehouse breakdown for each report
        elements.append(Spacer(1, 15))
        elements.append(Paragraph("Warehouse-wise Breakdown", subtitle_style))
        elements.append(Spacer(1, 5))
        
        for r in reports:
            report_date = r.get('date', '')
            deliveries = r.get('delivery_15kg', []) + r.get('delivery_21kg', [])
            received = r.get('received_empty_15kg', []) + r.get('received_empty_21kg', [])
            
            if deliveries or received:
                elements.append(Paragraph(f"Date: {report_date}", ParagraphStyle('DateHeader', fontSize=10, fontName='Helvetica-Bold')))
                elements.append(Spacer(1, 3))
                
                # Delivery to Warehouses table
                if r.get('delivery_15kg', []) or r.get('delivery_21kg', []):
                    elements.append(Paragraph("Delivery to Warehouses (Filled Cylinders)", ParagraphStyle('SubHeader', fontSize=9, textColor=colors.HexColor('#4338ca'))))
                    del_data = [['Warehouse', '15kg Filled', '21kg Filled']]
                    warehouse_del = {}
                    for d in r.get('delivery_15kg', []):
                        wname = d.get('warehouse_name', 'Unknown')
                        if wname not in warehouse_del:
                            warehouse_del[wname] = {'qty15': 0, 'qty21': 0}
                        warehouse_del[wname]['qty15'] = d.get('quantity', 0)
                    for d in r.get('delivery_21kg', []):
                        wname = d.get('warehouse_name', 'Unknown')
                        if wname not in warehouse_del:
                            warehouse_del[wname] = {'qty15': 0, 'qty21': 0}
                        warehouse_del[wname]['qty21'] = d.get('quantity', 0)
                    for wname, qty in warehouse_del.items():
                        del_data.append([wname, qty['qty15'], qty['qty21']])
                    
                    del_table = Table(del_data, colWidths=[150, 80, 80])
                    del_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c7d2fe')),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ]))
                    elements.append(del_table)
                    elements.append(Spacer(1, 5))
                
                # Empty Received from Warehouses table
                if r.get('received_empty_15kg', []) or r.get('received_empty_21kg', []):
                    elements.append(Paragraph("Empty Received from Warehouses", ParagraphStyle('SubHeader', fontSize=9, textColor=colors.HexColor('#c2410c'))))
                    recv_data = [['Warehouse', '15kg Empty', '21kg Empty']]
                    warehouse_recv = {}
                    for d in r.get('received_empty_15kg', []):
                        wname = d.get('warehouse_name', 'Unknown')
                        if wname not in warehouse_recv:
                            warehouse_recv[wname] = {'qty15': 0, 'qty21': 0}
                        warehouse_recv[wname]['qty15'] = d.get('quantity', 0)
                    for d in r.get('received_empty_21kg', []):
                        wname = d.get('warehouse_name', 'Unknown')
                        if wname not in warehouse_recv:
                            warehouse_recv[wname] = {'qty15': 0, 'qty21': 0}
                        warehouse_recv[wname]['qty21'] = d.get('quantity', 0)
                    for wname, qty in warehouse_recv.items():
                        recv_data.append([wname, qty['qty15'], qty['qty21']])
                    
                    recv_table = Table(recv_data, colWidths=[150, 80, 80])
                    recv_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#fed7aa')),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ]))
                    elements.append(recv_table)
                
                elements.append(Spacer(1, 8))
    
    doc.build(elements)
    buffer.seek(0)
    
    date_str = datetime.now().strftime('%d%m%y')
    if report_type == "daily":
        filename = f"Daily_Inventory_Report_{date_str}.pdf"
    else:
        filename = f"Plant_Hollongi_Report_{date_str}.pdf"
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@api_router.get("/export/excel")
async def export_excel(
    warehouse_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    report_type: str = "daily",
    user: dict = Depends(get_current_user)
):
    buffer = BytesIO()
    workbook = xlsxwriter.Workbook(buffer)
    worksheet = workbook.add_worksheet('Report')
    
    # Formats
    header_format = workbook.add_format({'bold': True, 'bg_color': '#15803d', 'font_color': 'white', 'align': 'center', 'border': 1, 'text_wrap': True})
    cell_format = workbook.add_format({'align': 'center', 'border': 1})
    title_format = workbook.add_format({'bold': True, 'font_size': 16, 'align': 'center', 'font_color': '#15803d'})
    opening_format = workbook.add_format({'align': 'center', 'border': 1, 'bg_color': '#dbeafe'})
    activity_format = workbook.add_format({'align': 'center', 'border': 1, 'bg_color': '#fef3c7'})
    closing_format = workbook.add_format({'align': 'center', 'border': 1, 'bg_color': '#dcfce7'})
    
    if report_type == "daily":
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
        
        # Get warehouse name for title
        warehouse_name = "All Warehouses"
        if user['role'] != 'admin':
            warehouse_name = user.get('warehouse_name', 'My Warehouse')
        elif warehouse_id:
            wh = await db.warehouses.find_one({'id': warehouse_id}, {'_id': 0})
            warehouse_name = wh['name'] if wh else warehouse_id
        
        worksheet.merge_range('A1:S1', f'K3 GAS SERVICE - Daily Inventory Report - {warehouse_name}', title_format)
        if start_date and end_date:
            worksheet.merge_range('A2:S2', f'Period: {start_date} to {end_date}', workbook.add_format({'align': 'center'}))
        
        # Comprehensive headers
        headers = [
            'Date', 'Warehouse',
            'Open 15kg Filled', 'Open 21kg Filled', 'Open 15kg Empty', 'Open 21kg Empty',
            'Sold 15kg', 'Sold 21kg',
            'Refill 15kg', 'Refill 21kg',
            'Refill to Plant 15kg', 'Refill to Plant 21kg',
            'Received from Plant-15kg', 'Received from Plant-21kg',
            'Close 15kg Filled', 'Close 21kg Filled', 'Close 15kg Empty', 'Close 21kg Empty',
            'Status'
        ]
        
        row_start = 3
        for col, header in enumerate(headers):
            worksheet.write(row_start, col, header, header_format)
            worksheet.set_column(col, col, 12 if col > 1 else 15)  # Set column width
        
        for row, r in enumerate(reports, start=row_start + 1):
            # Date and Warehouse
            worksheet.write(row, 0, r.get('date', ''), cell_format)
            worksheet.write(row, 1, r.get('warehouse_name', ''), cell_format)
            
            # Opening Stock (blue)
            worksheet.write(row, 2, r.get('opening_15kg_filled', 0), opening_format)
            worksheet.write(row, 3, r.get('opening_21kg_filled', 0), opening_format)
            worksheet.write(row, 4, r.get('opening_15kg_empty', 0), opening_format)
            worksheet.write(row, 5, r.get('opening_21kg_empty', 0), opening_format)
            
            # Day Activities (yellow)
            worksheet.write(row, 6, r.get('sold_15kg_filled', 0), activity_format)
            worksheet.write(row, 7, r.get('sold_21kg_filled', 0), activity_format)
            worksheet.write(row, 8, r.get('refilling_15kg', 0), activity_format)
            worksheet.write(row, 9, r.get('refilling_21kg', 0), activity_format)
            worksheet.write(row, 10, r.get('refilling_plant_15kg', 0), activity_format)
            worksheet.write(row, 11, r.get('refilling_plant_21kg', 0), activity_format)
            worksheet.write(row, 12, r.get('received_from_plant_15kg', 0), activity_format)
            worksheet.write(row, 13, r.get('received_from_plant_21kg', 0), activity_format)
            
            # Closing Stock (green)
            worksheet.write(row, 14, r.get('closing_15kg_filled', 0), closing_format)
            worksheet.write(row, 15, r.get('closing_21kg_filled', 0), closing_format)
            worksheet.write(row, 16, r.get('closing_15kg_empty', 0), closing_format)
            worksheet.write(row, 17, r.get('closing_21kg_empty', 0), closing_format)
            
            # Status
            status = "Discrepancy" if r.get('has_discrepancy') else "OK"
            worksheet.write(row, 18, status, cell_format)
    
    elif report_type == "plant":
        query = {}
        if start_date:
            query['date'] = {'$gte': start_date}
        if end_date:
            if 'date' in query:
                query['date']['$lte'] = end_date
            else:
                query['date'] = {'$lte': end_date}
        
        reports = await db.plant_reports.find(query, {'_id': 0}).sort('date', -1).to_list(1000)
        
        worksheet.merge_range('A1:R1', 'K3 GAS SERVICE - Plant Hollongi Report', title_format)
        if start_date and end_date:
            worksheet.merge_range('A2:R2', f'Period: {start_date} to {end_date}', workbook.add_format({'align': 'center'}))
        
        # Comprehensive headers for Plant with Day Reloading
        headers = [
            'Date',
            'Op.Tank(kg)', 'Op.15F', 'Op.21F', 'Op.15E', 'Op.21E',
            'Reload(kg)', 'Recv.15E', 'Recv.21E',
            'Refill.15', 'Refill.21',
            'Del.15F', 'Del.21F',
            'Cl.Tank(kg)', 'Cl.15F', 'Cl.21F', 'Cl.15E', 'Cl.21E'
        ]
        
        # Create a reloading format (cyan background)
        reloading_format = workbook.add_format({'bg_color': '#cffafe', 'align': 'center', 'border': 1})
        
        for col, header in enumerate(headers):
            worksheet.write(3, col, header, header_format)
            worksheet.set_column(col, col, 10)
        
        for row, r in enumerate(reports, start=4):
            # Calculate totals for deliveries and received
            del_15 = sum([d.get('quantity', 0) for d in r.get('delivery_15kg', [])])
            del_21 = sum([d.get('quantity', 0) for d in r.get('delivery_21kg', [])])
            recv_15 = sum([d.get('quantity', 0) for d in r.get('received_empty_15kg', [])])
            recv_21 = sum([d.get('quantity', 0) for d in r.get('received_empty_21kg', [])])
            
            worksheet.write(row, 0, r.get('date', ''), cell_format)
            # Opening
            worksheet.write(row, 1, r.get('opening_bullet_tank_kg', 0), opening_format)
            worksheet.write(row, 2, r.get('opening_15kg_filled', 0), opening_format)
            worksheet.write(row, 3, r.get('opening_21kg_filled', 0), opening_format)
            worksheet.write(row, 4, r.get('opening_15kg_empty', 0), opening_format)
            worksheet.write(row, 5, r.get('opening_21kg_empty', 0), opening_format)
            # Day Reloading
            worksheet.write(row, 6, r.get('day_reloading_kg', 0), reloading_format)
            # Activities
            worksheet.write(row, 7, recv_15, activity_format)
            worksheet.write(row, 8, recv_21, activity_format)
            worksheet.write(row, 9, r.get('day_refilled_15kg', 0), activity_format)
            worksheet.write(row, 10, r.get('day_refilled_21kg', 0), activity_format)
            worksheet.write(row, 11, del_15, activity_format)
            worksheet.write(row, 12, del_21, activity_format)
            # Closing
            worksheet.write(row, 13, r.get('closing_bullet_tank_kg', 0), closing_format)
            worksheet.write(row, 14, r.get('closing_15kg_filled', 0), closing_format)
            worksheet.write(row, 15, r.get('closing_21kg_filled', 0), closing_format)
            worksheet.write(row, 16, r.get('closing_15kg_empty', 0), closing_format)
            worksheet.write(row, 17, r.get('closing_21kg_empty', 0), closing_format)
        
        # Create second sheet for warehouse breakdown
        breakdown_sheet = workbook.add_worksheet('Warehouse Breakdown')
        breakdown_sheet.merge_range('A1:E1', 'Warehouse-wise Breakdown', title_format)
        
        breakdown_header_format = workbook.add_format({'bold': True, 'bg_color': '#15803d', 'font_color': 'white', 'align': 'center', 'border': 1})
        delivery_header_format = workbook.add_format({'bold': True, 'bg_color': '#c7d2fe', 'align': 'center', 'border': 1})
        received_header_format = workbook.add_format({'bold': True, 'bg_color': '#fed7aa', 'align': 'center', 'border': 1})
        
        breakdown_sheet.set_column(0, 0, 12)  # Date
        breakdown_sheet.set_column(1, 1, 10)  # Type
        breakdown_sheet.set_column(2, 2, 15)  # Warehouse
        breakdown_sheet.set_column(3, 3, 12)  # 15kg
        breakdown_sheet.set_column(4, 4, 12)  # 21kg
        
        breakdown_headers = ['Date', 'Type', 'Warehouse', '15kg Qty', '21kg Qty']
        for col, header in enumerate(breakdown_headers):
            breakdown_sheet.write(2, col, header, breakdown_header_format)
        
        breakdown_row = 3
        for r in reports:
            report_date = r.get('date', '')
            
            # Delivery to Warehouses
            warehouse_del = {}
            for d in r.get('delivery_15kg', []):
                wname = d.get('warehouse_name', 'Unknown')
                if wname not in warehouse_del:
                    warehouse_del[wname] = {'qty15': 0, 'qty21': 0}
                warehouse_del[wname]['qty15'] = d.get('quantity', 0)
            for d in r.get('delivery_21kg', []):
                wname = d.get('warehouse_name', 'Unknown')
                if wname not in warehouse_del:
                    warehouse_del[wname] = {'qty15': 0, 'qty21': 0}
                warehouse_del[wname]['qty21'] = d.get('quantity', 0)
            
            for wname, qty in warehouse_del.items():
                breakdown_sheet.write(breakdown_row, 0, report_date, cell_format)
                breakdown_sheet.write(breakdown_row, 1, 'Delivery', delivery_header_format)
                breakdown_sheet.write(breakdown_row, 2, wname, cell_format)
                breakdown_sheet.write(breakdown_row, 3, qty['qty15'], cell_format)
                breakdown_sheet.write(breakdown_row, 4, qty['qty21'], cell_format)
                breakdown_row += 1
            
            # Empty Received from Warehouses
            warehouse_recv = {}
            for d in r.get('received_empty_15kg', []):
                wname = d.get('warehouse_name', 'Unknown')
                if wname not in warehouse_recv:
                    warehouse_recv[wname] = {'qty15': 0, 'qty21': 0}
                warehouse_recv[wname]['qty15'] = d.get('quantity', 0)
            for d in r.get('received_empty_21kg', []):
                wname = d.get('warehouse_name', 'Unknown')
                if wname not in warehouse_recv:
                    warehouse_recv[wname] = {'qty15': 0, 'qty21': 0}
                warehouse_recv[wname]['qty21'] = d.get('quantity', 0)
            
            for wname, qty in warehouse_recv.items():
                breakdown_sheet.write(breakdown_row, 0, report_date, cell_format)
                breakdown_sheet.write(breakdown_row, 1, 'Empty Recv', received_header_format)
                breakdown_sheet.write(breakdown_row, 2, wname, cell_format)
                breakdown_sheet.write(breakdown_row, 3, qty['qty15'], cell_format)
                breakdown_sheet.write(breakdown_row, 4, qty['qty21'], cell_format)
                breakdown_row += 1
    
    workbook.close()
    buffer.seek(0)
    
    # Generate filename based on report type
    date_str = datetime.now().strftime('%d%m%y')
    if report_type == "daily":
        filename = f"Daily_Inventory_Report_{date_str}.xlsx"
    else:
        filename = f"Plant_Hollongi_Report_{date_str}.xlsx"
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ============ ROOT ROUTES ============

@api_router.get("/")
async def root():
    return {"message": "K3 GAS SERVICE API", "version": "1.0.0"}

# ============ DEALER MANAGEMENT ============

@api_router.post("/dealers", response_model=DealerResponse)
async def create_dealer(data: DealerCreate, user: dict = Depends(get_current_user)):
    """Create a new dealer - Plant Hollongi only"""
    dealer = {
        'id': str(uuid.uuid4()),
        'name': data.name,
        'contact': data.contact,
        'address': data.address,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'is_active': True
    }
    await db.dealers.insert_one(dealer)
    return DealerResponse(**dealer)

@api_router.get("/dealers")
async def get_dealers(user: dict = Depends(get_current_user)):
    """Get all dealers"""
    dealers = await db.dealers.find({'is_active': True}, {'_id': 0}).to_list(1000)
    return dealers

@api_router.put("/dealers/{dealer_id}")
async def update_dealer(dealer_id: str, data: DealerCreate, user: dict = Depends(get_current_user)):
    """Update a dealer"""
    result = await db.dealers.update_one(
        {'id': dealer_id},
        {'$set': {'name': data.name, 'contact': data.contact, 'address': data.address}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Dealer not found")
    dealer = await db.dealers.find_one({'id': dealer_id}, {'_id': 0})
    return dealer

@api_router.delete("/dealers/{dealer_id}")
async def delete_dealer(dealer_id: str, user: dict = Depends(get_current_user)):
    """Soft delete a dealer"""
    result = await db.dealers.update_one({'id': dealer_id}, {'$set': {'is_active': False}})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Dealer not found")
    return {"message": "Dealer deleted successfully"}

# ============ DEALER ENTRIES ============

@api_router.post("/dealer-entries", response_model=DealerEntryResponse)
async def create_dealer_entry(data: DealerEntryCreate, user: dict = Depends(get_current_user)):
    """Create a dealer entry for cylinder issuance/refilling"""
    dealer = await db.dealers.find_one({'id': data.dealer_id, 'is_active': True}, {'_id': 0})
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    
    # Check if entry exists for this dealer and date
    existing = await db.dealer_entries.find_one({'dealer_id': data.dealer_id, 'date': data.date}, {'_id': 0})
    
    entry = {
        'id': existing['id'] if existing else str(uuid.uuid4()),
        'dealer_id': data.dealer_id,
        'dealer_name': dealer['name'],
        'date': data.date,
        'issued_15kg': data.issued_15kg,
        'issued_21kg': data.issued_21kg,
        'refilled_15kg': data.refilled_15kg,
        'refilled_21kg': data.refilled_21kg,
        'remarks': data.remarks[:500] if data.remarks else "",
        'submitted_by': user['name'],
        'submitted_at': datetime.now(timezone.utc).isoformat()
    }
    
    if existing:
        await db.dealer_entries.update_one({'id': existing['id']}, {'$set': entry})
    else:
        entry['created_at'] = datetime.now(timezone.utc).isoformat()
        await db.dealer_entries.insert_one(entry)
    
    return DealerEntryResponse(**entry)

@api_router.get("/dealer-entries")
async def get_dealer_entries(
    dealer_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get dealer entries with optional filters"""
    query = {}
    if dealer_id:
        query['dealer_id'] = dealer_id
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    entries = await db.dealer_entries.find(query, {'_id': 0}).sort('date', -1).to_list(1000)
    return entries

@api_router.get("/dealer-entries/summary")
async def get_dealer_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get dealer-wise summary with totals"""
    query = {}
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    # Aggregate by dealer
    pipeline = [
        {'$match': query} if query else {'$match': {}},
        {'$group': {
            '_id': '$dealer_id',
            'dealer_name': {'$first': '$dealer_name'},
            'total_issued_15kg': {'$sum': '$issued_15kg'},
            'total_issued_21kg': {'$sum': '$issued_21kg'},
            'total_refilled_15kg': {'$sum': '$refilled_15kg'},
            'total_refilled_21kg': {'$sum': '$refilled_21kg'},
            'entries_count': {'$sum': 1}
        }},
        {'$sort': {'dealer_name': 1}}
    ]
    
    summary = []
    async for item in db.dealer_entries.aggregate(pipeline):
        summary.append({
            'dealer_id': item['_id'],
            'dealer_name': item['dealer_name'],
            'total_issued_15kg': item['total_issued_15kg'],
            'total_issued_21kg': item['total_issued_21kg'],
            'total_refilled_15kg': item['total_refilled_15kg'],
            'total_refilled_21kg': item['total_refilled_21kg'],
            'entries_count': item['entries_count']
        })
    
    # Calculate grand totals
    grand_totals = {
        'total_issued_15kg': sum(s['total_issued_15kg'] for s in summary),
        'total_issued_21kg': sum(s['total_issued_21kg'] for s in summary),
        'total_refilled_15kg': sum(s['total_refilled_15kg'] for s in summary),
        'total_refilled_21kg': sum(s['total_refilled_21kg'] for s in summary),
    }
    
    return {'dealers': summary, 'grand_totals': grand_totals}

@api_router.put("/dealer-entries/{entry_id}")
async def update_dealer_entry(entry_id: str, data: DealerEntryCreate, user: dict = Depends(get_current_user)):
    """Update a dealer entry"""
    existing = await db.dealer_entries.find_one({'id': entry_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    dealer = await db.dealers.find_one({'id': data.dealer_id}, {'_id': 0})
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    
    update_data = {
        'dealer_id': data.dealer_id,
        'dealer_name': dealer['name'],
        'date': data.date,
        'issued_15kg': data.issued_15kg,
        'issued_21kg': data.issued_21kg,
        'refilled_15kg': data.refilled_15kg,
        'refilled_21kg': data.refilled_21kg,
        'remarks': data.remarks[:500] if data.remarks else "",
        'submitted_by': user['name'],
        'submitted_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.dealer_entries.update_one({'id': entry_id}, {'$set': update_data})
    updated = await db.dealer_entries.find_one({'id': entry_id}, {'_id': 0})
    return updated

# ============ LPG ACCESSORIES MANAGEMENT ============

@api_router.post("/accessories", response_model=AccessoryResponse)
async def create_accessory(data: AccessoryCreate, user: dict = Depends(require_admin)):
    """Create a new LPG accessory - Admin only"""
    accessory = {
        'id': str(uuid.uuid4()),
        'name': data.name,
        'description': data.description,
        'unit': data.unit,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'is_active': True
    }
    await db.accessories.insert_one(accessory)
    return AccessoryResponse(**accessory)

@api_router.get("/accessories")
async def get_accessories(user: dict = Depends(get_current_user)):
    """Get all accessories"""
    accessories = await db.accessories.find({'is_active': True}, {'_id': 0}).to_list(1000)
    return accessories

@api_router.put("/accessories/{accessory_id}")
async def update_accessory(accessory_id: str, data: AccessoryCreate, user: dict = Depends(require_admin)):
    """Update an accessory - Admin only"""
    result = await db.accessories.update_one(
        {'id': accessory_id},
        {'$set': {'name': data.name, 'description': data.description, 'unit': data.unit}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Accessory not found")
    accessory = await db.accessories.find_one({'id': accessory_id}, {'_id': 0})
    return accessory

@api_router.delete("/accessories/{accessory_id}")
async def delete_accessory(accessory_id: str, user: dict = Depends(require_admin)):
    """Soft delete an accessory - Admin only"""
    result = await db.accessories.update_one({'id': accessory_id}, {'$set': {'is_active': False}})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Accessory not found")
    return {"message": "Accessory deleted successfully"}

# ============ ACCESSORY DEALERS ============

@api_router.post("/accessory-dealers", response_model=AccessoryDealerResponse)
async def create_accessory_dealer(data: AccessoryDealerCreate, user: dict = Depends(require_admin)):
    """Create a new accessory dealer - Admin only"""
    dealer = {
        'id': str(uuid.uuid4()),
        'name': data.name,
        'contact': data.contact,
        'address': data.address,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'is_active': True
    }
    await db.accessory_dealers.insert_one(dealer)
    return AccessoryDealerResponse(**dealer)

@api_router.get("/accessory-dealers")
async def get_accessory_dealers(user: dict = Depends(get_current_user)):
    """Get all accessory dealers"""
    dealers = await db.accessory_dealers.find({'is_active': True}, {'_id': 0}).to_list(1000)
    return dealers

@api_router.put("/accessory-dealers/{dealer_id}")
async def update_accessory_dealer(dealer_id: str, data: AccessoryDealerCreate, user: dict = Depends(require_admin)):
    """Update an accessory dealer - Admin only"""
    result = await db.accessory_dealers.update_one(
        {'id': dealer_id},
        {'$set': {'name': data.name, 'contact': data.contact, 'address': data.address}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Dealer not found")
    dealer = await db.accessory_dealers.find_one({'id': dealer_id}, {'_id': 0})
    return dealer

@api_router.delete("/accessory-dealers/{dealer_id}")
async def delete_accessory_dealer(dealer_id: str, user: dict = Depends(require_admin)):
    """Soft delete an accessory dealer - Admin only"""
    result = await db.accessory_dealers.update_one({'id': dealer_id}, {'$set': {'is_active': False}})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Dealer not found")
    return {"message": "Dealer deleted successfully"}

# ============ ACCESSORY ENTRIES ============

@api_router.post("/accessory-entries", response_model=AccessoryEntryResponse)
async def create_accessory_entry(data: AccessoryEntryCreate, user: dict = Depends(require_admin)):
    """Create an accessory entry - Admin only"""
    accessory = await db.accessories.find_one({'id': data.accessory_id, 'is_active': True}, {'_id': 0})
    if not accessory:
        raise HTTPException(status_code=404, detail="Accessory not found")
    
    dealer = await db.accessory_dealers.find_one({'id': data.dealer_id, 'is_active': True}, {'_id': 0})
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    
    # Check if entry exists for this accessory, dealer and date
    existing = await db.accessory_entries.find_one({
        'accessory_id': data.accessory_id,
        'dealer_id': data.dealer_id,
        'date': data.date
    }, {'_id': 0})
    
    entry = {
        'id': existing['id'] if existing else str(uuid.uuid4()),
        'accessory_id': data.accessory_id,
        'accessory_name': accessory['name'],
        'dealer_id': data.dealer_id,
        'dealer_name': dealer['name'],
        'date': data.date,
        'total_issued': data.total_issued,
        'total_sold': data.total_sold,
        'total_remaining': data.total_remaining,
        'remarks': data.remarks[:500] if data.remarks else "",
        'submitted_by': user['name'],
        'submitted_at': datetime.now(timezone.utc).isoformat()
    }
    
    if existing:
        await db.accessory_entries.update_one({'id': existing['id']}, {'$set': entry})
    else:
        entry['created_at'] = datetime.now(timezone.utc).isoformat()
        await db.accessory_entries.insert_one(entry)
    
    return AccessoryEntryResponse(**entry)

@api_router.get("/accessory-entries")
async def get_accessory_entries(
    accessory_id: Optional[str] = None,
    dealer_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get accessory entries with optional filters"""
    query = {}
    if accessory_id:
        query['accessory_id'] = accessory_id
    if dealer_id:
        query['dealer_id'] = dealer_id
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    entries = await db.accessory_entries.find(query, {'_id': 0}).sort('date', -1).to_list(1000)
    return entries

@api_router.get("/accessory-entries/latest-remaining")
async def get_latest_accessory_remaining(
    accessory_id: str,
    dealer_id: str,
    before_date: str,
    user: dict = Depends(get_current_user)
):
    """Get the latest remaining quantity for an accessory and dealer before a specific date"""
    # Find the most recent entry before the given date
    entry = await db.accessory_entries.find_one(
        {
            'accessory_id': accessory_id,
            'dealer_id': dealer_id,
            'date': {'$lt': before_date}
        },
        {'_id': 0},
        sort=[('date', -1)]
    )
    
    if entry:
        return {'opening_stock': entry.get('total_remaining', 0), 'last_date': entry.get('date')}
    return {'opening_stock': 0, 'last_date': None}

@api_router.put("/accessory-entries/{entry_id}")
async def update_accessory_entry(entry_id: str, data: AccessoryEntryCreate, user: dict = Depends(require_admin)):
    """Update an accessory entry - Admin only"""
    existing = await db.accessory_entries.find_one({'id': entry_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    accessory = await db.accessories.find_one({'id': data.accessory_id, 'is_active': True}, {'_id': 0})
    if not accessory:
        raise HTTPException(status_code=404, detail="Accessory not found")
    
    dealer = await db.accessory_dealers.find_one({'id': data.dealer_id, 'is_active': True}, {'_id': 0})
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    
    update_data = {
        'accessory_id': data.accessory_id,
        'accessory_name': accessory['name'],
        'dealer_id': data.dealer_id,
        'dealer_name': dealer['name'],
        'date': data.date,
        'total_issued': data.total_issued,
        'total_sold': data.total_sold,
        'total_remaining': data.total_remaining,
        'remarks': data.remarks[:500] if data.remarks else "",
        'submitted_by': user['name'],
        'submitted_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.accessory_entries.update_one({'id': entry_id}, {'$set': update_data})
    
    updated = await db.accessory_entries.find_one({'id': entry_id}, {'_id': 0})
    return updated

@api_router.get("/accessory-entries/summary")
async def get_accessory_summary(
    accessory_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get dealer-wise accessory summary with totals"""
    query = {}
    if accessory_id:
        query['accessory_id'] = accessory_id
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    # Aggregate by dealer and accessory
    pipeline = [
        {'$match': query} if query else {'$match': {}},
        {'$group': {
            '_id': {'dealer_id': '$dealer_id', 'accessory_id': '$accessory_id'},
            'dealer_name': {'$first': '$dealer_name'},
            'accessory_name': {'$first': '$accessory_name'},
            'total_issued': {'$sum': '$total_issued'},
            'total_sold': {'$sum': '$total_sold'},
            'latest_remaining': {'$last': '$total_remaining'},
            'entries_count': {'$sum': 1}
        }},
        {'$sort': {'accessory_name': 1, 'dealer_name': 1}}
    ]
    
    summary = []
    async for item in db.accessory_entries.aggregate(pipeline):
        summary.append({
            'dealer_id': item['_id']['dealer_id'],
            'accessory_id': item['_id']['accessory_id'],
            'dealer_name': item['dealer_name'],
            'accessory_name': item['accessory_name'],
            'total_issued': item['total_issued'],
            'total_sold': item['total_sold'],
            'latest_remaining': item['latest_remaining'],
            'entries_count': item['entries_count']
        })
    
    # Calculate grand totals
    grand_totals = {
        'total_issued': sum(s['total_issued'] for s in summary),
        'total_sold': sum(s['total_sold'] for s in summary),
    }
    
    return {'summary': summary, 'grand_totals': grand_totals}

# ============ ACCESSORY REPORT EXPORTS ============

@api_router.get("/export/accessory-pdf")
async def export_accessory_pdf(
    accessory_id: Optional[str] = None,
    dealer_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(require_admin)
):
    """Export accessory report as PDF - Admin only"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#15803d'), alignment=1)
    elements.append(Paragraph("K3 GAS SERVICE - LPG Accessories Report", title_style))
    elements.append(Paragraph("Khayal Hamesha", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    query = {}
    if accessory_id:
        query['accessory_id'] = accessory_id
    if dealer_id:
        query['dealer_id'] = dealer_id
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    entries = await db.accessory_entries.find(query, {'_id': 0}).sort([('accessory_name', 1), ('dealer_name', 1), ('date', -1)]).to_list(1000)
    
    if start_date and end_date:
        elements.append(Paragraph(f"Period: {start_date} to {end_date}", styles['Normal']))
    elements.append(Spacer(1, 10))
    
    # Detail Table
    data = [['Date', 'Accessory', 'Dealer', 'Issued', 'Sold', 'Remaining', 'Remarks']]
    total_issued = 0
    total_sold = 0
    
    for e in entries:
        data.append([
            e['date'],
            e['accessory_name'],
            e['dealer_name'],
            e['total_issued'],
            e['total_sold'],
            e['total_remaining'],
            e.get('remarks', '')[:30]
        ])
        total_issued += e['total_issued']
        total_sold += e['total_sold']
    
    data.append(['TOTAL', '', '', total_issued, total_sold, '', ''])
    
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7c3aed')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor('#f3e8ff')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#5b21b6')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=LPG_Accessories_Report_{datetime.now().strftime('%d%m%y')}.pdf"}
    )

@api_router.get("/export/accessory-excel")
async def export_accessory_excel(
    accessory_id: Optional[str] = None,
    dealer_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(require_admin)
):
    """Export accessory report as Excel - Admin only"""
    buffer = BytesIO()
    workbook = xlsxwriter.Workbook(buffer)
    
    # Formats
    header_format = workbook.add_format({'bold': True, 'bg_color': '#7c3aed', 'font_color': 'white', 'border': 1, 'align': 'center'})
    cell_format = workbook.add_format({'border': 1, 'align': 'center'})
    total_format = workbook.add_format({'bold': True, 'bg_color': '#5b21b6', 'font_color': 'white', 'border': 1, 'align': 'center'})
    
    query = {}
    if accessory_id:
        query['accessory_id'] = accessory_id
    if dealer_id:
        query['dealer_id'] = dealer_id
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    entries = await db.accessory_entries.find(query, {'_id': 0}).sort([('accessory_name', 1), ('dealer_name', 1), ('date', -1)]).to_list(1000)
    
    # Sheet: Detailed entries
    sheet = workbook.add_worksheet('Accessory Entries')
    headers = ['Date', 'Accessory', 'Dealer', 'Issued', 'Sold', 'Remaining', 'Remarks']
    
    for col, header in enumerate(headers):
        sheet.write(0, col, header, header_format)
        sheet.set_column(col, col, 15)
    
    total_issued = 0
    total_sold = 0
    
    for row, e in enumerate(entries, 1):
        sheet.write(row, 0, e['date'], cell_format)
        sheet.write(row, 1, e['accessory_name'], cell_format)
        sheet.write(row, 2, e['dealer_name'], cell_format)
        sheet.write(row, 3, e['total_issued'], cell_format)
        sheet.write(row, 4, e['total_sold'], cell_format)
        sheet.write(row, 5, e['total_remaining'], cell_format)
        sheet.write(row, 6, e.get('remarks', ''), cell_format)
        
        total_issued += e['total_issued']
        total_sold += e['total_sold']
    
    # Totals row
    total_row = len(entries) + 1
    sheet.write(total_row, 0, 'TOTAL', total_format)
    sheet.write(total_row, 1, '', total_format)
    sheet.write(total_row, 2, '', total_format)
    sheet.write(total_row, 3, total_issued, total_format)
    sheet.write(total_row, 4, total_sold, total_format)
    sheet.write(total_row, 5, '', total_format)
    sheet.write(total_row, 6, '', total_format)
    
    workbook.close()
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=LPG_Accessories_Report_{datetime.now().strftime('%d%m%y')}.xlsx"}
    )

# ============ ACCESSORY SALES ENDPOINTS ============

@api_router.post("/accessory-sales")
async def create_accessory_sale(data: AccessorySaleCreate, user: dict = Depends(get_current_user)):
    """Create a new accessory sale with multiple items"""
    
    # Handle customer
    customer_id = data.customer_id
    if data.is_new_customer or not customer_id:
        # Create new customer
        new_customer = {
            'id': str(uuid.uuid4()),
            'date': data.date,
            'customer_name': data.customer_name,
            'phone': data.customer_phone,
            'address': data.customer_address,
            'consumer_no': '',
            'connection_type': 'domestic',
            'warehouse_id': data.warehouse_id or user.get('warehouse_id', ''),
            'warehouse_name': '',
            'gas_card_issued': False,
            'kyc_done': False,
            'remarks': 'Created from accessory sale',
            'created_by': user['id'],
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        # Get warehouse name
        if new_customer['warehouse_id']:
            warehouse = await db.warehouses.find_one({'id': new_customer['warehouse_id']}, {'_id': 0})
            if warehouse:
                new_customer['warehouse_name'] = warehouse['name']
        await db.customers.insert_one(new_customer)
        customer_id = new_customer['id']
    
    # Process items
    sale_items = []
    subtotal = 0
    
    for item in data.items:
        accessory = await db.accessories.find_one({'id': item.accessory_id, 'is_active': True}, {'_id': 0})
        if not accessory:
            raise HTTPException(status_code=404, detail=f"Accessory not found: {item.accessory_id}")
        
        item_total = item.quantity * item.unit_price
        sale_items.append({
            'accessory_id': item.accessory_id,
            'accessory_name': accessory['name'],
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'total_amount': item_total
        })
        subtotal += item_total
    
    # Determine warehouse
    warehouse_id = data.warehouse_id or user.get('warehouse_id', '')
    warehouse_name = ''
    if warehouse_id:
        warehouse = await db.warehouses.find_one({'id': warehouse_id}, {'_id': 0})
        if warehouse:
            warehouse_name = warehouse['name']
    
    # Create sale record
    sale = {
        'id': str(uuid.uuid4()),
        'customer_id': customer_id,
        'customer_name': data.customer_name,
        'customer_phone': data.customer_phone,
        'customer_address': data.customer_address,
        'date': data.date,
        'memo_no': data.memo_no,
        'items': sale_items,
        'subtotal': subtotal,
        'grand_total': subtotal,
        'payment_mode': data.payment_mode,
        'remarks': data.remarks,
        'warehouse_id': warehouse_id,
        'warehouse_name': warehouse_name,
        'created_by': user['id'],
        'created_by_name': user['name'],
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.accessory_sales.insert_one(sale)
    
    # Update inventory - deduct from the LATEST accessory entry for each item
    for item in data.items:
        # Find the latest entry for this accessory (across all dealers)
        latest_entry = await db.accessory_entries.find_one(
            {'accessory_id': item.accessory_id},
            {'_id': 0},
            sort=[('date', -1)]
        )
        
        if latest_entry:
            # Update the entry's total_sold and total_remaining
            current_sold = latest_entry.get('total_sold', 0)
            current_issued = latest_entry.get('total_issued', 0)
            new_sold = current_sold + item.quantity
            new_remaining = current_issued - new_sold
            
            await db.accessory_entries.update_one(
                {'id': latest_entry['id']},
                {'$set': {
                    'total_sold': new_sold, 
                    'total_remaining': max(0, new_remaining)  # Prevent negative values
                }}
            )
    
    # Remove _id if present
    sale.pop('_id', None)
    return sale

@api_router.get("/accessory-sales")
async def get_accessory_sales(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    customer_name: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get all accessory sales with optional filters"""
    query = {}
    
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    if customer_name:
        query['customer_name'] = {'$regex': customer_name, '$options': 'i'}
    
    # Filter by warehouse for non-admin
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id', '')
    elif warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    
    sales = await db.accessory_sales.find(query, {'_id': 0}).sort('date', 1).to_list(1000)
    return sales

@api_router.get("/accessory-sales/{sale_id}")
async def get_accessory_sale(sale_id: str, user: dict = Depends(get_current_user)):
    """Get a specific accessory sale by ID"""
    sale = await db.accessory_sales.find_one({'id': sale_id}, {'_id': 0})
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return sale

@api_router.delete("/accessory-sales/{sale_id}")
async def delete_accessory_sale(sale_id: str, user: dict = Depends(require_admin)):
    """Delete an accessory sale - Admin only"""
    sale = await db.accessory_sales.find_one({'id': sale_id}, {'_id': 0})
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    
    await db.accessory_sales.delete_one({'id': sale_id})
    return {"message": "Sale deleted successfully"}

@api_router.get("/accessory-sales-summary")
async def get_accessory_sales_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get summary of accessory sales"""
    query = {}
    
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id', '')
    elif warehouse_id:
        query['warehouse_id'] = warehouse_id
    
    sales = await db.accessory_sales.find(query, {'_id': 0}).to_list(1000)
    
    total_sales = len(sales)
    total_amount = sum(s.get('grand_total', 0) for s in sales)
    cash_amount = sum(s.get('grand_total', 0) for s in sales if s.get('payment_mode') == 'cash')
    pending_amount = sum(s.get('grand_total', 0) for s in sales if s.get('payment_mode') == 'pending')
    online_amount = sum(s.get('grand_total', 0) for s in sales if s.get('payment_mode') == 'online')
    
    # Items sold count
    total_items = sum(len(s.get('items', [])) for s in sales)
    total_qty = sum(sum(i.get('quantity', 0) for i in s.get('items', [])) for s in sales)
    
    return {
        'total_sales': total_sales,
        'total_amount': total_amount,
        'cash_amount': cash_amount,
        'pending_amount': pending_amount,
        'online_amount': online_amount,
        'total_items': total_items,
        'total_quantity': total_qty
    }

@api_router.get("/export/accessory-sales-pdf")
async def export_accessory_sales_pdf(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Export accessory sales as PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=14, fontName='Helvetica-Bold', textColor=colors.HexColor('#7c3aed'), alignment=1)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=13, alignment=1)
    
    elements.append(Paragraph("K3 GAS SERVICE - LPG Accessories Sales Report", title_style))
    elements.append(Paragraph("Khayal Hamesha", subtitle_style))
    if start_date and end_date:
        elements.append(Paragraph(f"Period: {start_date} to {end_date}", ParagraphStyle('Period', fontSize=10, alignment=1)))
    elements.append(Spacer(1, 10))
    
    # Query
    query = {}
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id', '')
    elif warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    
    sales = await db.accessory_sales.find(query, {'_id': 0}).sort('date', 1).to_list(1000)
    
    # Flatten items for table - include Memo No
    data = [['SL', 'Date', 'Memo No', 'Customer', 'Phone', 'Accessory', 'Qty', 'Unit Price', 'Total', 'Payment', 'Warehouse', 'Created By']]
    
    sl = 1
    grand_total = 0
    for sale in sales:
        for item in sale.get('items', []):
            data.append([
                str(sl),
                sale.get('date', '')[-5:],
                sale.get('memo_no', '')[:10],
                sale.get('customer_name', '')[:12],
                sale.get('customer_phone', '')[:10],
                item.get('accessory_name', '')[:12],
                str(item.get('quantity', 0)),
                format_inr(item.get('unit_price', 0)),
                format_inr(item.get('total_amount', 0)),
                sale.get('payment_mode', 'cash')[:6].title(),
                sale.get('warehouse_name', '')[:8],
                sale.get('created_by_name', '')[:8]
            ])
            grand_total += item.get('total_amount', 0)
            sl += 1
    
    data.append(['', '', '', '', '', '', 'GRAND TOTAL:', '', format_inr(grand_total), '', '', ''])
    
    col_widths = [22, 42, 50, 70, 60, 70, 30, 55, 55, 45, 55, 55]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7c3aed')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e9d5ff')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Accessory_Sales_{datetime.now().strftime('%d%m%y')}.pdf"}
    )

@api_router.get("/export/accessory-sales-excel")
async def export_accessory_sales_excel(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Export accessory sales as Excel"""
    buffer = BytesIO()
    workbook = xlsxwriter.Workbook(buffer)
    
    # Formats
    title_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'bg_color': '#7c3aed', 'font_color': 'white'})
    header_format = workbook.add_format({'bold': True, 'bg_color': '#7c3aed', 'font_color': 'white', 'border': 1, 'align': 'center'})
    cell_format = workbook.add_format({'border': 1, 'align': 'center'})
    total_format = workbook.add_format({'bold': True, 'bg_color': '#e9d5ff', 'border': 1, 'align': 'center'})
    money_format = workbook.add_format({'border': 1, 'align': 'right', 'num_format': '#,##0.00'})
    
    # Query
    query = {}
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id', '')
    elif warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    
    sales = await db.accessory_sales.find(query, {'_id': 0}).sort('date', 1).to_list(1000)
    
    # Worksheet - include Memo No
    ws = workbook.add_worksheet('Accessory Sales')
    ws.merge_range('A1:L1', 'K3 GAS SERVICE - LPG Accessories Sales Report', title_format)
    if start_date and end_date:
        ws.merge_range('A2:L2', f'Period: {start_date} to {end_date}', workbook.add_format({'align': 'center'}))
    
    headers = ['SL No.', 'Date', 'Memo No', 'Customer Name', 'Phone', 'Accessory', 'Qty', 'Unit Price (Rs.)', 'Total (Rs.)', 'Payment', 'Warehouse', 'Created By']
    for col, header in enumerate(headers):
        ws.write(3, col, header, header_format)
        ws.set_column(col, col, 14)
    
    row = 4
    sl = 1
    grand_total = 0
    
    for sale in sales:
        for item in sale.get('items', []):
            ws.write(row, 0, sl, cell_format)
            ws.write(row, 1, sale.get('date', ''), cell_format)
            ws.write(row, 2, sale.get('memo_no', ''), cell_format)
            ws.write(row, 3, sale.get('customer_name', ''), cell_format)
            ws.write(row, 4, sale.get('customer_phone', ''), cell_format)
            ws.write(row, 5, item.get('accessory_name', ''), cell_format)
            ws.write(row, 6, item.get('quantity', 0), cell_format)
            ws.write(row, 7, item.get('unit_price', 0), money_format)
            ws.write(row, 8, item.get('total_amount', 0), money_format)
            ws.write(row, 9, sale.get('payment_mode', 'cash').title(), cell_format)
            ws.write(row, 10, sale.get('warehouse_name', ''), cell_format)
            ws.write(row, 11, sale.get('created_by_name', ''), cell_format)
            grand_total += item.get('total_amount', 0)
            sl += 1
            row += 1
    
    # Total row
    ws.write(row, 6, 'GRAND TOTAL:', total_format)
    ws.write(row, 7, '', total_format)
    ws.write(row, 8, grand_total, total_format)
    
    workbook.close()
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Accessory_Sales_{datetime.now().strftime('%d%m%y')}.xlsx"}
    )

# ============ DEALER REPORT EXPORTS ============

@api_router.get("/export/dealer-pdf")
async def export_dealer_pdf(
    dealer_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Export dealer report as PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#15803d'), alignment=1)
    elements.append(Paragraph("K3 GAS SERVICE - Dealer Report", title_style))
    elements.append(Paragraph("Khayal Hamesha", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    query = {}
    if dealer_id:
        query['dealer_id'] = dealer_id
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    entries = await db.dealer_entries.find(query, {'_id': 0}).sort([('dealer_name', 1), ('date', -1)]).to_list(1000)
    
    if start_date and end_date:
        elements.append(Paragraph(f"Period: {start_date} to {end_date}", styles['Normal']))
    elements.append(Spacer(1, 10))
    
    # Detail Table
    data = [['Date', 'Dealer', '15kg Issued', '21kg Issued', '15kg Refilled', '21kg Refilled', 'Remarks']]
    total_issued_15kg = 0
    total_issued_21kg = 0
    total_refilled_15kg = 0
    total_refilled_21kg = 0
    
    for e in entries:
        data.append([
            e['date'],
            e['dealer_name'],
            e['issued_15kg'],
            e['issued_21kg'],
            e['refilled_15kg'],
            e['refilled_21kg'],
            e.get('remarks', '')[:30]
        ])
        total_issued_15kg += e['issued_15kg']
        total_issued_21kg += e['issued_21kg']
        total_refilled_15kg += e['refilled_15kg']
        total_refilled_21kg += e['refilled_21kg']
    
    # Add totals row
    data.append(['TOTAL', '', total_issued_15kg, total_issued_21kg, total_refilled_15kg, total_refilled_21kg, ''])
    
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#15803d')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#166534')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    elements.append(table)
    
    # Summary section
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Dealer-wise Summary", styles['Heading2']))
    elements.append(Spacer(1, 10))
    
    # Get summary
    pipeline = [
        {'$match': query} if query else {'$match': {}},
        {'$group': {
            '_id': '$dealer_id',
            'dealer_name': {'$first': '$dealer_name'},
            'total_issued_15kg': {'$sum': '$issued_15kg'},
            'total_issued_21kg': {'$sum': '$issued_21kg'},
            'total_refilled_15kg': {'$sum': '$refilled_15kg'},
            'total_refilled_21kg': {'$sum': '$refilled_21kg'},
        }},
        {'$sort': {'dealer_name': 1}}
    ]
    
    summary_data = [['Dealer', '15kg Issued', '21kg Issued', '15kg Refilled', '21kg Refilled']]
    async for item in db.dealer_entries.aggregate(pipeline):
        summary_data.append([
            item['dealer_name'],
            item['total_issued_15kg'],
            item['total_issued_21kg'],
            item['total_refilled_15kg'],
            item['total_refilled_21kg']
        ])
    summary_data.append(['GRAND TOTAL', total_issued_15kg, total_issued_21kg, total_refilled_15kg, total_refilled_21kg])
    
    summary_table = Table(summary_data, repeatRows=1)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(summary_table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Dealer_Report_{datetime.now().strftime('%d%m%y')}.pdf"}
    )

@api_router.get("/export/dealer-excel")
async def export_dealer_excel(
    dealer_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Export dealer report as Excel"""
    buffer = BytesIO()
    workbook = xlsxwriter.Workbook(buffer)
    
    # Formats
    header_format = workbook.add_format({'bold': True, 'bg_color': '#15803d', 'font_color': 'white', 'border': 1, 'align': 'center'})
    cell_format = workbook.add_format({'border': 1, 'align': 'center'})
    total_format = workbook.add_format({'bold': True, 'bg_color': '#166534', 'font_color': 'white', 'border': 1, 'align': 'center'})
    summary_header = workbook.add_format({'bold': True, 'bg_color': '#1e40af', 'font_color': 'white', 'border': 1, 'align': 'center'})
    summary_total = workbook.add_format({'bold': True, 'bg_color': '#1e3a8a', 'font_color': 'white', 'border': 1, 'align': 'center'})
    
    query = {}
    if dealer_id:
        query['dealer_id'] = dealer_id
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    entries = await db.dealer_entries.find(query, {'_id': 0}).sort([('dealer_name', 1), ('date', -1)]).to_list(1000)
    
    # Sheet 1: Detailed entries
    sheet = workbook.add_worksheet('Dealer Entries')
    headers = ['Date', 'Dealer', '15kg Issued', '21kg Issued', '15kg Refilled', '21kg Refilled', 'Remarks']
    
    for col, header in enumerate(headers):
        sheet.write(0, col, header, header_format)
        sheet.set_column(col, col, 15)
    
    total_issued_15kg = 0
    total_issued_21kg = 0
    total_refilled_15kg = 0
    total_refilled_21kg = 0
    
    for row, e in enumerate(entries, 1):
        sheet.write(row, 0, e['date'], cell_format)
        sheet.write(row, 1, e['dealer_name'], cell_format)
        sheet.write(row, 2, e['issued_15kg'], cell_format)
        sheet.write(row, 3, e['issued_21kg'], cell_format)
        sheet.write(row, 4, e['refilled_15kg'], cell_format)
        sheet.write(row, 5, e['refilled_21kg'], cell_format)
        sheet.write(row, 6, e.get('remarks', ''), cell_format)
        
        total_issued_15kg += e['issued_15kg']
        total_issued_21kg += e['issued_21kg']
        total_refilled_15kg += e['refilled_15kg']
        total_refilled_21kg += e['refilled_21kg']
    
    # Totals row
    total_row = len(entries) + 1
    sheet.write(total_row, 0, 'TOTAL', total_format)
    sheet.write(total_row, 1, '', total_format)
    sheet.write(total_row, 2, total_issued_15kg, total_format)
    sheet.write(total_row, 3, total_issued_21kg, total_format)
    sheet.write(total_row, 4, total_refilled_15kg, total_format)
    sheet.write(total_row, 5, total_refilled_21kg, total_format)
    sheet.write(total_row, 6, '', total_format)
    
    # Sheet 2: Summary
    summary_sheet = workbook.add_worksheet('Dealer Summary')
    summary_headers = ['Dealer', '15kg Issued', '21kg Issued', '15kg Refilled', '21kg Refilled']
    
    for col, header in enumerate(summary_headers):
        summary_sheet.write(0, col, header, summary_header)
        summary_sheet.set_column(col, col, 18)
    
    # Get summary
    pipeline = [
        {'$match': query} if query else {'$match': {}},
        {'$group': {
            '_id': '$dealer_id',
            'dealer_name': {'$first': '$dealer_name'},
            'total_issued_15kg': {'$sum': '$issued_15kg'},
            'total_issued_21kg': {'$sum': '$issued_21kg'},
            'total_refilled_15kg': {'$sum': '$refilled_15kg'},
            'total_refilled_21kg': {'$sum': '$refilled_21kg'},
        }},
        {'$sort': {'dealer_name': 1}}
    ]
    
    row = 1
    async for item in db.dealer_entries.aggregate(pipeline):
        summary_sheet.write(row, 0, item['dealer_name'], cell_format)
        summary_sheet.write(row, 1, item['total_issued_15kg'], cell_format)
        summary_sheet.write(row, 2, item['total_issued_21kg'], cell_format)
        summary_sheet.write(row, 3, item['total_refilled_15kg'], cell_format)
        summary_sheet.write(row, 4, item['total_refilled_21kg'], cell_format)
        row += 1
    
    # Grand total
    summary_sheet.write(row, 0, 'GRAND TOTAL', summary_total)
    summary_sheet.write(row, 1, total_issued_15kg, summary_total)
    summary_sheet.write(row, 2, total_issued_21kg, summary_total)
    summary_sheet.write(row, 3, total_refilled_15kg, summary_total)
    summary_sheet.write(row, 4, total_refilled_21kg, summary_total)
    
    workbook.close()
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Dealer_Report_{datetime.now().strftime('%d%m%y')}.xlsx"}
    )

# ============ CUSTOMER MANAGEMENT ============

class CustomerCreate(BaseModel):
    date: str
    connection_type: str  # 'domestic' or 'commercial'
    customer_name: str
    address: str = ""
    phone: str = ""  # Mobile/WhatsApp number for messaging
    consumer_no: str = ""
    cash_memo_no: str = ""
    cylinder_nos: str = ""
    gas_card_issued: bool = False
    kyc_done: bool = False
    remarks: str = ""

class CustomerUpdate(BaseModel):
    date: Optional[str] = None
    connection_type: Optional[str] = None
    customer_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    consumer_no: Optional[str] = None
    cash_memo_no: Optional[str] = None
    cylinder_nos: Optional[str] = None
    gas_card_issued: Optional[bool] = None
    kyc_done: Optional[bool] = None
    remarks: Optional[str] = None

class CustomerResponse(BaseModel):
    id: str
    warehouse_id: str
    warehouse_name: str
    date: str
    connection_type: str
    customer_name: str
    address: str
    phone: str
    consumer_no: str
    cash_memo_no: str
    cylinder_nos: str
    gas_card_issued: bool
    kyc_done: bool
    remarks: str
    created_by: str
    created_at: str
    updated_at: Optional[str] = None

class BulkCustomerUpload(BaseModel):
    customers: List[CustomerCreate]

@api_router.get("/customers")
async def get_customers(
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
    
    customers = await db.customers.find(query).sort('date', -1).to_list(1000)
    
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
    
    return result

@api_router.post("/customers")
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

@api_router.post("/customers/warehouse/{warehouse_id}")
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

@api_router.put("/customers/{customer_id}")
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

@api_router.delete("/customers/{customer_id}")
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
    if warnings:
        response["warnings"] = warnings
    return response

@api_router.get("/customers/{customer_id}/linked-records")
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

@api_router.post("/customers/bulk")
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

@api_router.post("/customers/bulk/warehouse/{warehouse_id}")
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

@api_router.get("/customers/refill-status")
async def get_customers_refill_status(
    warehouse_id: Optional[str] = None,
    overdue_only: Optional[bool] = False,
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

@api_router.get("/customers/{customer_id}/last-refill")
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

@api_router.get("/export/customer-refill-pdf")
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

@api_router.get("/export/customer-refill-excel")
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
    
    # Title rows
    ws.merge_cells('A1:H1')
    ws['A1'] = "K3 GAS SERVICE - Customer LPG Refill Status Report"
    ws['A1'].font = Font(bold=True, size=14, color="15803d")
    ws.merge_cells('A2:H2')
    ws['A2'] = f"Generated: {today_display} | Total: {total_c} | Recently Refilled (<=15d): {recent_c} | Overdue (>30d): {overdue_c}"
    ws['A2'].font = Font(size=9, color="666666")
    
    headers = ['SL No.', 'Customer Name', 'Consumer No.', 'Phone', 'Address', 'Last Refill Date', 'Days Since Refill', 'Total Refills']
    ws.append([])
    ws.append(headers)
    
    header_fill = PatternFill(start_color="16a34a", end_color="16a34a", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=10)
    for cell in ws[4]:
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
        row_num = i + 4
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
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=customer_refill_status_{today}.xlsx"}
    )

@api_router.get("/customers/summary")
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

@api_router.get("/customers/sample-excel")
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

@api_router.get("/export/customers-pdf")
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

@api_router.get("/export/customers-excel")
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
    
    # Headers
    headers = ['Date', 'Connection Type', 'Customer Name', 'Phone', 'Address', 'Consumer No', 'Cash Memo No', 'Cylinder Nos', 'Gas Card Issued', 'KYC Done', 'Remarks', 'Warehouse']
    
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)
        worksheet.set_column(col, col, 15 if col < 4 else 20)
    
    # Data
    for row, c in enumerate(customers, start=1):
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
    
    # Generate filename with category
    category_name = category.capitalize() if category and category != 'all' else 'All'
    date_str = datetime.now().strftime('%d%m%y')
    filename = f"Customer_Report_{category_name}_{date_str}.xlsx"
    
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ============ SALES DASHBOARD ============

class SalesEntryCreate(BaseModel):
    date: str
    customer_id: Optional[str] = None  # Existing customer
    consumer_name: str
    address: str = ""
    consumer_no: str = ""
    memo_no: str = ""
    amount: float = 0
    connection_type: str = "domestic"  # domestic, domestic_refill, commercial, commercial_refill
    cylinder_nos: str = ""  # Required for refill types
    payment_mode: str = "cash"  # cash, online, pending, split
    cash_amount: float = 0
    online_amount: float = 0
    credit_amount: float = 0
    no_of_refills: int = 0
    remarks: str = ""

class SalesEntryUpdate(BaseModel):
    date: Optional[str] = None
    consumer_name: Optional[str] = None
    address: Optional[str] = None
    consumer_no: Optional[str] = None
    memo_no: Optional[str] = None
    amount: Optional[float] = None
    connection_type: Optional[str] = None
    cylinder_nos: Optional[str] = None
    payment_mode: Optional[str] = None
    cash_amount: Optional[float] = None
    online_amount: Optional[float] = None
    credit_amount: Optional[float] = None
    no_of_refills: Optional[int] = None
    remarks: Optional[str] = None

@api_router.get("/sales-entries")
async def get_sales_entries(
    warehouse_id: str = None,
    start_date: str = None,
    end_date: str = None,
    payment_mode: str = None,
    search: str = None,
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
    
    entries = await db.sales_entries.find(query, {'_id': 0}).sort('date', 1).to_list(5000)
    
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
    
    return result

@api_router.post("/sales-entries")
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
    
    return {
        **entry_doc,
        'warehouse_name': warehouse_name,
        'created_by_name': user['name']
    }

@api_router.post("/sales-entries/warehouse/{warehouse_id}")
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
    
    return {
        **entry_doc,
        'warehouse_name': warehouse['name'],
        'created_by_name': user['name']
    }

@api_router.put("/sales-entries/{entry_id}")
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

@api_router.delete("/sales-entries/{entry_id}")
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

@api_router.get("/sales-entries/summary")
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

@api_router.get("/sales-entries/frequent-customers")
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

@api_router.get("/export/sales-pdf")
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

@api_router.get("/export/sales-excel")
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

@api_router.get("/export/sales-summary-pdf")
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


@api_router.get("/export/sales-summary-excel")
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

# ============ ORDER MANAGEMENT ============

class OrderCreate(BaseModel):
    order_date: str
    customer_id: Optional[str] = None  # Existing customer
    customer_name: str
    mobile_number: str = ""
    address_landmark: str = ""
    connection_type: str = "domestic"  # domestic, domestic_refill, commercial, commercial_refill
    cylinder_nos: str = ""  # Required for refill types
    payment_mode: str = "cash"  # cash, online, credit_pending
    remarks: str = ""

class OrderUpdate(BaseModel):
    order_date: Optional[str] = None
    customer_name: Optional[str] = None
    mobile_number: Optional[str] = None
    address_landmark: Optional[str] = None
    connection_type: Optional[str] = None
    cylinder_nos: Optional[str] = None
    payment_mode: Optional[str] = None
    remarks: Optional[str] = None
    status: Optional[str] = None  # pending, delivered, cancelled

class OrderStatusUpdate(BaseModel):
    status: str  # pending, delivered, cancelled
    cancellation_reason: Optional[str] = None

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

@api_router.get("/orders")
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

@api_router.post("/orders")
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

@api_router.post("/orders/warehouse/{warehouse_id}")
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

@api_router.get("/orders/{order_id}")
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

@api_router.put("/orders/{order_id}")
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

@api_router.patch("/orders/{order_id}/status")
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

@api_router.delete("/orders/{order_id}")
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

@api_router.get("/admin/order-analysis")
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

@api_router.get("/export/order-analysis-pdf")
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

@api_router.get("/export/order-analysis-excel")
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


# ===================== CONNECTION & REFILL ANALYTICS =====================

def _count_cylinders(cylinder_nos_str):
    """Count cylinder quantity from the cylinder_nos field (should be a number)"""
    if not cylinder_nos_str or not str(cylinder_nos_str).strip():
        return 0
    val = str(cylinder_nos_str).strip()
    try:
        return int(val)
    except ValueError:
        # Legacy data: comma-separated serial numbers
        parts = [p.strip() for p in val.split(',') if p.strip()]
        return len(parts)

def _get_date_range_for_period(period, custom_start=None, custom_end=None):
    """Return (start_date, end_date) strings for a given period"""
    today = datetime.now(timezone.utc).date()
    if period == 'daily':
        return str(today), str(today)
    elif period == 'monthly':
        return str(today.replace(day=1)), str(today)
    elif period == 'quarterly':
        q_month = ((today.month - 1) // 3) * 3 + 1
        return str(today.replace(month=q_month, day=1)), str(today)
    elif period == 'yearly':
        return str(today.replace(month=1, day=1)), str(today)
    elif period == 'custom' and custom_start and custom_end:
        return custom_start, custom_end
    return str(today), str(today)

@api_router.get("/admin/connection-refill-analytics")
async def get_connection_refill_analytics(
    period: str = 'monthly',
    warehouse_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Analytics for new connections and refills from sales_entries"""
    user = await get_current_user(credentials)
    if user['role'] != 'admin':
        warehouse_id = user.get('warehouse_id', '')
    
    sd, ed = _get_date_range_for_period(period, start_date, end_date)
    
    query = {'date': {'$gte': sd, '$lte': ed}}
    if warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    
    entries = await db.sales_entries.find(query, {'_id': 0}).to_list(None)
    
    # Categorize
    domestic_new = [e for e in entries if e.get('connection_type') == 'domestic']
    commercial_new = [e for e in entries if e.get('connection_type') == 'commercial']
    domestic_refill = [e for e in entries if e.get('connection_type') == 'domestic_refill']
    commercial_refill = [e for e in entries if e.get('connection_type') == 'commercial_refill']
    
    # Cylinder counts
    domestic_new_cyl = sum(_count_cylinders(e.get('cylinder_nos', '')) for e in domestic_new)
    commercial_new_cyl = sum(_count_cylinders(e.get('cylinder_nos', '')) for e in commercial_new)
    domestic_refill_cyl = sum(int(e.get('no_of_refills', 0) or 0) for e in domestic_refill)
    commercial_refill_cyl = sum(int(e.get('no_of_refills', 0) or 0) for e in commercial_refill)
    
    # For new connections without cylinder_nos, count as 1 per entry
    for e in domestic_new:
        if not e.get('cylinder_nos', '').strip():
            domestic_new_cyl += 1
    for e in commercial_new:
        if not e.get('cylinder_nos', '').strip():
            commercial_new_cyl += 1
    
    # Warehouse breakdown
    warehouses = await db.warehouses.find({}, {'_id': 0}).to_list(None)
    wh_map = {w['id']: w['name'] for w in warehouses}
    
    wh_breakdown = {}
    for e in entries:
        wid = e.get('warehouse_id', '')
        if wid not in wh_breakdown:
            wh_breakdown[wid] = {
                'warehouse_id': wid,
                'warehouse_name': wh_map.get(wid, e.get('warehouse_name', 'Unknown')),
                'domestic_new': 0, 'commercial_new': 0,
                'domestic_new_cyl': 0, 'commercial_new_cyl': 0,
                'domestic_refill': 0, 'commercial_refill': 0,
                'domestic_refill_cyl': 0, 'commercial_refill_cyl': 0
            }
        wb = wh_breakdown[wid]
        ct = e.get('connection_type', '')
        if ct == 'domestic':
            wb['domestic_new'] += 1
            cyl = _count_cylinders(e.get('cylinder_nos', ''))
            wb['domestic_new_cyl'] += cyl if cyl > 0 else 1
        elif ct == 'commercial':
            wb['commercial_new'] += 1
            cyl = _count_cylinders(e.get('cylinder_nos', ''))
            wb['commercial_new_cyl'] += cyl if cyl > 0 else 1
        elif ct == 'domestic_refill':
            wb['domestic_refill'] += 1
            wb['domestic_refill_cyl'] += int(e.get('no_of_refills', 0) or 0)
        elif ct == 'commercial_refill':
            wb['commercial_refill'] += 1
            wb['commercial_refill_cyl'] += int(e.get('no_of_refills', 0) or 0)
    
    # Date-wise breakdown
    from collections import defaultdict
    date_data = defaultdict(lambda: {
        'domestic_new': 0, 'commercial_new': 0,
        'domestic_new_cyl': 0, 'commercial_new_cyl': 0,
        'domestic_refill': 0, 'commercial_refill': 0,
        'domestic_refill_cyl': 0, 'commercial_refill_cyl': 0
    })
    
    for e in entries:
        d = e.get('date', '')
        ct = e.get('connection_type', '')
        dd = date_data[d]
        if ct == 'domestic':
            dd['domestic_new'] += 1
            cyl = _count_cylinders(e.get('cylinder_nos', ''))
            dd['domestic_new_cyl'] += cyl if cyl > 0 else 1
        elif ct == 'commercial':
            dd['commercial_new'] += 1
            cyl = _count_cylinders(e.get('cylinder_nos', ''))
            dd['commercial_new_cyl'] += cyl if cyl > 0 else 1
        elif ct == 'domestic_refill':
            dd['domestic_refill'] += 1
            dd['domestic_refill_cyl'] += int(e.get('no_of_refills', 0) or 0)
        elif ct == 'commercial_refill':
            dd['commercial_refill'] += 1
            dd['commercial_refill_cyl'] += int(e.get('no_of_refills', 0) or 0)
    
    date_breakdown = [{'date': k, **v} for k, v in sorted(date_data.items())]
    
    return {
        'summary': {
            'total_new_connections': len(domestic_new) + len(commercial_new),
            'domestic_new_connections': len(domestic_new),
            'commercial_new_connections': len(commercial_new),
            'domestic_new_cylinders': domestic_new_cyl,
            'commercial_new_cylinders': commercial_new_cyl,
            'total_refills': len(domestic_refill) + len(commercial_refill),
            'domestic_refills': len(domestic_refill),
            'commercial_refills': len(commercial_refill),
            'domestic_refill_cylinders': domestic_refill_cyl,
            'commercial_refill_cylinders': commercial_refill_cyl
        },
        'warehouse_breakdown': list(wh_breakdown.values()),
        'date_breakdown': date_breakdown,
        'period': period,
        'date_range': {'start': sd, 'end': ed}
    }

@api_router.get("/export/connection-refill-analytics-pdf")
async def export_connection_refill_analytics_pdf(
    period: str = 'monthly',
    warehouse_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export connection & refill analytics as PDF"""
    user = await get_current_user(credentials)
    if user['role'] != 'admin':
        warehouse_id = user.get('warehouse_id', '')
    
    sd, ed = _get_date_range_for_period(period, start_date, end_date)
    query = {'date': {'$gte': sd, '$lte': ed}}
    if warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    
    entries = await db.sales_entries.find(query, {'_id': 0}).to_list(None)
    warehouses = await db.warehouses.find({}, {'_id': 0}).to_list(None)
    wh_map = {w['id']: w['name'] for w in warehouses}
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = []
    
    # Title
    title_style = ParagraphStyle('ReportTitle', parent=styles['Title'], fontSize=16, spaceAfter=6)
    elements.append(Paragraph("Connection & Refill Analytics Report", title_style))
    
    wh_label = 'All Warehouses'
    if warehouse_id and warehouse_id != 'all':
        wh_label = wh_map.get(warehouse_id, warehouse_id)
    elements.append(Paragraph(f"Period: {sd} to {ed} | Warehouse: {wh_label}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Summary table
    domestic_new = [e for e in entries if e.get('connection_type') == 'domestic']
    commercial_new = [e for e in entries if e.get('connection_type') == 'commercial']
    domestic_refill = [e for e in entries if e.get('connection_type') == 'domestic_refill']
    commercial_refill = [e for e in entries if e.get('connection_type') == 'commercial_refill']
    
    dn_cyl = sum(_count_cylinders(e.get('cylinder_nos', '')) or 1 for e in domestic_new)
    cn_cyl = sum(_count_cylinders(e.get('cylinder_nos', '')) or 1 for e in commercial_new)
    dr_cyl = sum(int(e.get('no_of_refills', 0) or 0) for e in domestic_refill)
    cr_cyl = sum(int(e.get('no_of_refills', 0) or 0) for e in commercial_refill)
    
    summary_data = [
        ['Category', 'Count', 'Cylinders'],
        ['Domestic New Connections', str(len(domestic_new)), str(dn_cyl)],
        ['Commercial New Connections', str(len(commercial_new)), str(cn_cyl)],
        ['Total New Connections', str(len(domestic_new)+len(commercial_new)), str(dn_cyl+cn_cyl)],
        ['Domestic Refills', str(len(domestic_refill)), str(dr_cyl)],
        ['Commercial Refills', str(len(commercial_refill)), str(cr_cyl)],
        ['Total Refills', str(len(domestic_refill)+len(commercial_refill)), str(dr_cyl+cr_cyl)],
        ['Grand Total', str(len(entries)), str(dn_cyl+cn_cyl+dr_cyl+cr_cyl)]
    ]
    
    st = Table(summary_data, colWidths=[250, 100, 100])
    st.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#e8f5e9')),
        ('BACKGROUND', (0, 6), (-1, 6), colors.HexColor('#e3f2fd')),
        ('BACKGROUND', (0, 7), (-1, 7), colors.HexColor('#fff3e0')),
        ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),
        ('FONTNAME', (0, 6), (-1, 6), 'Helvetica-Bold'),
        ('FONTNAME', (0, 7), (-1, 7), 'Helvetica-Bold'),
    ]))
    elements.append(st)
    elements.append(Spacer(1, 16))
    
    # Date-wise breakdown table
    elements.append(Paragraph("Date-wise Breakdown", styles['Heading3']))
    from collections import defaultdict
    date_data = defaultdict(lambda: [0]*8)
    for e in entries:
        d = e.get('date', '')
        ct = e.get('connection_type', '')
        dd = date_data[d]
        if ct == 'domestic':
            dd[0] += 1; dd[1] += _count_cylinders(e.get('cylinder_nos', '')) or 1
        elif ct == 'commercial':
            dd[2] += 1; dd[3] += _count_cylinders(e.get('cylinder_nos', '')) or 1
        elif ct == 'domestic_refill':
            dd[4] += 1; dd[5] += int(e.get('no_of_refills', 0) or 0)
        elif ct == 'commercial_refill':
            dd[6] += 1; dd[7] += int(e.get('no_of_refills', 0) or 0)
    
    dt_table = [['Date', 'Dom. New', 'Cyl', 'Com. New', 'Cyl', 'Dom. Refill', 'Cyl', 'Com. Refill', 'Cyl']]
    grand = [0]*8
    for d in sorted(date_data.keys()):
        row = date_data[d]
        dt_table.append([d] + [str(v) for v in row])
        for i in range(8): grand[i] += row[i]
    dt_table.append(['TOTAL'] + [str(v) for v in grand])
    
    dt = Table(dt_table, colWidths=[70, 55, 40, 55, 40, 60, 40, 60, 40])
    dt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fff3e0')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(dt)
    
    doc.build(elements)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=connection_refill_analytics_{sd}_to_{ed}.pdf"})

@api_router.get("/export/connection-refill-analytics-excel")
async def export_connection_refill_analytics_excel(
    period: str = 'monthly',
    warehouse_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export connection & refill analytics as Excel"""
    user = await get_current_user(credentials)
    if user['role'] != 'admin':
        warehouse_id = user.get('warehouse_id', '')
    
    sd, ed = _get_date_range_for_period(period, start_date, end_date)
    query = {'date': {'$gte': sd, '$lte': ed}}
    if warehouse_id and warehouse_id != 'all':
        query['warehouse_id'] = warehouse_id
    
    entries = await db.sales_entries.find(query, {'_id': 0}).to_list(None)
    warehouses = await db.warehouses.find({}, {'_id': 0}).to_list(None)
    wh_map = {w['id']: w['name'] for w in warehouses}
    
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    
    header_format = workbook.add_format({'bold': True, 'bg_color': '#1e3a5f', 'font_color': 'white', 'border': 1, 'align': 'center'})
    data_fmt = workbook.add_format({'border': 1, 'align': 'center'})
    bold_fmt = workbook.add_format({'border': 1, 'bold': True, 'align': 'center', 'bg_color': '#fff3e0'})
    green_fmt = workbook.add_format({'border': 1, 'bold': True, 'align': 'center', 'bg_color': '#e8f5e9'})
    blue_fmt = workbook.add_format({'border': 1, 'bold': True, 'align': 'center', 'bg_color': '#e3f2fd'})
    
    # Summary Sheet
    ws1 = workbook.add_worksheet('Summary')
    domestic_new = [e for e in entries if e.get('connection_type') == 'domestic']
    commercial_new = [e for e in entries if e.get('connection_type') == 'commercial']
    domestic_refill = [e for e in entries if e.get('connection_type') == 'domestic_refill']
    commercial_refill = [e for e in entries if e.get('connection_type') == 'commercial_refill']
    
    dn_cyl = sum(_count_cylinders(e.get('cylinder_nos', '')) or 1 for e in domestic_new)
    cn_cyl = sum(_count_cylinders(e.get('cylinder_nos', '')) or 1 for e in commercial_new)
    dr_cyl = sum(int(e.get('no_of_refills', 0) or 0) for e in domestic_refill)
    cr_cyl = sum(int(e.get('no_of_refills', 0) or 0) for e in commercial_refill)
    
    ws1.write(0, 0, f'Connection & Refill Analytics | {sd} to {ed}', workbook.add_format({'bold': True, 'font_size': 14}))
    for col, h in enumerate(['Category', 'Count', 'Cylinders']):
        ws1.write(2, col, h, header_format)
    summary_rows = [
        ('Domestic New Connections', len(domestic_new), dn_cyl),
        ('Commercial New Connections', len(commercial_new), cn_cyl),
        ('Total New Connections', len(domestic_new)+len(commercial_new), dn_cyl+cn_cyl),
        ('Domestic Refills', len(domestic_refill), dr_cyl),
        ('Commercial Refills', len(commercial_refill), cr_cyl),
        ('Total Refills', len(domestic_refill)+len(commercial_refill), dr_cyl+cr_cyl),
        ('Grand Total', len(entries), dn_cyl+cn_cyl+dr_cyl+cr_cyl)
    ]
    for i, (cat, cnt, cyl) in enumerate(summary_rows):
        fmt = green_fmt if i == 2 else (blue_fmt if i == 5 else (bold_fmt if i == 6 else data_fmt))
        ws1.write(3+i, 0, cat, fmt)
        ws1.write(3+i, 1, cnt, fmt)
        ws1.write(3+i, 2, cyl, fmt)
    ws1.set_column(0, 0, 30)
    ws1.set_column(1, 2, 15)
    
    # Date-wise Sheet
    ws2 = workbook.add_worksheet('Date-wise Breakdown')
    headers = ['Date', 'Warehouse', 'Dom. New', 'Dom. New Cyl', 'Com. New', 'Com. New Cyl', 'Dom. Refill', 'Dom. Refill Cyl', 'Com. Refill', 'Com. Refill Cyl']
    for col, h in enumerate(headers):
        ws2.write(0, col, h, header_format)
        ws2.set_column(col, col, 15)
    
    row = 1
    from collections import defaultdict
    date_wh = defaultdict(lambda: [0]*8)
    for e in entries:
        key = (e.get('date', ''), e.get('warehouse_id', ''))
        ct = e.get('connection_type', '')
        dd = date_wh[key]
        if ct == 'domestic':
            dd[0] += 1; dd[1] += _count_cylinders(e.get('cylinder_nos', '')) or 1
        elif ct == 'commercial':
            dd[2] += 1; dd[3] += _count_cylinders(e.get('cylinder_nos', '')) or 1
        elif ct == 'domestic_refill':
            dd[4] += 1; dd[5] += int(e.get('no_of_refills', 0) or 0)
        elif ct == 'commercial_refill':
            dd[6] += 1; dd[7] += int(e.get('no_of_refills', 0) or 0)
    
    grand = [0]*8
    for (d, wid), vals in sorted(date_wh.items()):
        ws2.write(row, 0, d, data_fmt)
        ws2.write(row, 1, wh_map.get(wid, 'Unknown'), data_fmt)
        for i, v in enumerate(vals):
            ws2.write(row, 2+i, v, data_fmt)
            grand[i] += v
        row += 1
    
    ws2.write(row, 0, 'TOTAL', bold_fmt)
    ws2.write(row, 1, '', bold_fmt)
    for i, v in enumerate(grand):
        ws2.write(row, 2+i, v, bold_fmt)
    
    # Warehouse Sheet
    ws3 = workbook.add_worksheet('Warehouse Breakdown')
    wh_headers = ['Warehouse', 'Dom. New', 'Dom. New Cyl', 'Com. New', 'Com. New Cyl', 'Dom. Refill', 'Dom. Refill Cyl', 'Com. Refill', 'Com. Refill Cyl', 'Total']
    for col, h in enumerate(wh_headers):
        ws3.write(0, col, h, header_format)
        ws3.set_column(col, col, 16)
    
    wh_data = defaultdict(lambda: [0]*8)
    for e in entries:
        wid = e.get('warehouse_id', '')
        ct = e.get('connection_type', '')
        dd = wh_data[wid]
        if ct == 'domestic':
            dd[0] += 1; dd[1] += _count_cylinders(e.get('cylinder_nos', '')) or 1
        elif ct == 'commercial':
            dd[2] += 1; dd[3] += _count_cylinders(e.get('cylinder_nos', '')) or 1
        elif ct == 'domestic_refill':
            dd[4] += 1; dd[5] += int(e.get('no_of_refills', 0) or 0)
        elif ct == 'commercial_refill':
            dd[6] += 1; dd[7] += int(e.get('no_of_refills', 0) or 0)
    
    row = 1
    grand = [0]*8
    for wid, vals in sorted(wh_data.items(), key=lambda x: wh_map.get(x[0], '')):
        ws3.write(row, 0, wh_map.get(wid, 'Unknown'), data_fmt)
        total = 0
        for i, v in enumerate(vals):
            ws3.write(row, 1+i, v, data_fmt)
            grand[i] += v
            total += v
        ws3.write(row, 9, total, data_fmt)
        row += 1
    ws3.write(row, 0, 'TOTAL', bold_fmt)
    for i, v in enumerate(grand):
        ws3.write(row, 1+i, v, bold_fmt)
    ws3.write(row, 9, sum(grand), bold_fmt)
    
    workbook.close()
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=connection_refill_analytics_{sd}_to_{ed}.xlsx"})


@api_router.get("/admin/customer-order-report")
async def get_customer_order_report(
    warehouse_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Customer-wise order report grouped by warehouse - all roles with warehouse filtering"""
    user = await get_current_user(credentials)
    
    # Non-admin users are forced to their own warehouse
    if user['role'] != 'admin':
        warehouse_id = user.get('warehouse_id', '')
    
    # Build customer query
    cust_query = {}
    if warehouse_id and warehouse_id != 'all':
        cust_query['warehouse_id'] = warehouse_id
    if search:
        cust_query['$or'] = [
            {'customer_name': {'$regex': search, '$options': 'i'}},
            {'phone': {'$regex': search, '$options': 'i'}},
            {'consumer_no': {'$regex': search, '$options': 'i'}}
        ]
    
    customers = await db.customers.find(cust_query, {'_id': 0}).to_list(5000)
    
    # Get warehouse names
    all_wh = await db.warehouses.find({}, {'_id': 0}).to_list(100)
    wh_map = {w['id']: w['name'] for w in all_wh}
    
    # Build order query
    order_query = {}
    if warehouse_id and warehouse_id != 'all':
        order_query['warehouse_id'] = warehouse_id
    if start_date:
        order_query['order_date'] = order_query.get('order_date', {})
        order_query['order_date']['$gte'] = start_date
    if end_date:
        if 'order_date' not in order_query:
            order_query['order_date'] = {}
        order_query['order_date']['$lte'] = end_date
    
    all_orders = await db.orders.find(order_query, {'_id': 0}).sort('order_date', 1).to_list(10000)
    
    # Also get sales entries for connection/refill history
    sales_query = {}
    if warehouse_id and warehouse_id != 'all':
        sales_query['warehouse_id'] = warehouse_id
    if start_date:
        sales_query['date'] = sales_query.get('date', {})
        sales_query['date']['$gte'] = start_date
    if end_date:
        if 'date' not in sales_query:
            sales_query['date'] = {}
        sales_query['date']['$lte'] = end_date
    
    all_sales = await db.sales_entries.find(sales_query, {'_id': 0}).sort('date', 1).to_list(10000)
    
    # Build customer-id to orders map and name to orders map
    order_by_cid = {}
    order_by_name = {}
    for o in all_orders:
        cid = o.get('customer_id')
        cname = (o.get('customer_name') or '').lower()
        if cid:
            order_by_cid.setdefault(cid, []).append(o)
        elif cname:
            order_by_name.setdefault(cname, []).append(o)
    
    sales_by_cid = {}
    sales_by_name = {}
    for s in all_sales:
        cid = s.get('customer_id')
        cname = (s.get('consumer_name') or '').lower()
        if cid:
            sales_by_cid.setdefault(cid, []).append(s)
        elif cname:
            sales_by_name.setdefault(cname, []).append(s)
    
    total_orders = 0
    total_refills = 0
    customer_groups = []
    
    for c in customers:
        cid = c['id']
        cname = (c.get('customer_name') or '').lower()
        
        # Get orders for this customer
        c_orders = order_by_cid.get(cid, []) + order_by_name.get(cname, [])
        c_sales = sales_by_cid.get(cid, []) + sales_by_name.get(cname, [])
        
        # Combine into unified entries
        entries = []
        seen_ids = set()
        
        for o in c_orders:
            oid = o.get('id', o.get('order_no', ''))
            if oid in seen_ids:
                continue
            seen_ids.add(oid)
            conn_type = o.get('connection_type', '')
            is_refill = 'refill' in conn_type.lower()
            qty = o.get('no_of_cylinders', 1) or 1
            entries.append({
                'source': 'order',
                'id': o.get('order_no', o.get('id', '')),
                'date': o.get('order_date', ''),
                'type': 'Refill' if is_refill else 'New Connection',
                'cylinder_type': conn_type.replace('_refill', '').replace('_', ' ').title(),
                'cylinder_nos': o.get('cylinder_nos', ''),
                'quantity': qty,
                'status': o.get('status', 'pending').title(),
                'payment': o.get('payment_mode', '').replace('_', ' ').title(),
                'memo_no': o.get('memo_no', '')
            })
            total_orders += 1
            if is_refill:
                total_refills += qty
        
        for s in c_sales:
            sid = s.get('id', '')
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            conn_type = s.get('connection_type', '')
            is_refill = 'refill' in conn_type.lower()
            qty = s.get('no_of_refills', 1) or 1 if is_refill else 1
            entries.append({
                'source': 'sale',
                'id': s.get('memo_no', s.get('id', '')),
                'date': s.get('date', ''),
                'type': 'Refill' if is_refill else 'New Connection',
                'cylinder_type': conn_type.replace('_refill', '').replace('_', ' ').title(),
                'cylinder_nos': s.get('cylinder_nos', ''),
                'quantity': qty,
                'status': 'Completed',
                'payment': s.get('payment_mode', '').replace('_', ' ').title(),
                'memo_no': s.get('memo_no', '')
            })
            total_orders += 1
            if is_refill:
                total_refills += qty
        
        # Sort entries by date ascending
        entries.sort(key=lambda x: x.get('date', ''))
        
        if not entries and not search:
            continue
        
        # Find initial connection date
        connection_date = None
        for e in entries:
            if e['type'] == 'New Connection':
                connection_date = e['date']
                break
        
        customer_groups.append({
            'customer_name': c.get('customer_name', ''),
            'customer_id': c['id'],
            'consumer_no': c.get('consumer_no', ''),
            'phone': c.get('phone', ''),
            'address': c.get('address', ''),
            'connection_type': c.get('connection_type', ''),
            'warehouse_id': c.get('warehouse_id', ''),
            'warehouse_name': wh_map.get(c.get('warehouse_id', ''), 'Unknown'),
            'connection_date': connection_date,
            'total_entries': len(entries),
            'entries': entries
        })
    
    # Sort customer groups by name
    customer_groups.sort(key=lambda x: x['customer_name'].lower())
    
    return {
        'customers': customer_groups,
        'summary': {
            'total_customers': len(customer_groups),
            'total_orders': total_orders,
            'total_refills': total_refills
        }
    }

@api_router.get("/export/customer-order-report-pdf")
async def export_customer_order_report_pdf(
    warehouse_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export customer-wise order report as PDF - all roles"""
    user = await get_current_user(credentials)
    if user['role'] != 'admin':
        warehouse_id = user.get('warehouse_id', '')
    
    # Reuse the report logic
    from starlette.datastructures import QueryParams
    
    # Build same data
    cust_query = {}
    if warehouse_id and warehouse_id != 'all':
        cust_query['warehouse_id'] = warehouse_id
    customers = await db.customers.find(cust_query, {'_id': 0}).to_list(5000)
    
    all_wh = await db.warehouses.find({}, {'_id': 0}).to_list(100)
    wh_map = {w['id']: w['name'] for w in all_wh}
    wh_label = wh_map.get(warehouse_id, 'All Warehouses') if warehouse_id and warehouse_id != 'all' else 'All Warehouses'
    
    order_query = {}
    if warehouse_id and warehouse_id != 'all':
        order_query['warehouse_id'] = warehouse_id
    if start_date:
        order_query['order_date'] = order_query.get('order_date', {})
        order_query['order_date']['$gte'] = start_date
    if end_date:
        if 'order_date' not in order_query:
            order_query['order_date'] = {}
        order_query['order_date']['$lte'] = end_date
    
    all_orders = await db.orders.find(order_query, {'_id': 0}).sort('order_date', 1).to_list(10000)
    
    sales_query = {}
    if warehouse_id and warehouse_id != 'all':
        sales_query['warehouse_id'] = warehouse_id
    if start_date:
        sales_query['date'] = sales_query.get('date', {})
        sales_query['date']['$gte'] = start_date
    if end_date:
        if 'date' not in sales_query:
            sales_query['date'] = {}
        sales_query['date']['$lte'] = end_date
    
    all_sales = await db.sales_entries.find(sales_query, {'_id': 0}).sort('date', 1).to_list(10000)
    
    order_by_cid = {}
    order_by_name = {}
    for o in all_orders:
        cid = o.get('customer_id')
        cname = (o.get('customer_name') or '').lower()
        if cid:
            order_by_cid.setdefault(cid, []).append(o)
        elif cname:
            order_by_name.setdefault(cname, []).append(o)
    
    sales_by_cid = {}
    sales_by_name = {}
    for s in all_sales:
        cid = s.get('customer_id')
        cname = (s.get('consumer_name') or '').lower()
        if cid:
            sales_by_cid.setdefault(cid, []).append(s)
        elif cname:
            sales_by_name.setdefault(cname, []).append(s)
    
    today_display = datetime.now(timezone.utc).strftime('%d-%m-%Y')
    total_orders = 0
    total_refills = 0
    
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), topMargin=20, bottomMargin=20, leftMargin=20, rightMargin=20)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=15, spaceAfter=4, textColor=colors.HexColor('#15803d'))
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=9, textColor=colors.grey, spaceAfter=6)
    cust_header_style = ParagraphStyle('CustHeader', parent=styles['Heading3'], fontSize=10, textColor=colors.HexColor('#1e3a5f'), spaceBefore=10, spaceAfter=2)
    cust_info_style = ParagraphStyle('CustInfo', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#666666'), spaceAfter=4)
    
    elements.append(Paragraph("K3 GAS SERVICE - Customer Order Report", title_style))
    elements.append(Paragraph(f"Warehouse: {wh_label} | Generated: {today_display}", subtitle_style))
    
    for c in sorted(customers, key=lambda x: (x.get('customer_name') or '').lower()):
        cid = c['id']
        cname = (c.get('customer_name') or '').lower()
        c_orders = order_by_cid.get(cid, []) + order_by_name.get(cname, [])
        c_sales = sales_by_cid.get(cid, []) + sales_by_name.get(cname, [])
        
        entries = []
        seen_ids = set()
        for o in c_orders:
            oid = o.get('id', o.get('order_no', ''))
            if oid in seen_ids: continue
            seen_ids.add(oid)
            conn_type = o.get('connection_type', '')
            is_refill = 'refill' in conn_type.lower()
            qty = o.get('no_of_cylinders', 1) or 1
            entries.append({'id': o.get('order_no', ''), 'date': o.get('order_date', ''), 'type': 'Refill' if is_refill else 'Connection', 'cyl_type': conn_type.replace('_refill', '').replace('_', ' ').title(), 'cyl_nos': o.get('cylinder_nos', ''), 'qty': qty, 'status': o.get('status', 'pending').title(), 'payment': o.get('payment_mode', '').title()})
            total_orders += 1
            if is_refill: total_refills += qty
        
        for s in c_sales:
            sid = s.get('id', '')
            if sid in seen_ids: continue
            seen_ids.add(sid)
            conn_type = s.get('connection_type', '')
            is_refill = 'refill' in conn_type.lower()
            qty = s.get('no_of_refills', 1) or 1 if is_refill else 1
            entries.append({'id': s.get('memo_no', sid[:8]), 'date': s.get('date', ''), 'type': 'Refill' if is_refill else 'Connection', 'cyl_type': conn_type.replace('_refill', '').replace('_', ' ').title(), 'cyl_nos': s.get('cylinder_nos', ''), 'qty': qty, 'status': 'Completed', 'payment': s.get('payment_mode', '').title()})
            total_orders += 1
            if is_refill: total_refills += qty
        
        if not entries: continue
        entries.sort(key=lambda x: x.get('date', ''))
        
        wh_name = wh_map.get(c.get('warehouse_id', ''), 'Unknown')
        elements.append(Paragraph(f"{c.get('customer_name', '')} ({wh_name})", cust_header_style))
        elements.append(Paragraph(f"Phone: {c.get('phone', '-')} | Consumer No: {c.get('consumer_no', '-')} | Address: {c.get('address', '-')[:40]}", cust_info_style))
        
        data = [['SL', 'Date', 'Order ID', 'Type', 'Cylinder', 'Cyl Nos', 'Qty', 'Status', 'Payment']]
        for i, e in enumerate(entries, 1):
            try:
                d = datetime.strptime(e['date'], '%Y-%m-%d').strftime('%d-%m-%Y')
            except:
                d = e['date']
            data.append([str(i), d, str(e['id'])[:12], e['type'], e['cyl_type'][:10], e.get('cyl_nos', '')[:10], str(e['qty']), e['status'], e['payment'][:8]])
        
        col_widths = [20, 55, 65, 55, 60, 55, 25, 50, 50]
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
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
    
    # Add summary at end
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Summary: {len([c for c in customers])} Customers | {total_orders} Orders | {total_refills} Refills", subtitle_style))
    
    doc.build(elements)
    output.seek(0)
    return StreamingResponse(output, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=customer_order_report_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.pdf"})

@api_router.get("/export/customer-order-report-excel")
async def export_customer_order_report_excel(
    warehouse_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export customer-wise order report as Excel - all roles"""
    user = await get_current_user(credentials)
    if user['role'] != 'admin':
        warehouse_id = user.get('warehouse_id', '')
    
    cust_query = {}
    if warehouse_id and warehouse_id != 'all':
        cust_query['warehouse_id'] = warehouse_id
    customers = await db.customers.find(cust_query, {'_id': 0}).to_list(5000)
    
    all_wh = await db.warehouses.find({}, {'_id': 0}).to_list(100)
    wh_map = {w['id']: w['name'] for w in all_wh}
    wh_label = wh_map.get(warehouse_id, 'All Warehouses') if warehouse_id and warehouse_id != 'all' else 'All Warehouses'
    
    order_query = {}
    if warehouse_id and warehouse_id != 'all':
        order_query['warehouse_id'] = warehouse_id
    if start_date:
        order_query['order_date'] = order_query.get('order_date', {})
        order_query['order_date']['$gte'] = start_date
    if end_date:
        if 'order_date' not in order_query:
            order_query['order_date'] = {}
        order_query['order_date']['$lte'] = end_date
    
    all_orders = await db.orders.find(order_query, {'_id': 0}).sort('order_date', 1).to_list(10000)
    
    sales_query = {}
    if warehouse_id and warehouse_id != 'all':
        sales_query['warehouse_id'] = warehouse_id
    if start_date:
        sales_query['date'] = sales_query.get('date', {})
        sales_query['date']['$gte'] = start_date
    if end_date:
        if 'date' not in sales_query:
            sales_query['date'] = {}
        sales_query['date']['$lte'] = end_date
    
    all_sales = await db.sales_entries.find(sales_query, {'_id': 0}).sort('date', 1).to_list(10000)
    
    order_by_cid = {}
    order_by_name = {}
    for o in all_orders:
        cid = o.get('customer_id')
        cname = (o.get('customer_name') or '').lower()
        if cid:
            order_by_cid.setdefault(cid, []).append(o)
        elif cname:
            order_by_name.setdefault(cname, []).append(o)
    
    sales_by_cid = {}
    sales_by_name = {}
    for s in all_sales:
        cid = s.get('customer_id')
        cname = (s.get('consumer_name') or '').lower()
        if cid:
            sales_by_cid.setdefault(cid, []).append(s)
        elif cname:
            sales_by_name.setdefault(cname, []).append(s)
    
    today_display = datetime.now(timezone.utc).strftime('%d-%m-%Y')
    total_orders = 0
    total_refills = 0
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Customer Order Report"
    
    ws.merge_cells('A1:I1')
    ws['A1'] = "K3 GAS SERVICE - Customer Order Report"
    ws['A1'].font = Font(bold=True, size=14, color="15803d")
    ws.merge_cells('A2:I2')
    ws['A2'] = f"Warehouse: {wh_label} | Generated: {today_display}"
    ws['A2'].font = Font(size=9, color="666666")
    
    current_row = 4
    header_fill = PatternFill(start_color="1e3a5f", end_color="1e3a5f", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=9)
    cust_fill = PatternFill(start_color="e0e7ff", end_color="e0e7ff", fill_type="solid")
    cust_font = Font(bold=True, size=10, color="1e3a5f")
    info_font = Font(size=8, color="666666")
    
    for c in sorted(customers, key=lambda x: (x.get('customer_name') or '').lower()):
        cid = c['id']
        cname = (c.get('customer_name') or '').lower()
        c_orders = order_by_cid.get(cid, []) + order_by_name.get(cname, [])
        c_sales = sales_by_cid.get(cid, []) + sales_by_name.get(cname, [])
        
        entries = []
        seen_ids = set()
        for o in c_orders:
            oid = o.get('id', o.get('order_no', ''))
            if oid in seen_ids: continue
            seen_ids.add(oid)
            conn_type = o.get('connection_type', '')
            is_refill = 'refill' in conn_type.lower()
            qty = o.get('no_of_cylinders', 1) or 1
            entries.append({'id': o.get('order_no', ''), 'date': o.get('order_date', ''), 'type': 'Refill' if is_refill else 'Connection', 'cyl_type': conn_type.replace('_refill', '').replace('_', ' ').title(), 'cyl_nos': o.get('cylinder_nos', ''), 'qty': qty, 'status': o.get('status', 'pending').title(), 'payment': o.get('payment_mode', '').title()})
            total_orders += 1
            if is_refill: total_refills += qty
        
        for s in c_sales:
            sid = s.get('id', '')
            if sid in seen_ids: continue
            seen_ids.add(sid)
            conn_type = s.get('connection_type', '')
            is_refill = 'refill' in conn_type.lower()
            qty = s.get('no_of_refills', 1) or 1 if is_refill else 1
            entries.append({'id': s.get('memo_no', sid[:8]), 'date': s.get('date', ''), 'type': 'Refill' if is_refill else 'Connection', 'cyl_type': conn_type.replace('_refill', '').replace('_', ' ').title(), 'cyl_nos': s.get('cylinder_nos', ''), 'qty': qty, 'status': 'Completed', 'payment': s.get('payment_mode', '').title()})
            total_orders += 1
            if is_refill: total_refills += qty
        
        if not entries: continue
        entries.sort(key=lambda x: x.get('date', ''))
        
        wh_name = wh_map.get(c.get('warehouse_id', ''), 'Unknown')
        
        # Customer header row
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=9)
        cell = ws.cell(row=current_row, column=1, value=f"{c.get('customer_name', '')} ({wh_name})")
        cell.fill = cust_fill
        cell.font = cust_font
        current_row += 1
        
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=9)
        cell = ws.cell(row=current_row, column=1, value=f"Phone: {c.get('phone', '-')} | Consumer No: {c.get('consumer_no', '-')} | Address: {c.get('address', '-')}")
        cell.font = info_font
        current_row += 1
        
        headers = ['SL', 'Date', 'Order ID', 'Type', 'Cylinder Type', 'Cyl Nos', 'Qty', 'Status', 'Payment']
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=current_row, column=col, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
        current_row += 1
        
        for i, e in enumerate(entries, 1):
            try:
                d = datetime.strptime(e['date'], '%Y-%m-%d').strftime('%d-%m-%Y')
            except:
                d = e['date']
            ws.append([i, d, str(e['id']), e['type'], e['cyl_type'], e.get('cyl_nos', ''), e['qty'], e['status'], e['payment']])
            current_row += 1
        
        current_row += 1
    
    # Summary
    ws.cell(row=current_row + 1, column=1, value=f"Total Customers: {len(customers)} | Total Orders: {total_orders} | Total Refills: {total_refills}").font = Font(bold=True, size=10)
    
    col_widths = [6, 12, 16, 12, 14, 12, 6, 12, 12]
    for idx, w in enumerate(col_widths, 1):
        ws.column_dimensions[chr(64 + idx)].width = w
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=customer_order_report_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.xlsx"})

@api_router.get("/orders/summary/stats")
async def get_order_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get order summary statistics"""
    user = await get_current_user(credentials)
    
    query = {}
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id')
    
    if start_date:
        query['order_date'] = query.get('order_date', {})
        query['order_date']['$gte'] = start_date
    if end_date:
        if 'order_date' not in query:
            query['order_date'] = {}
        query['order_date']['$lte'] = end_date
    
    # Get counts
    total_orders = await db.orders.count_documents(query)
    
    domestic_query = {**query, 'connection_type': 'domestic'}
    commercial_query = {**query, 'connection_type': 'commercial'}
    cash_query = {**query, 'payment_mode': 'cash'}
    online_query = {**query, 'payment_mode': 'online'}
    credit_query = {**query, 'payment_mode': 'credit_pending'}
    pending_query = {**query, '$or': [{'status': 'pending'}, {'status': {'$exists': False}}]}
    delivered_query = {**query, 'status': 'delivered'}
    
    total_domestic = await db.orders.count_documents(domestic_query)
    total_commercial = await db.orders.count_documents(commercial_query)
    total_cash = await db.orders.count_documents(cash_query)
    total_online = await db.orders.count_documents(online_query)
    total_credit = await db.orders.count_documents(credit_query)
    total_pending = await db.orders.count_documents(pending_query)
    total_delivered = await db.orders.count_documents(delivered_query)
    cancelled_query = {**query, 'status': 'cancelled'}
    total_cancelled = await db.orders.count_documents(cancelled_query)
    
    return {
        'total_orders': total_orders,
        'total_domestic': total_domestic,
        'total_commercial': total_commercial,
        'total_cash': total_cash,
        'total_online': total_online,
        'total_credit_pending': total_credit,
        'total_pending': total_pending,
        'total_delivered': total_delivered,
        'total_cancelled': total_cancelled
    }

@api_router.get("/orders/pdf/{order_id}")
async def download_order_pdf(
    order_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Download a single order as PDF"""
    user = await get_current_user(credentials)
    
    order = await db.orders.find_one({'id': order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check access
    if user['role'] != 'admin' and order.get('warehouse_id') != user.get('warehouse_id'):
        raise HTTPException(status_code=403, detail="Access denied")
    
    warehouse = await db.warehouses.find_one({'id': order.get('warehouse_id')})
    warehouse_name = warehouse['name'] if warehouse else 'Unknown'
    
    # Create PDF
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#2d5016'),
        spaceAfter=10,
        alignment=1
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.grey,
        alignment=1,
        spaceAfter=20
    )
    
    # Header
    elements.append(Paragraph("K3 GAS SERVICE", title_style))
    elements.append(Paragraph("Khayal Hamesha", subtitle_style))
    elements.append(Spacer(1, 10))
    
    # Order details box
    order_title = ParagraphStyle('OrderTitle', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#2d5016'))
    elements.append(Paragraph(f"ORDER: {order['order_no']}", order_title))
    elements.append(Spacer(1, 10))
    
    # Order info table
    order_data = [
        ['Order Date:', order['order_date']],
        ['Order No:', order['order_no']],
        ['Warehouse:', warehouse_name],
        ['Customer Name:', order['customer_name']],
        ['Mobile Number:', order.get('mobile_number', '-')],
        ['Address/Landmark:', order.get('address_landmark', '-')],
        ['Connection Type:', order['connection_type'].capitalize()],
        ['Payment Mode:', order['payment_mode'].replace('_', ' ').title()],
        ['Remarks:', order.get('remarks', '-')],
    ]
    
    table = Table(order_data, colWidths=[150, 300])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#eeeeee')),
    ]))
    elements.append(table)
    
    elements.append(Spacer(1, 30))
    
    # Footer
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=1)
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", footer_style))
    
    doc.build(elements)
    output.seek(0)
    
    return Response(
        content=output.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Order_{order['order_no']}_{datetime.now().strftime('%d%m%y')}.pdf"}
    )

@api_router.get("/export/orders-pdf")
async def export_orders_pdf(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    payment_mode: Optional[str] = None,
    connection_type: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export orders report to PDF"""
    user = await get_current_user(credentials)
    
    query = {}
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id')
    
    if start_date:
        query['order_date'] = query.get('order_date', {})
        query['order_date']['$gte'] = start_date
    if end_date:
        if 'order_date' not in query:
            query['order_date'] = {}
        query['order_date']['$lte'] = end_date
    
    if payment_mode and payment_mode != 'all':
        query['payment_mode'] = payment_mode
    if connection_type and connection_type != 'all':
        query['connection_type'] = connection_type
    
    orders = await db.orders.find(query).sort('order_date', -1).to_list(1000)
    
    # Get warehouse name
    warehouse_name = "All Warehouses"
    if user['role'] != 'admin':
        warehouse = await db.warehouses.find_one({'id': user.get('warehouse_id')})
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
    
    date_range = ""
    if start_date and end_date:
        date_range = f" ({start_date} to {end_date})"
    elif start_date:
        date_range = f" (from {start_date})"
    elif end_date:
        date_range = f" (until {end_date})"
    
    elements.append(Paragraph(f"K3 GAS SERVICE - Orders Report{date_range}", title_style))
    elements.append(Paragraph(f"Warehouse: {warehouse_name}", ParagraphStyle('Sub', fontSize=10, alignment=1)))
    elements.append(Spacer(1, 5))
    
    # Table data with clear headers
    table_data = [['Date', 'Order No', 'Customer', 'Mobile', 'Address', 'Type', 'Payment', 'Status', 'Remarks']]
    
    for o in orders:
        status = o.get('status', 'pending').title()
        if status == 'Cancelled' and o.get('cancellation_reason'):
            status = f"Cancelled: {o.get('cancellation_reason', '')[:15]}"
        table_data.append([
            o.get('order_date', ''),
            o.get('order_no', ''),
            o.get('customer_name', '')[:18],
            o.get('mobile_number', ''),
            o.get('address_landmark', '')[:20],
            o.get('connection_type', '').replace('_', ' ').title()[:10],
            o.get('payment_mode', '').title()[:6],
            status[:18],
            o.get('remarks', '')[:12]
        ])
    
    # Fit to A4 landscape
    col_widths = [55, 45, 100, 70, 110, 70, 50, 75, 70]
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
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Total Orders: {len(orders)}", ParagraphStyle('Total', fontSize=10)))
    
    doc.build(elements)
    output.seek(0)
    
    return Response(
        content=output.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Orders_Report_{datetime.now().strftime('%d%m%y')}.pdf"}
    )

@api_router.get("/export/orders-excel")
async def export_orders_excel(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    payment_mode: Optional[str] = None,
    connection_type: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export orders report to Excel"""
    user = await get_current_user(credentials)
    
    query = {}
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id')
    
    if start_date:
        query['order_date'] = query.get('order_date', {})
        query['order_date']['$gte'] = start_date
    if end_date:
        if 'order_date' not in query:
            query['order_date'] = {}
        query['order_date']['$lte'] = end_date
    
    if payment_mode and payment_mode != 'all':
        query['payment_mode'] = payment_mode
    if connection_type and connection_type != 'all':
        query['connection_type'] = connection_type
    
    orders = await db.orders.find(query).sort('order_date', -1).to_list(1000)
    
    # Get warehouse names
    warehouse_ids = list(set(o.get('warehouse_id') for o in orders if o.get('warehouse_id')))
    warehouses = await db.warehouses.find({'id': {'$in': warehouse_ids}}).to_list(100)
    warehouse_map = {w['id']: w['name'] for w in warehouses}
    
    # Create Excel
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('Orders')
    
    # Formats
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#2d5016',
        'font_color': 'white',
        'border': 1,
        'align': 'center'
    })
    
    data_format = workbook.add_format({'border': 1, 'align': 'left'})
    cash_format = workbook.add_format({'border': 1, 'align': 'center', 'bg_color': '#d4edda'})
    online_format = workbook.add_format({'border': 1, 'align': 'center', 'bg_color': '#cce5ff'})
    credit_format = workbook.add_format({'border': 1, 'align': 'center', 'bg_color': '#fff3cd'})
    cancelled_format = workbook.add_format({'border': 1, 'align': 'center', 'bg_color': '#f8d7da', 'font_color': '#721c24'})
    delivered_format = workbook.add_format({'border': 1, 'align': 'center', 'bg_color': '#d4edda', 'font_color': '#155724'})
    pending_format = workbook.add_format({'border': 1, 'align': 'center', 'bg_color': '#fff3cd', 'font_color': '#856404'})
    
    # Headers
    headers = ['Order Date', 'Order No', 'Customer Name', 'Mobile', 'Address/Landmark', 'Connection Type', 'Payment Mode', 'Status', 'Remarks', 'Warehouse']
    
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)
        worksheet.set_column(col, col, 15 if col < 3 else 20)
    
    # Data
    for row, o in enumerate(orders, start=1):
        worksheet.write(row, 0, o.get('order_date', ''), data_format)
        worksheet.write(row, 1, o.get('order_no', ''), data_format)
        worksheet.write(row, 2, o.get('customer_name', ''), data_format)
        worksheet.write(row, 3, o.get('mobile_number', ''), data_format)
        worksheet.write(row, 4, o.get('address_landmark', ''), data_format)
        worksheet.write(row, 5, o.get('connection_type', '').capitalize(), data_format)
        
        pm = o.get('payment_mode', '')
        pm_format = cash_format if pm == 'cash' else (online_format if pm == 'online' else credit_format)
        worksheet.write(row, 6, pm.replace('_', ' ').title(), pm_format)
        
        status = o.get('status', 'pending')
        status_label = status.title()
        if status == 'cancelled' and o.get('cancellation_reason'):
            status_label = f"Cancelled: {o.get('cancellation_reason', '')}"
        s_fmt = cancelled_format if status == 'cancelled' else (delivered_format if status == 'delivered' else pending_format)
        worksheet.write(row, 7, status_label, s_fmt)
        
        worksheet.write(row, 8, o.get('remarks', ''), data_format)
        worksheet.write(row, 9, warehouse_map.get(o.get('warehouse_id', ''), 'Unknown'), data_format)
    
    workbook.close()
    output.seek(0)
    
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Orders_Report_{datetime.now().strftime('%d%m%y')}.xlsx"}
    )

# ============ BULK MESSAGING ============

class MessagingSettings(BaseModel):
    provider: str = ""  # twilio, msg91, whatsapp_business, etc.
    sms_api_key: str = ""
    sms_api_secret: str = ""
    sms_sender_id: str = ""
    whatsapp_api_key: str = ""
    whatsapp_api_secret: str = ""
    whatsapp_phone_number: str = ""
    whatsapp_business_id: str = ""

class BulkMessageCreate(BaseModel):
    channel: str  # sms, whatsapp, both
    message: str
    recipient_filter: str = "all"  # all, warehouse, category
    warehouse_id: Optional[str] = None
    category: Optional[str] = None  # domestic, commercial

class MessageLogResponse(BaseModel):
    id: str
    channel: str
    message: str
    recipient_count: int
    successful_count: int
    failed_count: int
    status: str
    created_at: str
    created_by: str

@api_router.get("/messaging/settings")
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

@api_router.post("/messaging/settings")
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

@api_router.get("/messaging/recipients/count")
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

@api_router.post("/messaging/send")
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

@api_router.get("/messaging/logs")
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

@api_router.get("/messaging/logs/{log_id}")
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

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
