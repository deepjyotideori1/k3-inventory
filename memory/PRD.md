# K3 GAS SERVICE - Inventory Dashboard PRD

## Original Problem Statement
Build an Inventory Dashboard for K3 GAS SERVICE business with tagline "Khayal Hamesha". The system manages LPG cylinder inventory across multiple warehouses with comprehensive reporting and discrepancy detection.

## User Personas
1. **Master Admin** - Full system access, manages warehouses, users, settings, views all reports, can edit any report/customer/order
2. **Warehouse Manager** - Manages daily stock entries, customers, and orders for assigned warehouse, views own reports
3. **Plant Hollongi Manager** - Special role for managing the refilling plant with bullet tank tracking and dealer reports (NO order management)

## Core Requirements
- JWT-based authentication with role-based access control
- 5 warehouses: Jullang, Naharlagun, Doimukh, Plant Hollongi
- LPG cylinder tracking: 15kg and 21kg (Filled and Empty)
- Daily stock entry forms with opening/closing balance
- Auto-carry forward of closing stock to next day's opening
- Stock discrepancy detection and alerts
- Reports with PDF and Excel export
- Dealer management for Plant Hollongi
- LPG Accessories management for admin
- Customer management per warehouse
- Order management per warehouse (except Plant Hollongi)

---

## COMPLETED FEATURES

### Authentication & Users
- [x] JWT authentication with bcrypt password hashing
- [x] Role-based access control (Admin vs Warehouse Manager)
- [x] User management CRUD operations
- [x] Protected routes based on user role

### Warehouse Management
- [x] Warehouse listing and stock overview
- [x] Admin stock update for all warehouses
- [x] Plant Hollongi special tracking (bullet tank)

### Daily Reports System
- [x] Daily stock entry form with all fields
- [x] **System Calculated Closing Stock** (read-only, auto-calculated)
  - Filled = Opening - Sold - Refilling (Local) + Received from Plant
  - Empty = Opening + Refilling (Local) - Refilling at Plant
- [x] **Delivery Received from Plant** - Auto-synced from Plant Hollongi deliveries
- [x] **Save as Draft** - Save reports before final submission
- [x] **Edit Report** - Managers can edit their own reports
- [x] **Admin Edit Access** - Master admin can edit any report
- [x] Discrepancy detection and warning alerts
- [x] **Reports filtered by user** - Each user sees only their warehouse data

### Plant Hollongi Features
- [x] Bullet tank tracking (in Kg)
- [x] Cylinder stock management
- [x] Delivery to warehouses tracking (manual entry, no auto-sync to warehouses)
- [x] Empties received from warehouses (auto-synced from warehouse "Refilling at Plant" entries)
- [x] **Warehouses Recorded Receipt (Reference)** - Notification showing what warehouses recorded as received from Plant

### Warehouse Daily Entry Features
- [x] **Received from Plant (Manual Entry)** - Warehouses manually enter filled cylinders received
- [x] **Reference Notification** - Shows what Plant Hollongi recorded as delivered (informational only)

### Dealer Reports (Plant Hollongi)
- [x] Add/manage dealers
- [x] Daily entry for cylinder issuance (15kg/21kg issued, refilled)
- [x] Date-wise entries with dealer selection
- [x] **Search functionality** - Search by dealer name and date
- [x] **Total Issued Till Date** - Dealers tab shows total issued quantities per dealer
- [x] Dealer-wise summary with grand totals
- [x] PDF and Excel export for dealer reports
- [x] **Download All-Time Report** - Export complete issuance history

### LPG Accessories (Admin Only)
- [x] Add/manage LPG accessories (Regulator, Pipe, Burner, etc.)
- [x] Add/manage accessory dealers (separate from cylinder dealers)
- [x] Daily entry per dealer per accessory:
  - Total Issued
  - Total Sold
  - **Total Remaining (Auto-calculated: Issued - Sold)**
- [x] Accessory-wise dealer summary
- [x] PDF and Excel export for accessory reports

### Customer Management (Feb 23, 2026)
- [x] **Warehouse-specific customers** - Each warehouse stores customers separately
- [x] **Warehouse Filter (Admin)** - Admin can filter customers by warehouse
- [x] Customer data fields:
  - Date, Connection Type (Domestic/Commercial), Customer Name, Address
  - Consumer No, Cash Memo No, Cylinder Nos
  - Gas Card Issued (Yes/No), KYC Done (Yes/No), Remarks
