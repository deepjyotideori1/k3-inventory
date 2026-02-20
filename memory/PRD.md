# K3 GAS SERVICE - Inventory Dashboard PRD

## Original Problem Statement
Build an Inventory Dashboard for K3 GAS SERVICE business with tagline "Khayal Hamesha". The system manages LPG cylinder inventory across multiple warehouses with comprehensive reporting and discrepancy detection.

## User Personas
1. **Master Admin** - Full system access, manages warehouses, users, settings, views all reports
2. **Warehouse Manager** - Manages daily stock entries for assigned warehouse, views own reports
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

## What's Been Implemented (Jan 2026)

### Backend (FastAPI + MongoDB)
- [x] JWT authentication with role-based access
- [x] User management CRUD operations
- [x] Warehouse management with stock tracking
- [x] Daily reports with discrepancy calculation
- [x] Plant Hollongi special reports (bullet tank, deliveries, receipts)
- [x] Dashboard statistics aggregation
- [x] PDF export using ReportLab
- [x] Excel export using XlsxWriter
- [x] Maintenance mode settings
- [x] Inventory items management

### Frontend (React + Tailwind + Shadcn UI)
- [x] Professional login page with split-screen design
- [x] Master Admin Dashboard with Bento grid layout
- [x] Warehouse Manager Dashboard with quick actions
- [x] Daily Stock Entry Form with discrepancy detection
- [x] Plant Hollongi Entry Form with warehouse selection
- [x] Reports page with filters (period, warehouse, date range)
- [x] Warehouses management page
- [x] Users management page with password change
- [x] Settings page with maintenance mode toggle
- [x] Green theme matching gas/energy industry
- [x] Responsive design with mobile sidebar

### Default Credentials
- Master Admin: admin@k3gas.com / Admin@123
- Jullang: jullang@k3gas.com / Jullang@123
- Naharlagun: naharlagun@k3gas.com / Naharlagun@123
- Doimukh: doimukh@k3gas.com / Doimukh@123
- Plant Hollongi: hollongi@k3gas.com / Hollongi@123

## Prioritized Backlog

### P0 (Critical) - COMPLETED
- [x] Authentication system
- [x] Daily stock entry and reports
- [x] Discrepancy detection
- [x] PDF/Excel exports

### P1 (Important)
- [ ] Email notifications for discrepancies
- [ ] Audit log for stock changes
- [ ] Bulk import/export of data
- [ ] Dashboard charts/graphs using Recharts

### P2 (Nice to Have)
- [ ] Mobile app version
- [ ] SMS alerts for low stock
- [ ] Barcode/QR scanning for cylinders
- [ ] Customer management module
- [ ] Sales order integration

## Next Tasks
1. Add dashboard charts for stock trends visualization
2. Implement email notifications for discrepancies
3. Add audit logging for all stock changes
4. Create print-friendly report layouts
5. Add bulk data import feature

## Technical Stack
- Frontend: React 19, Tailwind CSS, Shadcn UI, Recharts
- Backend: FastAPI, Motor (MongoDB async driver)
- Database: MongoDB
- Authentication: JWT with bcrypt password hashing
- Exports: ReportLab (PDF), XlsxWriter (Excel)
