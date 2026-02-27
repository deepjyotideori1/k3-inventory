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
    
    # Generate filename based on report type
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
        headers={"Content-Disposition": f"attachment; filename=accessory_report_{datetime.now().strftime('%Y%m%d')}.pdf"}
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
        headers={"Content-Disposition": f"attachment; filename=accessory_report_{datetime.now().strftime('%Y%m%d')}.xlsx"}
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
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get customers for the user's warehouse (or all for admin)"""
    user = await get_current_user(credentials)
    
    query = {}
    
    # Filter by warehouse for non-admin users
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id')
    
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
    """Update a customer (admin only)"""
    user = await get_current_user(credentials)
    
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admin can edit customers")
    
    existing = await db.customers.find_one({'id': customer_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Customer not found")
    
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
    """Delete a customer (admin only)"""
    user = await get_current_user(credentials)
    
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admin can delete customers")
    
    result = await db.customers.delete_one({'id': customer_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return {"message": "Customer deleted successfully"}

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

@api_router.get("/customers/summary")
async def get_customer_summary(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get customer summary statistics"""
    user = await get_current_user(credentials)
    
    query = {}
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id')
    
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
        'Date (YYYY-MM-DD)',
        'Connection Type (domestic/commercial)',
        'Customer Name',
        'Address',
        'Phone',
        'Consumer No',
        'Cash Memo No',
        'Cylinder Nos',
        'Gas Card Issued (yes/no)',
        'KYC Done (yes/no)',
        'Remarks'
    ]
    
    # Set column widths
    column_widths = [18, 30, 25, 35, 15, 15, 15, 15, 22, 18, 30]
    for i, width in enumerate(column_widths):
        worksheet.set_column(i, i, width)
    
    # Write headers
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)
    
    # Sample data rows
    sample_data = [
        ['2026-02-23', 'domestic', 'Rahul Sharma', 'House No. 123, Itanagar', '9876543210', 'CON001', 'CM001', 'CYL-001, CYL-002', 'yes', 'yes', 'Regular customer'],
        ['2026-02-23', 'commercial', 'ABC Restaurant', 'Market Complex, Naharlagun', '9876543211', 'CON002', 'CM002', 'CYL-003', 'no', 'yes', 'New connection'],
        ['2026-02-22', 'domestic', 'Priya Devi', 'Ward No. 5, Doimukh', '9876543212', 'CON003', 'CM003', 'CYL-004, CYL-005', 'yes', 'no', ''],
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
    instructions.write(2, 0, '1. Date Format: Use YYYY-MM-DD format (e.g., 2026-02-23)', instruction_format)
    instructions.write(3, 0, '2. Connection Type: Must be either "domestic" or "commercial" (lowercase)', instruction_format)
    instructions.write(4, 0, '3. Customer Name: Required field - cannot be empty', instruction_format)
    instructions.write(5, 0, '4. Phone: Customer mobile number for SMS/WhatsApp messaging (10+ digits)', instruction_format)
    instructions.write(6, 0, '5. Gas Card Issued: Use "yes" or "no" (lowercase)', instruction_format)
    instructions.write(7, 0, '6. KYC Done: Use "yes" or "no" (lowercase)', instruction_format)
    instructions.write(8, 0, '7. Delete the sample data rows before uploading your actual data', instruction_format)
    instructions.write(9, 0, '8. Do not modify the header row', instruction_format)
    
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
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export customers to PDF"""
    user = await get_current_user(credentials)
    
    query = {}
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id')
    
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
    
    # Create PDF
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#2d5016'),
        spaceAfter=20,
        alignment=1
    )
    
    category_text = category.capitalize() if category and category != 'all' else 'All'
    title = Paragraph(f"K3 GAS SERVICE - {category_text} Customer Report", title_style)
    elements.append(title)
    
    subtitle = Paragraph(f"Warehouse: {warehouse_name}", styles['Normal'])
    elements.append(subtitle)
    elements.append(Spacer(1, 20))
    
    # Table data
    table_data = [['Date', 'Type', 'Customer Name', 'Phone', 'Address', 'Consumer No', 'Gas Card', 'KYC']]
    
    for c in customers:
        table_data.append([
            c.get('date', ''),
            c.get('connection_type', '').capitalize(),
            c.get('customer_name', '')[:20],
            c.get('phone', ''),
            c.get('address', '')[:25],
            c.get('consumer_no', ''),
            'Yes' if c.get('gas_card_issued') else 'No',
            'Yes' if c.get('kyc_done') else 'No'
        ])
    
    # Create table
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d5016')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')])
    ]))
    
    elements.append(table)
    
    # Summary
    elements.append(Spacer(1, 20))
    domestic_count = sum(1 for c in customers if c.get('connection_type') == 'domestic')
    commercial_count = sum(1 for c in customers if c.get('connection_type') == 'commercial')
    summary = Paragraph(f"Total: {len(customers)} customers (Domestic: {domestic_count}, Commercial: {commercial_count})", styles['Normal'])
    elements.append(summary)
    
    doc.build(elements)
    output.seek(0)
    
    return Response(
        content=output.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=customers_{category or 'all'}_{datetime.now().strftime('%Y%m%d')}.pdf"}
    )

