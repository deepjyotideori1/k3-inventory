from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any


# ============ USER MODELS ============

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
    role: str
    warehouse_id: Optional[str] = None
    linked_employee_id: Optional[str] = None

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
    allowed_dashboards: Optional[list] = None
    linked_employee_id: Optional[str] = None
    created_at: str
    visible_password: Optional[str] = None

class ResetPasswordRequest(BaseModel):
    new_password: Optional[str] = None

class LoginResponse(BaseModel):
    token: str
    user: UserResponse

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


# ============ WAREHOUSE MODELS ============

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


# ============ INVENTORY MODELS ============

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


# ============ DAILY REPORT MODELS ============

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
    status: str = "draft"

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


# ============ PLANT REPORT MODELS ============

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
    delivery_15kg: List[Dict[str, Any]] = []
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


# ============ SETTINGS MODELS ============

class SettingsResponse(BaseModel):
    maintenance_mode: bool
    maintenance_message: str
    app_version: str

class SettingsUpdate(BaseModel):
    maintenance_mode: Optional[bool] = None
    maintenance_message: Optional[str] = None


# ============ STOCK MODELS ============

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


# ============ DEALER MODELS ============

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


# ============ ACCESSORY MODELS ============

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


# ============ ACCESSORY SALES MODELS ============

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
    payment_mode: str = "cash"
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


# ============ PLANT ISSUANCE MODELS ============

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


# ============ CUSTOMER MODELS ============

class CustomerCreate(BaseModel):
    date: str
    connection_type: str
    customer_name: str
    address: str = ""
    phone: str = ""
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


# ============ SALES MODELS ============

class SalesEntryCreate(BaseModel):
    date: str
    customer_id: Optional[str] = None
    consumer_name: str
    address: str = ""
    consumer_no: str = ""
    memo_no: str = ""
    amount: float = 0
    connection_type: str = "domestic"
    cylinder_nos: str = ""
    payment_mode: str = "cash"
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


# ============ ORDER MODELS ============

class OrderCreate(BaseModel):
    order_date: str
    customer_id: Optional[str] = None
    customer_name: str
    mobile_number: str = ""
    address_landmark: str = ""
    connection_type: str = "domestic"
    cylinder_nos: str = ""
    payment_mode: str = "cash"
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
    status: Optional[str] = None

class OrderStatusUpdate(BaseModel):
    status: str
    cancellation_reason: Optional[str] = None


# ============ MESSAGING MODELS ============

class MessagingSettings(BaseModel):
    provider: str = ""
    sms_api_key: str = ""
    sms_api_secret: str = ""
    sms_sender_id: str = ""
    whatsapp_api_key: str = ""
    whatsapp_api_secret: str = ""
    whatsapp_phone_number: str = ""
    whatsapp_business_id: str = ""

class BulkMessageCreate(BaseModel):
    channel: str
    message: str
    recipient_filter: str = "all"
    warehouse_id: Optional[str] = None
    category: Optional[str] = None

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