- [x] **Add Single Customer** - Form with all fields
- [x] **Bulk Upload** - Upload customers via Excel file
- [x] **Sample Excel Download** - Template with correct format and instructions
- [x] **View Customers** - List with search, category filter, date range filter
- [x] **Warehouse Isolation** - Managers only see their own warehouse customers
- [x] **Admin Full Access** - Admin sees all warehouses with edit/delete
- [x] **PDF Export** - Category-wise customer list
- [x] **Excel Export** - Category-wise customer list
- [x] **Summary Cards** - Total, Domestic, Commercial, Gas Card Issued, KYC Done

### Sales Dashboard (Dec 2025)
- [x] **Daily Sales Entry** - Log daily sales data for all warehouses
- [x] **Sales Entry Fields** - Date, Consumer Name, Address, Consumer No, Memo No, Amount, Connection Type, Cylinder Nos, Payment Mode, Refills, Remarks
- [x] **Connection Types** - Domestic, Domestic Refill, Commercial, Commercial Refill
- [x] **New Connection Mode** - Shows Domestic/Commercial connection types only (no refill options), with Cylinder Nos field
- [x] **Existing Customer Mode** - Shows Domestic Refill/Commercial Refill connection types only, with No of Refills field (no cylinder nos)
- [x] **Customer Auto-Fill** - When selecting existing customer, consumer name, address, consumer no, memo no, and remarks are auto-filled
- [x] **Fields Disabled After Selection** - Customer fields become read-only after selection to prevent accidental edits
- [x] **Quick Refill Feature** - One-click refill for top 8 frequent customers with pre-filled data (amount, payment mode)
- [x] **Payment Mode Support** - Cash, Online, Pending
- [x] **Summary Cards** - Cash Collection, Online Collection, Pending Collection, Accessory Sales, Grand Total (combined cylinder + accessory)
- [x] **Accessory Sales Integration** - Accessory sales shown in summary card and merged into main sales table with "Accessory" badge
- [x] **Combined Sales Table** - Unified view of cylinder and accessory sales sorted by date, with type badges
- [x] **Grand Total Card** - Shows combined total (Cylinder + Accessory amounts) with breakdown
- [x] **Filtering** - By warehouse (admin), payment mode, date range (Today/Week/Month/Year/Custom)
- [x] **Search** - Search by consumer, memo
- [x] **PDF/Excel Export** - Export consolidated sales data (cylinder + accessory) with section subtotals and grand total
- [x] **Export Connection Type Filter** - Filter exports by: All Types, Domestic New Connection, Commercial New Connection, Domestic Refill, Commercial Refill
- [x] **Edit Entry** - Update existing sales entries
- [x] **Delete Entry** - Remove sales entries with confirmation
- [x] **Role-Based Access** - Admin sees all warehouses; managers/sales executives see their assigned warehouse only

### LPG Accessories Sales Module (March 2026)
- [x] **Accessory Sales Page** - Dedicated page for creating/viewing accessory sales
- [x] **Multi-Item Sales** - Sales entries with multiple accessory items, quantities, and unit prices
- [x] **Memo No Field** - Memo number tracking for accessory sales
- [x] **Automatic Inventory Deduction** - Stock auto-deducted when accessory sale is created
- [x] **Dedicated Exports** - PDF and Excel exports for accessory-only reports
- [x] **Integrated in Main Dashboard** - Accessory sales data shown in main Sales Dashboard summary cards and table

### Sales Executive Role (Dec 2025)
- [x] **New User Role** - sales_executive with restricted access
- [x] **Warehouse Assignment** - Each sales executive assigned to a specific warehouse
- [x] **Limited Sidebar** - Only Customers, Orders, and Sales Data visible
- [x] **Data Isolation** - Can only view/manage data for their assigned warehouse
- [x] **Plant Hollongi Excluded** - Sales executives cannot be assigned to Plant Hollongi

