from fastapi import FastAPI
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from datetime import datetime, timezone
import uuid

from database import db, client
from helpers import hash_password, init_jwt_secret

# Route modules
from routes.auth import router as auth_router
from routes.warehouses import router as warehouses_router
from routes.reports import router as reports_router
from routes.plant import router as plant_router
from routes.dashboard import router as dashboard_router
from routes.audit import router as audit_router
from routes.stock import router as stock_router
from routes.exports import router as exports_router
from routes.dealers import router as dealers_router
from routes.accessories import router as accessories_router
from routes.customers import router as customers_router
from routes.sales import router as sales_router
from routes.orders import router as orders_router
from routes.analytics import router as analytics_router
from routes.messaging import router as messaging_router
from routes.hrms import router as hrms_router
from routes.hrms_payroll import router as hrms_payroll_router
from routes.hrms_attendance import router as hrms_attendance_router

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# JWT settings
JWT_SECRET = os.environ.get('JWT_SECRET', 'k3gas_secret_key_2024_secure')
init_jwt_secret(JWT_SECRET)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create the main app
app = FastAPI(title="K3 GAS SERVICE API", version="1.0.0")

# ============ CORS MIDDLEWARE (must be before routes) ============

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ INITIALIZATION ============

async def init_default_data():
    """Initialize default warehouses, users, and settings"""
    try:
        settings = await db.settings.find_one({'key': 'app_settings'}, {'_id': 0})
        if settings:
            return

        logger.info("Initializing default data...")

        await db.settings.insert_one({
            'key': 'app_settings',
            'maintenance_mode': False,
            'maintenance_message': 'System is under maintenance. Please check back later.',
            'app_version': '1.0.0'
        })

        warehouses = [
            {'id': str(uuid.uuid4()), 'name': 'Jullang', 'location': 'Jullang, Arunachal Pradesh', 'is_plant': False, 'is_active': True, 'created_at': datetime.now(timezone.utc).isoformat()},
            {'id': str(uuid.uuid4()), 'name': 'Naharlagun', 'location': 'Naharlagun, Arunachal Pradesh', 'is_plant': False, 'is_active': True, 'created_at': datetime.now(timezone.utc).isoformat()},
            {'id': str(uuid.uuid4()), 'name': 'Doimukh', 'location': 'Doimukh, Arunachal Pradesh', 'is_plant': False, 'is_active': True, 'created_at': datetime.now(timezone.utc).isoformat()},
            {'id': str(uuid.uuid4()), 'name': 'Plant Hollongi', 'location': 'Hollongi, Arunachal Pradesh', 'is_plant': True, 'is_active': True, 'created_at': datetime.now(timezone.utc).isoformat()},
        ]
        await db.warehouses.insert_many(warehouses)

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

        warehouse_users = [
            {'id': str(uuid.uuid4()), 'email': 'jullang@k3gas.com', 'password': hash_password('Jullang@123'), 'name': 'Jullang Manager', 'role': 'warehouse_manager', 'warehouse_id': warehouses[0]['id'], 'created_at': datetime.now(timezone.utc).isoformat()},
            {'id': str(uuid.uuid4()), 'email': 'naharlagun@k3gas.com', 'password': hash_password('Naharlagun@123'), 'name': 'Naharlagun Manager', 'role': 'warehouse_manager', 'warehouse_id': warehouses[1]['id'], 'created_at': datetime.now(timezone.utc).isoformat()},
            {'id': str(uuid.uuid4()), 'email': 'doimukh@k3gas.com', 'password': hash_password('Doimukh@123'), 'name': 'Doimukh Manager', 'role': 'warehouse_manager', 'warehouse_id': warehouses[2]['id'], 'created_at': datetime.now(timezone.utc).isoformat()},
            {'id': str(uuid.uuid4()), 'email': 'hollongi@k3gas.com', 'password': hash_password('Hollongi@123'), 'name': 'Plant Hollongi Manager', 'role': 'warehouse_manager', 'warehouse_id': warehouses[3]['id'], 'created_at': datetime.now(timezone.utc).isoformat()},
        ]
        await db.users.insert_many(warehouse_users)

        items = [
            {'id': str(uuid.uuid4()), 'name': '15kg Cylinder', 'unit': 'units', 'category': 'LPG Cylinder', 'created_at': datetime.now(timezone.utc).isoformat()},
            {'id': str(uuid.uuid4()), 'name': '21kg Cylinder', 'unit': 'units', 'category': 'LPG Cylinder', 'created_at': datetime.now(timezone.utc).isoformat()},
        ]
        await db.inventory_items.insert_many(items)

        logger.info("Default data initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing default data: {e}")


@app.on_event("startup")
async def startup_event():
    try:
        await init_default_data()
        await db.sales_entries.create_index([("consumer_name", 1)])
        await db.sales_entries.create_index([("date", 1)])
        await db.sales_entries.create_index([("warehouse_id", 1)])
        logger.info("Startup complete - all indexes created")
    except Exception as e:
        logger.error(f"Startup error (non-fatal): {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


# ============ INCLUDE ROUTERS (all under /api prefix) ============

app.include_router(auth_router, prefix="/api")
app.include_router(warehouses_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(plant_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(stock_router, prefix="/api")
app.include_router(exports_router, prefix="/api")
app.include_router(dealers_router, prefix="/api")
app.include_router(accessories_router, prefix="/api")
app.include_router(customers_router, prefix="/api")
app.include_router(sales_router, prefix="/api")
app.include_router(orders_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(messaging_router, prefix="/api")
app.include_router(hrms_router, prefix="/api")
app.include_router(hrms_payroll_router, prefix="/api")
app.include_router(hrms_attendance_router, prefix="/api")


# ============ HEALTH CHECK ============

@app.get("/api/health")
async def health():
    return {"status": "healthy"}
