# K3 GAS SERVICE - Inventory Dashboard PRD

## Original Problem Statement
Build an Inventory Dashboard for K3 GAS SERVICE business with tagline "Khayal Hamesha". The system manages LPG cylinder inventory across multiple warehouses with comprehensive reporting and discrepancy detection.

## User Personas
1. **Master Admin** - Full system access, manages warehouses, users, settings, views all reports, can edit any report
2. **Warehouse Manager** - Manages daily stock entries for assigned warehouse, views own reports, can save drafts and edit own reports
3. **Plant Hollongi Manager** - Special role for managing the refilling plant with bullet tank tracking

## Core Requirements (Static)
- JWT-based authentication
- Role-based access control (Admin vs Warehouse Manager)
- 5 warehouses: Jullang, Naharlagun, Doimukh, Plant Hollongi
- LPG cylinder tracking: 15kg and 21kg (Filled and Empty)
- Daily stock entry forms with opening/closing balance
- Auto-carry forward of closing stock to next day's opening
- Stock discrepancy detection and alerts
- Reports: Daily, Weekly, Monthly, Yearly
- PDF and Excel export functionality
- Maintenance mode toggle for admin
- Ability to add new warehouses and inventory items

## What's Been Implemented

### Session 1 (Feb 2026) - Core System
- [x] JWT authentication with role-based access
- [x] User management CRUD operations
- [x] Warehouse management with stock tracking
- [x] Daily reports with discrepancy calculation
- [x] Plant Hollongi special reports (bullet tank, deliveries, receipts)
- [x] Dashboard statistics aggregation
- [x] PDF export using ReportLab
- [x] Excel export using XlsxWriter
- [x] Maintenance mode settings

### Session 2 (Feb 20, 2026) - Enhanced Features
- [x] **System Calculated Closing Stock** - Auto-calculated read-only fields showing expected closing for 15kg/21kg filled/empty
- [x] **Delivery Received from Plant** - Auto-synced filled cylinders from Plant Hollongi deliveries
- [x] **Save as Draft** - Warehouse managers can save reports as draft before final submission
- [x] **Edit Report** - Warehouse managers can edit their draft reports
- [x] **Admin Edit Access** - Master admin can edit any report (submitted or draft) from Reports page
- [x] **Updated Stock Formula** - Filled = Opening - Sold - Refilling (Local) + Received from Plant | Empty = Opening + Refilling (Local) - Refilling at Plant
- [x] **Dealer Reports** - Full dealer management for Plant Hollongi with:
  - Add/manage dealers
  - Daily entry for cylinder issuance (15kg/21kg issued, 15kg/21kg refilled)
  - Date-wise entries with dealer selection
  - Dealer-wise summary with grand totals
  - PDF and Excel export for dealer reports

### Frontend Features
- [x] Professional login page with split-screen design
- [x] Master Admin Dashboard with Bento grid layout
- [x] Warehouse Manager Dashboard with quick actions
- [x] Daily Stock Entry Form with:
  - Opening stock (auto-filled from previous day)
  - Day activity (sold, refilling local, refilling at plant)
  - Delivery received from plant (auto-synced, read-only)
  - System calculated closing stock (read-only)
  - Actual closing stock (physical count)
  - Discrepancy detection and warning
  - Save as Draft / Submit buttons
  - Edit Report for submitted reports
- [x] Plant Hollongi Entry Form with warehouse selection
- [x] Reports page with filters and admin edit functionality
- [x] Admin Edit Report page with full override access
- [x] Green theme matching gas/energy industry
- [x] Responsive design with mobile sidebar

### Default Credentials
- Master Admin: admin@k3gas.com / Admin@123
- Jullang: jullang@k3gas.com / Jullang@123
- Naharlagun: naharlagun@k3gas.com / Naharlagun@123
- Doimukh: doimukh@k3gas.com / Doimukh@123
- Plant Hollongi: hollongi@k3gas.com / Hollongi@123

## Key Formulas
### Filled Cylinders Closing Stock
```
Closing = Opening - Sold - Refilling (Local) + Received from Plant
```

### Empty Cylinders Closing Stock
```
Closing = Opening + Refilling (Local) - Refilling at Plant Hollongi
```

## Prioritized Backlog

### P0 (Critical) - COMPLETED
- [x] Authentication system
- [x] Daily stock entry and reports
- [x] Discrepancy detection
- [x] PDF/Excel exports
- [x] System calculated closing stock
- [x] Delivery received from plant sync
- [x] Save as Draft / Edit Report
- [x] Admin edit access

### P1 (Important)
- [ ] Auto-sync warehouse 'refilling at plant' to Plant Hollongi's received empties (backend done)
- [ ] Email notifications for discrepancies
- [ ] Audit log for stock changes
- [ ] Dashboard charts/graphs using Recharts
- [ ] Admin UI to add new inventory stock items
- [ ] Admin UI to add new warehouses with credentials

### P2 (Nice to Have)
- [ ] Weekly, Monthly, Yearly aggregated reports
- [ ] Under Maintenance mode UI
- [ ] Bulk import/export of data
- [ ] Mobile app version
- [ ] SMS alerts for low stock

## Technical Stack
- Frontend: React 19, Tailwind CSS, Shadcn UI
- Backend: FastAPI, Motor (MongoDB async driver)
- Database: MongoDB
- Authentication: JWT with bcrypt password hashing
- Exports: ReportLab (PDF), XlsxWriter (Excel)

## API Endpoints
- `/api/auth/login` - User login
- `/api/auth/me` - Get current user
- `/api/reports/daily` - Create/list daily reports
- `/api/reports/daily/today/{warehouse_id}` - Get today's report (including drafts)
- `/api/reports/daily/{report_id}` - Update report (PUT)
- `/api/reports/warehouse-received-from-plant/{warehouse_id}/{date}` - Get plant deliveries
- `/api/reports/plant` - Plant Hollongi reports
- `/api/stock/update` - Admin stock update
- `/api/stock/plant-update` - Admin plant stock update
- `/api/dashboard/stats` - Dashboard statistics
- `/api/export/pdf` - PDF export
- `/api/export/excel` - Excel export
- `/api/dealers` - CRUD for dealers
- `/api/dealer-entries` - Dealer daily entries
- `/api/dealer-entries/summary` - Dealer-wise summary with totals
- `/api/export/dealer-pdf` - Dealer report PDF export
- `/api/export/dealer-excel` - Dealer report Excel export