### Order Management (Feb 23, 2026)
- [x] **Order Generation Dashboard** - All warehouses except Plant Hollongi
- [x] **Auto Order Sequence** - Warehouse-specific prefixes (J1, J2... for Jullang, N1, N2... for Naharlagun, D1, D2... for Doimukh)
- [x] Order data fields:
  - Order Date, Order No (Auto-generated), Customer Name, Mobile Number
  - Address/Landmark, Connection Type (Domestic/Commercial/Domestic Refill/Commercial Refill)
  - Payment Mode (Cash/Online/Credit-Pending), Remarks
  - Cylinder Nos (for new customer connection types only)
- [x] **New Customer Mode** - Shows Domestic/Commercial connection types with Cylinder Nos field
- [x] **Select Existing Mode** - Shows Domestic Refill/Commercial Refill connection types (no cylinder nos field)
- [x] **Auto-Fill Customer Data** - When selecting existing customer, fields auto-populate correctly
- [x] **Add New Customer** - Option to add customer while creating order
- [x] **Individual Order PDF** - Download single order as PDF
- [x] **Order Reports View** with filters:
  - Period: Daily, Weekly, Monthly, Yearly, Custom
  - Payment Mode filter
  - Connection Type filter (including refill types)
  - Status filter (Pending/Delivered)
  - Search by name, mobile, order no, address
- [x] **PDF/Excel Export** - Export order reports
- [x] **Edit Order** - Managers can edit same-day orders; Admin can edit any
- [x] **Delete Order** - Admin only
- [x] **Plant Hollongi Exclusion** - No Orders link in sidebar, API returns 403
- [x] **Summary Cards** - Total Orders, Pending, Delivered, Domestic, Commercial, Cash, Online, Credit

### Order Status Tracking (Feb 23, 2026)
- [x] **Status Field** - Orders have status: Pending → Delivered
- [x] **Status Badges** - Visual indicators (Orange=Pending, Green=Delivered)
- [x] **Status Dropdown** - Update status directly from table row
- [x] **Status Filter** - Filter orders by Pending, Delivered, or All Status
- [x] **Pending/Delivered Counts** - Summary cards show status counts
- [x] **Delivered Timestamp** - Tracks when order was marked as delivered
- [x] **PATCH API** - `/orders/{id}/status` endpoint for status updates

### Bulk Messaging (Feb 23, 2026) - PLACEHOLDER
- [x] **Admin-only Feature** - Only Master Admin can access
- [x] **Bulk Messaging Page** - Accessible at /bulk-messaging
- [x] **Compose Message Tab** - Channel selection (SMS/WhatsApp/Both), message textarea
- [x] **Recipients Selection** - Filter by All Customers, By Warehouse, By Category
- [x] **Recipient Count Display** - Shows total recipients with phone numbers
- [x] **Message History Tab** - View past sent messages with status
- [x] **API Settings Tab** - Configure SMS and WhatsApp API credentials
- [x] **Provider Configuration** - Support for Twilio, MSG91, Meta WhatsApp Business API
- [x] **Simulated Mode** - Messages simulated when API not configured
- [x] **Customer Phone Field** - Added phone field to customer schema for messaging
- [x] **Phone in Customer Table** - Phone column visible in Customer Management
- [x] **Phone in Add/Edit Forms** - Phone input field in customer forms
- [x] **Updated Excel Template** - Bulk upload template includes Phone column
- [x] **Message Logs API** - Track sent messages with success/failure counts
- **Note:** This is a PLACEHOLDER implementation. Real message sending requires API integration.

### Export Features
- [x] PDF export using ReportLab
- [x] Excel export using XlsxWriter
- [x] Exports filtered by user role (managers see only their data)
- [x] **Indian Rupee Formatting** - All Sales exports display amounts in ₹XX,XX,XXX format
- [x] **Clear Export Headers** - PDF and Excel exports have descriptive column headers
- [x] **Export Date Range Filters** - Filter by Daily, Weekly, Monthly, Custom date ranges
- [x] **Export Connection Type Filters** - Filter by Domestic, Commercial, Refill types
- [x] **Sales Summary Reports** - Period-based summary exports (Daily/Weekly/Monthly totals) with payment mode and connection type breakdowns

