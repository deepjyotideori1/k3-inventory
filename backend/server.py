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
    closing_15kg_filled: int = 0
    closing_21kg_filled: int = 0
    closing_15kg_empty: int = 0
    closing_21kg_empty: int = 0
    remarks: str = ""

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
    expected_15kg_filled = data.opening_15kg_filled - data.sold_15kg_filled + data.refilling_15kg + data.refilling_plant_15kg
    expected_21kg_filled = data.opening_21kg_filled - data.sold_21kg_filled + data.refilling_21kg + data.refilling_plant_21kg
    expected_15kg_empty = data.opening_15kg_empty + data.sold_15kg_filled - data.refilling_15kg - data.refilling_plant_15kg
    expected_21kg_empty = data.opening_21kg_empty + data.sold_21kg_filled - data.refilling_21kg - data.refilling_plant_21kg
    
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
        'submitted_by': user['name'],
        'submitted_at': datetime.now(timezone.utc).isoformat(),
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Check if report exists for same date and warehouse
    existing = await db.daily_reports.find_one({'warehouse_id': data.warehouse_id, 'date': data.date}, {'_id': 0})
    if existing:
        await db.daily_reports.update_one({'id': existing['id']}, {'$set': report})
        report['id'] = existing['id']
    else:
        await db.daily_reports.insert_one(report)
    
    return DailyReportResponse(**report)

@api_router.get("/reports/daily", response_model=List[DailyReportResponse])
async def get_daily_reports(
    warehouse_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    query = {}
    if warehouse_id:
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
        if warehouse_id:
            query['warehouse_id'] = warehouse_id
        if start_date:
            query['date'] = {'$gte': start_date}
        if end_date:
            if 'date' in query:
                query['date']['$lte'] = end_date
            else:
                query['date'] = {'$lte': end_date}
        
        reports = await db.daily_reports.find(query, {'_id': 0}).sort('date', -1).to_list(1000)
        
        elements.append(Paragraph(f"Daily Inventory Report", styles['Heading2']))
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
        if warehouse_id:
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