@api_router.get("/export/customers-excel")
async def export_customers_excel(
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export customers to Excel"""
    user = await get_current_user(credentials)
    
    query = {}
    if user['role'] != 'admin':
        query['warehouse_id'] = user.get('warehouse_id')
    
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
    
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=customers_{category or 'all'}_{datetime.now().strftime('%Y%m%d')}.xlsx"}
    )

# ============ ORDER MANAGEMENT ============

class OrderCreate(BaseModel):
    order_date: str
    customer_id: Optional[str] = None  # Existing customer
    customer_name: str
    mobile_number: str = ""
    address_landmark: str = ""
    connection_type: str = "domestic"  # domestic or commercial
    payment_mode: str = "cash"  # cash, online, credit_pending
    remarks: str = ""

class OrderUpdate(BaseModel):
    order_date: Optional[str] = None
    customer_name: Optional[str] = None
    mobile_number: Optional[str] = None
    address_landmark: Optional[str] = None
    connection_type: Optional[str] = None
    payment_mode: Optional[str] = None
    remarks: Optional[str] = None
    status: Optional[str] = None  # pending, delivered

class OrderStatusUpdate(BaseModel):
    status: str  # pending, delivered

async def get_next_order_number(warehouse_id: str) -> str:
    """Generate next order number for a warehouse (A1, A2, A3...)"""
    # Find the highest order number for this warehouse
    latest_order = await db.orders.find_one(
        {'warehouse_id': warehouse_id},
        sort=[('order_sequence', -1)]
    )
    
    if latest_order and 'order_sequence' in latest_order:
        next_seq = latest_order['order_sequence'] + 1
    else:
        next_seq = 1
    
    return f"A{next_seq}", next_seq

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
            'payment_mode': o['payment_mode'],
            'status': o.get('status', 'pending'),
            'remarks': o.get('remarks', ''),
            'created_by': o.get('created_by', ''),
            'created_at': o.get('created_at', ''),
            'delivered_at': o.get('delivered_at')
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
    """Update an order (admin only or same day by creator)"""
    user = await get_current_user(credentials)
    
    existing = await db.orders.find_one({'id': order_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check access - admin can edit any, others can edit same-day orders they created
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    if user['role'] != 'admin':
        if existing.get('created_by') != user['id']:
            raise HTTPException(status_code=403, detail="You can only edit your own orders")
        if existing.get('order_date') != today:
            raise HTTPException(status_code=403, detail="You can only edit today's orders")
    
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
    """Update order status (Pending → Delivered)"""
    user = await get_current_user(credentials)
    
    existing = await db.orders.find_one({'id': order_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check warehouse access
    if user['role'] != 'admin' and existing.get('warehouse_id') != user.get('warehouse_id'):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if status_update.status not in ['pending', 'delivered']:
        raise HTTPException(status_code=400, detail="Invalid status. Must be 'pending' or 'delivered'")
    
    update_data = {
        'status': status_update.status,
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    if status_update.status == 'delivered':
        update_data['delivered_at'] = datetime.now(timezone.utc).isoformat()
    elif status_update.status == 'pending':
        update_data['delivered_at'] = None
    
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
    
    return {
        'total_orders': total_orders,
        'total_domestic': total_domestic,
        'total_commercial': total_commercial,
        'total_cash': total_cash,
        'total_online': total_online,
        'total_credit_pending': total_credit,
        'total_pending': total_pending,
        'total_delivered': total_delivered
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
        headers={"Content-Disposition": f"attachment; filename=order_{order['order_no']}_{order['order_date']}.pdf"}
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
    
    # Create PDF
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#2d5016'),
        spaceAfter=20,
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
    elements.append(Paragraph(f"Warehouse: {warehouse_name}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Table data
    table_data = [['Date', 'Order No', 'Customer', 'Mobile', 'Address', 'Type', 'Payment', 'Remarks']]
    
    for o in orders:
        table_data.append([
            o.get('order_date', ''),
            o.get('order_no', ''),
            o.get('customer_name', '')[:20],
            o.get('mobile_number', ''),
            o.get('address_landmark', '')[:25],
            o.get('connection_type', '').capitalize(),
            o.get('payment_mode', '').replace('_', ' ').title(),
            o.get('remarks', '')[:15]
        ])
    
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d5016')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')])
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"Total Orders: {len(orders)}", styles['Normal']))
    
    doc.build(elements)
    output.seek(0)
    
    return Response(
        content=output.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=orders_report_{datetime.now().strftime('%Y%m%d')}.pdf"}
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
    
    # Headers
    headers = ['Order Date', 'Order No', 'Customer Name', 'Mobile', 'Address/Landmark', 'Connection Type', 'Payment Mode', 'Remarks', 'Warehouse']
    
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
        
        worksheet.write(row, 7, o.get('remarks', ''), data_format)
        worksheet.write(row, 8, warehouse_map.get(o.get('warehouse_id', ''), 'Unknown'), data_format)
    
    workbook.close()
    output.seek(0)
    
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=orders_report_{datetime.now().strftime('%Y%m%d')}.xlsx"}
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
    
    # Get customers and filter to those with valid phone numbers (10+ digits)
    customers = await db.customers.find(query).to_list(10000)
    
    # Filter to those with phone numbers (matching send endpoint logic)
    valid_recipients = []
    for c in customers:
        phone = c.get('mobile_number') or c.get('phone') or ''
        if phone and len(phone) >= 10:
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
    
    # Filter to those with phone numbers
    recipients = []
    for c in customers:
        phone = c.get('mobile_number') or c.get('phone') or ''
        if phone and len(phone) >= 10:
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
