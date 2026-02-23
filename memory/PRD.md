# K3 GAS SERVICE - Inventory Dashboard PRD

## Original Problem Statement
Build an Inventory Dashboard for K3 GAS SERVICE business with tagline "Khayal Hamesha". The system manages LPG cylinder inventory across multiple warehouses with comprehensive reporting and discrepancy detection.

## User Personas
1. **Master Admin** - Full system access, manages warehouses, users, settings, views all reports, can edit any report/customer
2. **Warehouse Manager** - Manages daily stock entries and customers for assigned warehouse, views own reports
3. **Plant Hollongi Manager** - Special role for managing the refilling plant with bullet tank tracking and dealer reports

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
- [x] Delivery to warehouses tracking
- [x] Empties received from warehouses

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

### Customer Management (NEW - Feb 23, 2026)
- [x] **Warehouse-specific customers** - Each warehouse stores customers separately
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

### Export Features
- [x] PDF export using ReportLab
- [x] Excel export using XlsxWriter
- [x] Exports filtered by user role (managers see only their data)

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
  - **customers** (NEW)

---

## API ENDPOINTS

### Authentication
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Get current user

### Daily Reports
- `POST /api/reports/daily` - Create daily report
- `GET /api/reports/daily` - List reports (filtered by role)
- `GET /api/reports/daily/today/{warehouse_id}` - Get today's report
- `PUT /api/reports/daily/{report_id}` - Update report
- `GET /api/reports/daily/latest/{warehouse_id}` - Get latest closing stock

### Plant Hollongi
- `POST /api/reports/plant` - Create plant report
- `GET /api/reports/plant` - List plant reports
- `GET /api/reports/warehouse-received-from-plant/{warehouse_id}/{date}` - Get deliveries

### Dealers (Cylinder)
- `GET /api/dealers` - List dealers
- `POST /api/dealers` - Create dealer
- `DELETE /api/dealers/{dealer_id}` - Delete dealer
- `POST /api/dealer-entries` - Create dealer entry
- `GET /api/dealer-entries` - List entries
- `GET /api/dealer-entries/summary` - Dealer summary

### Accessories
- `GET /api/accessories` - List accessories
- `POST /api/accessories` - Create accessory
- `DELETE /api/accessories/{accessory_id}` - Delete accessory
- `GET /api/accessory-dealers` - List accessory dealers
- `POST /api/accessory-dealers` - Create accessory dealer
- `POST /api/accessory-entries` - Create accessory entry

### Customers (NEW)
- `GET /api/customers` - List customers (filtered by warehouse for managers)
- `POST /api/customers` - Create customer (manager's warehouse)
- `POST /api/customers/warehouse/{warehouse_id}` - Create customer (admin only)
- `PUT /api/customers/{customer_id}` - Update customer (admin only)
- `DELETE /api/customers/{customer_id}` - Delete customer (admin only)
- `POST /api/customers/bulk` - Bulk upload customers
- `POST /api/customers/bulk/warehouse/{warehouse_id}` - Admin bulk upload
- `GET /api/customers/summary` - Customer statistics
- `GET /api/customers/sample-excel` - Download template

### Exports
- `GET /api/export/pdf` - Export daily reports PDF
- `GET /api/export/excel` - Export daily reports Excel
- `GET /api/export/dealer-pdf` - Export dealer reports PDF
- `GET /api/export/dealer-excel` - Export dealer reports Excel
- `GET /api/export/accessory-pdf` - Export accessory reports PDF
- `GET /api/export/accessory-excel` - Export accessory reports Excel
- `GET /api/export/customers-pdf` - Export customers PDF (NEW)
- `GET /api/export/customers-excel` - Export customers Excel (NEW)

---

## DEFAULT CREDENTIALS

| Role | Email | Password |
|------|-------|----------|
| Master Admin | admin@k3gas.com | Admin@123 |
| Jullang Manager | jullang@k3gas.com | Jullang@123 |
| Naharlagun Manager | naharlagun@k3gas.com | Naharlagun@123 |
| Doimukh Manager | doimukh@k3gas.com | Doimukh@123 |
| Plant Hollongi | hollongi@k3gas.com | Hollongi@123 |

---

## PENDING/FUTURE TASKS

### P1 (Important)
- [ ] Sync warehouse 'refilling at plant' to Plant Hollongi's received empties
- [ ] Admin UI to add new warehouses with credentials
- [ ] Admin UI to add new inventory stock items

### P2 (Nice to Have)
- [ ] Weekly, Monthly, Yearly aggregated reports
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
│       └── test_customer_management.py
├── frontend/
│   ├── .env
│   ├── package.json
│   ├── public/
│   │   └── k3-logo.png
│   └── src/
│       ├── App.js
│       ├── context/AuthContext.jsx
│       ├── lib/api.js
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
│           ├── CustomerManagement.jsx (NEW)
│           ├── Warehouses.jsx
│           ├── Users.jsx
│           ├── Settings.jsx
│           └── Login.jsx
├── memory/
│   └── PRD.md
└── test_reports/
    ├── iteration_1.json
    ├── iteration_2.json
    └── iteration_3.json
```

---

*Last Updated: February 23, 2026*