### Reports System Overhaul (March 2026)
- [x] **Comprehensive Warehouse Reports** - Detailed cards with Opening Stock, Day Activities, Received from Plant, Closing Stock
- [x] **Comprehensive Plant Reports** - Detailed cards with Bullet Tank, Opening Stock, Day Activities, Empty Received, Closing Stock
- [x] **Plant Hollongi Manager View Fix** - Plant managers now see their own plant reports on /reports page
- [x] **Descriptive Export Headers** - Warehouse report exports use clear column names (e.g., "Refill to plant 15kg" instead of "ToPl15")
- [x] **Standardized PDF Format** - All PDFs use A4 size, fit-to-page, consistent fonts (Header: bold 14pt, Body: 13pt)
- [x] **Sync Logic Removed** - Warehouse and Plant forms are now pure manual entry (no auto-sync between forms)
- [x] **Sales Summary Reports** - Period-based exports (Daily/Weekly/Monthly) with payment mode and connection type breakdowns
- [x] **Warehouse-Specific Order Numbers** - Orders get warehouse prefixes (J-1 for Jullang, N-1 for Naharlagun, D-1 for Doimukh)
- [x] **Customer Warehouse Filter** - Admin can filter customers by specific warehouse

### Dashboard Cylinder Stock Summary (March 2026)
- [x] **Redesigned Top Stats Cards** - Total Warehouses, Total Filled Cylinders (green, 15kg/21kg shown separately), Total Empty Cylinders (orange, 15kg/21kg separately), Stock Discrepancies
- [x] **Cylinder Stock Summary Widget** - Large visual counters for Filled (green) vs Empty (orange) with percentage progress bars
- [x] **Auto-Refresh** - Dashboard auto-refreshes every 30 seconds with countdown badge and toggle button
- [x] **Cylinder Type Filter** - Filter by All Types, 15kg Only, or 21kg Only
- [x] **Warehouse Filter** - Filter by specific warehouse or view all
- [x] **Expandable Warehouse Breakdown** - Table showing per-warehouse stock with Plant Hollongi row and TOTAL row
- [x] **Role-Based Access** - Only admin sees full warehouse-level details; managers see their own dashboard

### Admin Order Analysis Dashboard (March 2026)
- [x] **Order Analysis Tab** - New tab in Admin Dashboard between Warehouse Overview and Stock Discrepancies
- [x] **Filters** - Warehouse dropdown, Status (All/Pending/Delivered/Cancelled), Date range (Today/Week/Month/Year/Custom), Search bar
- [x] **Summary Cards** - Total Orders with Qty, Pending, Delivered, Warehouse-wise breakdown
- [x] **Date-grouped Orders** - Orders grouped by date (descending) with headers showing count, full order details per row
- [x] **Export** - PDF and Excel exports with date-wise grouping, warehouse label, and summary section
- [x] **Admin-only Access** - All endpoints require admin role, non-admin gets 403

### Customer Order Report - All Roles Access (March 2026)
- [x] **Order Report accessible to all roles** - Admin, Warehouse Managers, and Sales Executives can view and export
- [x] **Auto-warehouse filtering** - Non-admin users see only their assigned warehouse data
- [x] **Warehouse dropdown hidden** for non-admin users (auto-filtered)
- [x] **PDF/Excel exports** work for all roles (filtered to their warehouse)
- [x] **Sidebar link** added for managers and sales executives

### Customer LPG Refill Tracking (March 2026)
- [x] **Refill Status API** - Backend aggregates last refill date per customer from sales entries
- [x] **Customer Dashboard** - "Last Refill" and "Days Since" columns with color-coded badges (Green <=15d, Yellow 16-30d, Red >30d)
- [x] **Order Management** - Last refill info panel shown when selecting existing customer (date, days, color badge, alert if overdue)
- [x] **Refill Status Export** - PDF and Excel reports with color-coded days, summary stats (total, recent, moderate, overdue, no history)
- [x] **Export Buttons** - "Refill PDF" and "Refill Excel" on Customer Dashboard

