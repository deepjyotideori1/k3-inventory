from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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

# PDF and Excel imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import xlsxwriter

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
    role: str  # 'admin' or 'warehouse_manager'
    warehouse_id: Optional[str] = None

class UserCreate(BaseModel):
    email: str
    password: str
    name: str
    role: str
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
            created_at=u['created_at']
        ))
    return result

@api_router.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate, user: dict = Depends(require_admin)):
    existing = await db.users.find_one({'email': data.email}, {'_id': 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    new_user = {
        'id': str(uuid.uuid4()),
        'email': data.email,
        'password': hash_password(data.password),
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
        created_at=new_user['created_at']
    )

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(require_admin)):
    result = await db.users.delete_one({'id': user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}

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
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=20, alignment=1)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=12, spaceAfter=10, alignment=1)
    
    elements.append(Paragraph("K3 GAS SERVICE", title_style))
    elements.append(Paragraph("Khayal Hamesha", subtitle_style))
    elements.append(Spacer(1, 20))
    
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
        
        elements.append(Paragraph(f"Daily Inventory Report - {warehouse_name}", styles['Heading2']))
        if start_date and end_date:
            elements.append(Paragraph(f"Period: {start_date} to {end_date}", styles['Normal']))
        elements.append(Spacer(1, 10))
        
        data = [['Date', 'Warehouse', '15kg Filled', '21kg Filled', '15kg Empty', '21kg Empty', 'Discrepancy']]
        for r in reports:
            disc = "Yes" if r['has_discrepancy'] else "No"
            data.append([
                r['date'],
                r['warehouse_name'],
                r['closing_15kg_filled'],
                r['closing_21kg_filled'],
                r['closing_15kg_empty'],
                r['closing_21kg_empty'],
                disc
            ])
        
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#15803d')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
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
        
        elements.append(Paragraph(f"Plant Hollongi Report", styles['Heading2']))
        if start_date and end_date:
            elements.append(Paragraph(f"Period: {start_date} to {end_date}", styles['Normal']))
        elements.append(Spacer(1, 10))
        
        data = [['Date', 'Bullet Tank (kg)', '15kg Filled', '21kg Filled', '15kg Empty', '21kg Empty', 'Refilled 15kg', 'Refilled 21kg']]
        for r in reports:
            data.append([
                r['date'],
                r['closing_bullet_tank_kg'],
                r['closing_15kg_filled'],
                r['closing_21kg_filled'],
                r['closing_15kg_empty'],
                r['closing_21kg_empty'],
                r['day_refilled_15kg'],
                r['day_refilled_21kg']
            ])
        
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#15803d')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=k3_gas_report_{datetime.now().strftime('%Y%m%d')}.pdf"}
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
    header_format = workbook.add_format({'bold': True, 'bg_color': '#15803d', 'font_color': 'white', 'align': 'center', 'border': 1})
    cell_format = workbook.add_format({'align': 'center', 'border': 1})
    title_format = workbook.add_format({'bold': True, 'font_size': 16, 'align': 'center'})
    
    worksheet.merge_range('A1:H1', 'K3 GAS SERVICE - Khayal Hamesha', title_format)
    
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
        
        headers = ['Date', 'Warehouse', 'Opening 15kg', 'Opening 21kg', 'Sold 15kg', 'Sold 21kg', 'Closing 15kg', 'Closing 21kg', 'Discrepancy 15kg', 'Discrepancy 21kg']
        for col, header in enumerate(headers):
            worksheet.write(2, col, header, header_format)
        
        for row, r in enumerate(reports, start=3):
            worksheet.write(row, 0, r['date'], cell_format)
            worksheet.write(row, 1, r['warehouse_name'], cell_format)
            worksheet.write(row, 2, r['opening_15kg_filled'], cell_format)
            worksheet.write(row, 3, r['opening_21kg_filled'], cell_format)
            worksheet.write(row, 4, r['sold_15kg_filled'], cell_format)
            worksheet.write(row, 5, r['sold_21kg_filled'], cell_format)
            worksheet.write(row, 6, r['closing_15kg_filled'], cell_format)
            worksheet.write(row, 7, r['closing_21kg_filled'], cell_format)
            worksheet.write(row, 8, r['discrepancy_15kg_filled'], cell_format)
            worksheet.write(row, 9, r['discrepancy_21kg_filled'], cell_format)
    
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
        
        headers = ['Date', 'Bullet Tank (kg)', '15kg Filled', '21kg Filled', '15kg Empty', '21kg Empty', 'Refilled 15kg', 'Refilled 21kg']
        for col, header in enumerate(headers):
            worksheet.write(2, col, header, header_format)
        
        for row, r in enumerate(reports, start=3):
            worksheet.write(row, 0, r['date'], cell_format)
            worksheet.write(row, 1, r['closing_bullet_tank_kg'], cell_format)
            worksheet.write(row, 2, r['closing_15kg_filled'], cell_format)
            worksheet.write(row, 3, r['closing_21kg_filled'], cell_format)
            worksheet.write(row, 4, r['closing_15kg_empty'], cell_format)
            worksheet.write(row, 5, r['closing_21kg_empty'], cell_format)
            worksheet.write(row, 6, r['day_refilled_15kg'], cell_format)
            worksheet.write(row, 7, r['day_refilled_21kg'], cell_format)
    
    workbook.close()
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=k3_gas_report_{datetime.now().strftime('%Y%m%d')}.xlsx"}
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
        headers={"Content-Disposition": f"attachment; filename=dealer_report_{datetime.now().strftime('%Y%m%d')}.pdf"}
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
        headers={"Content-Disposition": f"attachment; filename=dealer_report_{datetime.now().strftime('%Y%m%d')}.xlsx"}
    )

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