### Dashboard Analytics - Connections & Refills (March 2026)
- [x] **Analytics Tab** on Dashboard with chart icon
- [x] **Time Period Filters**: Daily, Monthly, Quarterly, Yearly, Custom Range
- [x] **Warehouse Filter**: All Warehouses or individual warehouse selection
- [x] **New Connections Summary Cards**: Total New, Domestic New, Commercial New with cylinder counts
- [x] **Refill Activity Summary Cards**: Total Refills, Domestic Refills, Commercial Refills with cylinder counts
- [x] **Warehouse Breakdown Table**: Per-warehouse metrics with totals
- [x] **Date-wise Breakdown Table**: Per-date metrics with TOTAL row
- [x] **PDF Export**: Full report with summary and date-wise breakdown
- [x] **Excel Export**: 3-sheet workbook (Summary, Date-wise, Warehouse Breakdown)
- [x] **Role-based Access**: Non-admin users auto-filtered to their warehouse
- [x] **Data Integrity**: Uses sales_entries (completed transactions), excludes pending/cancelled orders

### Order Cancellation Feature (March 2026)
- [x] **Cancel Order Status** - New "Cancelled" status alongside Pending and Delivered
- [x] **Confirmation Dialog** - Modal with optional cancellation reason textarea before cancelling
- [x] **Read-Only Cancelled Orders** - Cancelled orders cannot be edited (400 error), edit button hidden
- [x] **Visual Indicators** - Red badge, red row background (bg-red-50), cancellation reason shown
- [x] **Summary Card** - Red "Cancelled" summary card with count in Order Management
- [x] **Status Filter** - Filter orders by All/Pending/Delivered/Cancelled
- [x] **Exports** - PDF and Excel exports include Status column with cancelled status and reason
- [x] **Sales Exclusion** - Cancelled orders do not affect refill tracking (uses sales_entries, not orders)
- [x] **Admin Revert** - Admin can revert cancelled orders back to pending
- [x] **Order Analysis** - Admin dashboard order analysis includes total_cancelled count

### Sales → Customer Auto-Creation Fix (March 2026)
- [x] **New Connection sales auto-create customer** - When a "Domestic" or "Commercial" new connection sale is created, a customer record is auto-created in the customers collection
- [x] **Both endpoints fixed** - Manager endpoint and admin warehouse-specific endpoint both auto-create customers
- [x] **Sales entry linked** - The sales entry's `customer_id` is updated to reference the newly created customer

### UI/UX
- [x] Professional green theme matching gas/energy industry
- [x] K3 Gas Service logo integration
- [x] Responsive sidebar navigation
- [x] Bento grid dashboard layout
- [x] Toast notifications for actions
- [x] Loading states and error handling

---

## TECHNICAL STACK

### Frontend
- React 19 with Vite
- Tailwind CSS for styling
- Shadcn/UI components
- Axios for API calls
- React Router for navigation
- XLSX library for Excel parsing

### Backend
- FastAPI (Python)
- Motor (MongoDB async driver)
- PyJWT for authentication
- bcrypt for password hashing
- ReportLab for PDF generation
- XlsxWriter for Excel generation

### Database
- MongoDB with collections:
  - users, warehouses, daily_reports, plant_reports, plant_stock
  - dealers, dealer_entries
  - accessories, accessory_dealers, accessory_entries
  - customers
  - **orders** (NEW)

---

## API ENDPOINTS

### Authentication
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Get current user

### Daily Reports
- `POST /api/reports/daily` - Create daily report
- `GET /api/reports/daily` - List reports (filtered by role)
- `PUT /api/reports/daily/{report_id}` - Update report

### Customers
- `GET /api/customers` - List customers (filtered by warehouse)
- `POST /api/customers` - Create customer
- `PUT /api/customers/{customer_id}` - Update customer (admin)
- `DELETE /api/customers/{customer_id}` - Delete customer (admin)
- `POST /api/customers/bulk` - Bulk upload customers
- `GET /api/customers/sample-excel` - Download template

### Orders (NEW)
- `GET /api/orders` - List orders (filtered by warehouse)
- `POST /api/orders` - Create order (warehouse user)
- `POST /api/orders/warehouse/{warehouse_id}` - Create order (admin)
- `GET /api/orders/{order_id}` - Get single order
- `PUT /api/orders/{order_id}` - Update order
- `DELETE /api/orders/{order_id}` - Delete order (admin)
- `GET /api/orders/summary/stats` - Order statistics
- `GET /api/orders/pdf/{order_id}` - Download single order PDF
- `GET /api/export/orders-pdf` - Export orders report PDF
- `GET /api/export/orders-excel` - Export orders report Excel

### Messaging (NEW - Placeholder)
- `GET /api/messaging/settings` - Get messaging API configuration
- `POST /api/messaging/settings` - Update messaging API credentials
- `GET /api/messaging/recipients/count` - Get recipient count with filters
- `POST /api/messaging/send` - Send bulk message (simulated if no API)
- `GET /api/messaging/logs` - Get message history
- `GET /api/messaging/logs/{log_id}` - Get message detail

### Exports
- `GET /api/export/pdf` - Export daily reports PDF
- `GET /api/export/excel` - Export daily reports Excel
- `GET /api/export/dealer-pdf` - Export dealer reports PDF
- `GET /api/export/dealer-excel` - Export dealer reports Excel
- `GET /api/export/customers-pdf` - Export customers PDF
- `GET /api/export/customers-excel` - Export customers Excel
- `GET /api/export/sales-summary-pdf` - Export sales summary PDF (group_by: daily/weekly/monthly)
- `GET /api/export/sales-summary-excel` - Export sales summary Excel (group_by: daily/weekly/monthly)

---

## DEFAULT CREDENTIALS

| Role | Email | Password | Warehouse |
|------|-------|----------|-----------|
| Master Admin | admin@k3gas.com | Admin@123 | All |
| Sales Executive | sales@k3gas.com | Sales@123 | Jullang |
| Jullang Manager | jullang@k3gas.com | Jullang@123 | Jullang |
| Naharlagun Manager | naharlagun@k3gas.com | Naharlagun@123 | Naharlagun |
| Doimukh Manager | doimukh@k3gas.com | Doimukh@123 | Doimukh |
| Plant Hollongi | hollongi@k3gas.com | Hollongi@123 | Plant Hollongi |

---

## PENDING/FUTURE TASKS

### P0 (Complete)
- [x] Integrate Accessory Sales into Main Sales Dashboard (March 13, 2026)

### P1 (Important)
- [ ] Complete Dynamic Search Integration - Add SearchBar.jsx to SalesDashboard, Reports, and all remaining data tables
- [ ] Admin UI to add new warehouses with credentials
- [ ] Admin UI to add new inventory stock items
- [ ] Sync warehouse 'refilling at plant' to Plant Hollongi's received empties

### P2 (Nice to Have)
- [ ] Refactor backend/server.py into smaller modules using FastAPI APIRouter
- [ ] Migrate client-side search to server-side for scalability
- [ ] Integrate real SMS/WhatsApp provider (Twilio, MSG91, Meta) with Bulk Messaging
- [ ] Weekly, Monthly, Yearly aggregated reports for dashboard
- [ ] Dashboard charts/graphs using Recharts
- [ ] Email notifications for discrepancies
- [ ] Audit log for stock changes
- [ ] Under Maintenance mode UI

---

## FILE STRUCTURE

```
/app/
├── backend/
│   ├── .env
│   ├── requirements.txt
│   ├── server.py
│   └── tests/
│       ├── test_dealer_reports.py
│       ├── test_customer_management.py
│       ├── test_order_management.py
│       └── test_bulk_messaging.py (NEW)
├── frontend/
│   ├── .env
│   ├── package.json
│   ├── public/
│   │   └── k3-logo.png
│   └── src/
│       ├── App.js
│       ├── context/AuthContext.jsx
│       ├── lib/api.js
│       ├── lib/utils.js
│       ├── components/
│       │   ├── Layout.jsx
│       │   └── ui/ (Shadcn components)
│       └── pages/
│           ├── Dashboard.jsx
│           ├── ManagerDashboard.jsx
│           ├── DailyEntry.jsx
│           ├── PlantEntry.jsx
│           ├── Reports.jsx
│           ├── AdminEditReport.jsx
│           ├── DealerReports.jsx
│           ├── AccessoryReports.jsx
│           ├── CustomerManagement.jsx
│           ├── OrderManagement.jsx
│           ├── BulkMessaging.jsx (NEW)
│           ├── Warehouses.jsx
│           ├── Users.jsx
│           ├── Settings.jsx
│           └── Login.jsx
├── memory/
│   └── PRD.md
└── test_reports/
    ├── iteration_1.json
    ├── iteration_2.json
    ├── iteration_3.json
    └── iteration_4.json
```

---

*Last Updated: March 13, 2026*
