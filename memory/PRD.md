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


---

## GST BILLING DASHBOARD (Added 2026-02-29)

Module: `/app/backend/routes/gst_billing.py` + `/app/frontend/src/pages/GSTBilling.jsx`
Route: `/gst-billing` (Admin only)

### Features
- [x] Auto-generate GST tax invoice on every NEW LPG sale and accessory sale (sale amount treated as GST-inclusive)
- [x] Manual "Generate from Sale" for legacy/old sales (no auto-backfill)
- [x] Invoice format: `<PREFIX>/<FY>/<SEQ:0001>` e.g. `INV/2026-27/0001` - admin-editable prefix/suffix
- [x] Indian FY sequence (Apr-Mar), auto-reset per FY, atomic via findOneAndUpdate
- [x] Tax modes: Intra-state (CGST+SGST) for Arunachal Pradesh / Inter-state (IGST)
- [x] Item Master with HSN codes (~14 default items: LPG, regulators, cookers, etc.)
- [x] Full CRUD: View, Add, Edit, Cancel (with reason), Delete
- [x] PDF invoice export (embeds company logo, full tax breakdown)
- [x] Excel export with filters
- [x] Search by invoice no/customer/phone, filter by status/bill-type/date range
- [x] Summary dashboard: total invoices, active/cancelled count, total GST collected
- [x] Admin-only access (both backend `require_admin` + frontend `adminOnly` route)

### Business Rules (locked)
- Sale amount is GST-INCLUSIVE: taxable = amount / (1 + gst_rate/100)
- Cancelled invoices cannot be edited
- Cancelled invoices stay in records (not deleted)
- Customer GSTIN is invoice-only (not stored on customer master per user request)
- Default tax mode: intra_state (CGST+SGST) for Arunachal Pradesh

### Tests
- Backend: 19/19 GST + 14/14 Plans + 6/6 Phase A + **38/38 Phase B Reports** = **77/77 pytest cases pass**
- Frontend: All flows verified by testing_agent_v3_fork (iter 43, 44, 45, 47, 48, 49)
- Iteration reports: `/app/test_reports/iteration_43...49.json`

### Phase B: GST Reports Module (Added 2026-03-02)New **Reports tab** in GST Billing dashboard with **10 reports**, each supporting date range filter + Excel export (frozen header, autofilter, autowidth, wrapped text, bold totals, right-aligned amounts, landscape for >6 columns) + PDF export (company header, repeating header, page footer with name/label/page-number, landscape for wide reports).

**Reports:**
1. **Daily Sales** — group by date, totals per day
2. **Monthly Sales** — group by YYYY-MM
3. **GST Report (GSTR-1 style)** — B2B (with customer GSTIN) + B2C breakdown
4. **HSN Summary** — group line items by HSN code + unit + GST rate (consolidated)
5. **Item-wise Sales** — group by item_name + HSN, sorted by total value desc
6. **Customer-wise Sales** — group by customer, sorted by grand_total desc
7. **Warehouse-wise Sales** — group by warehouse (Plant excluded)
8. **Cancelled Invoice Report** — status=cancelled only, with reason/cancelled_by/date
9. **Payment-wise Sales** — group by payment_mode (cash/online/pending/split)
10. **Tax Summary** — group line items by GST rate (5/12/18/28/0)

**Backend module**: `/app/backend/routes/gst_reports.py` (~530 lines). Routes:
- `GET /api/gst/reports/list` — list available reports
- `GET /api/gst/reports/{report_type}` — JSON data for preview
- `GET /api/gst/reports/{report_type}/excel` — Excel download
- `GET /api/gst/reports/{report_type}/pdf` — PDF download

All routes are admin-only (`require_admin`). Invalid `report_type` returns 400 with valid keys.

**Frontend**: New "Reports" TabsTrigger in `GSTBilling.jsx`. Filter row (report type select + start/end dates), action buttons (Refresh, Export Excel, Export PDF), and a live data table with bold blue header + highlighted totals footer. Indian number formatting (`toLocaleString('en-IN')`) on all amount cells. Mobile/tablet/desktop responsive.

---


### Phase A: Print-Preview Dialogs & Spec-Compliant Exports (Added 2026-03-02)
**Dialogs**: All 8 GST Billing dialogs (View/Add/Edit/Cancel/Item/Plan/Settings/Generate) now use `w-[95vw] max-h-[90vh] overflow-y-auto` for full mobile/tablet/desktop responsiveness.

**View Invoice Dialog redesigned as print-preview**: full company header (logo + name + address + GSTIN + state code), TAX INVOICE banner, customer block, items table with CGST+SGST or IGST columns based on tax_mode, totals row, **Amount in Words**, summary box, **Bank Details**, **Terms & Conditions**, **Signatory** cell. Top action bar: Print (window.print + @media print CSS), Download PDF, Edit, Cancel, Close.

**Settings Dialog rebuilt with 4 tabs**: Numbering / Company / Bank / Terms & Signatory. Captures 22 fields: prefix/suffix/tax mode/place + company name/tagline/address/GSTIN/state/state_code/phone/email/logo_url + bank name/holder/A/c/IFSC/branch + T&C/signatory_name/designation.

**Single-invoice PDF** rebuilt as professional Tax Invoice format with logo header, customer block, items table (CGST/SGST split or IGST), totals tile, amount-in-words, bank+T&C+signatory footer (`KeepTogether`), state jurisdiction footer.

**Invoice Register Excel** rewritten as 32-column item-wise report: Sl No · Invoice No · Date · Status · Customer Name/Mobile/GSTIN · Item Name · HSN · Qty · Unit · Rate · Taxable · GST%/CGST%/CGST Amt/SGST%/SGST Amt/IGST%/IGST Amt · Total GST · Discount · Round Off · Grand Total · Payment Mode · Warehouse · Sales Executive · Created By/Date · Cancelled By/Date/Reason. Frozen pane at A6, autofilter on header row, autosize widths, wrapped text, bold highlighted totals row, right-aligned amounts, DD-MM-YYYY date format. Cancelled rows shown with strike-through red.

**Plant Warehouse Exclusion**: Sales entries on Plant Hollongi (or any warehouse with 'plant'/'hollongi' in name) DO NOT auto-generate GST invoices (internal plant operations are not customer invoices).

**Amount in Words**: Backend `amount_in_words_inr` (num2words + 'And'/hyphen normalisation) and frontend `amountInWords` JS helper now produce identical wording (e.g. 1234.56 → "Rupees One Thousand Two Hundred Thirty Four and Fifty Six Paise Only").

---


### Connection Plans (Added 2026-03-01)
Imported from K3 Gas Service Excel "new connection plans with items details":
- **11 default plans seeded**: 4 Domestic (single/double × with/without accessories) + 7 Commercial (1/2/3/4/6/10/15 cylinders)
- Each plan: name, plan_type, connection_type, cylinder_count, has_accessories, items[{item_name, hsn, unit, quantity, gst_rate, unit_price}]
- Admin sets `unit_price` per item via GST Billing → Connection Plans tab
- **Auto-gen with plan**: When a NEW domestic/commercial connection sale is created AND the matching plan has all unit_prices set, the GST invoice is itemized using plan items (per Excel spec). Otherwise falls back to single-line invoice.
- Plan matching: cylinder_count + has_accessories flag (domestic) / closest cylinder_count (commercial)
- `has_accessories` checkbox added to Sales Entry form for new domestic connections — picks the right plan variant
- Refills always single-line (unchanged)
- Manual invoice dialog has "Load from Connection Plan..." dropdown that pre-fills line_items

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
- [x] **Manager Edit/Delete Access** - Warehouse managers can edit/delete customers in their own warehouse
- [x] **Delete Safety Check** - Delete confirmation dialog shows linked orders and sales entries count before deletion
- [x] **Role-Based Actions Column** - Actions column visible for admin and warehouse managers only; sales executives have no edit/delete access
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
- [x] **Multiple Payment Modes** - Split payment support: separate Cash, Online, Credit/Pending amount fields per entry with auto-calculated total. Payment mode auto-detected as 'split' when multiple modes used. Backward compatible with legacy single-mode entries.
- [x] **Summary Cards** - Cash Collection, Online Collection, Pending Collection, Accessory Sales, Grand Total (combined cylinder + accessory)
- [x] **Accessory Sales Integration** - Accessory sales shown in summary card and merged into main sales table with "Accessory" badge
- [x] **Accessory Sales Warehouse Filter** - Accessory sales summary correctly filters by warehouse_id for admin, shows Cash/Online/Pending breakdown
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
- [x] **Split Payment Exports** - PDF/Excel exports include Cash, Online, Credit columns with per-entry and total breakdowns. Summary exports correctly aggregate split amounts.
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

### Sales Cylinder Calculation Logic (March 2026)
- [x] **Clear calculation rules** - New Connection = cylinder sale count (quantity), Refill = cylinder refill count (quantity)
- [x] **4-category breakdown** - Domestic New Conn (6 cyl), Commercial New Conn (10 cyl), Domestic Refills (19 cyl), Commercial Refills (12 cyl)
- [x] **Legacy data handling** - Falls back to `no_of_refills` if `cylinder_nos` is empty for new connections
- [x] **Form labels updated** - "No. of Cylinders" (type=number) for new connections, "No. of Cylinders Refilled" for refills
- [x] **Table columns** - "New Conn Cyl" and "Refill Cyl" with proper display logic
- [x] **Exports** - PDF/Excel include category breakdown row with all 4 categories

### Sales Report Refill & Cylinder Count Fix (March 2026)
- [x] **Backend summary fix** - `no_of_refills` now only summed for refill-type entries, not new connections
- [x] **New cylinder count metric** - Total cylinders calculated from `cylinder_nos` (new connections) + `no_of_refills` (refills)
- [x] **Summary cards updated** - Show "X cyl refilled" per payment mode, Grand Total shows "total cyl / refilled / new conn"
- [x] **Table columns fixed** - Separate "Cyl Nos" (new connections only) and "Refills" (refill entries only) columns
- [x] **Total row fixed** - Shows correct totals for both columns independently

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
- [x] Multiple Payment Modes in Single Sales Entry (March 18, 2026)
- [x] Customer Edit/Delete for Warehouse Managers (March 18, 2026)
- [x] Accessory Sales Warehouse Filter Fix (March 18, 2026)

### P1 (Complete)
- [x] Plant Reports — Dealer-wise Cylinder Issuance Breakdown (March 31, 2026)
- [x] Dealer Reports — Source column showing Hollongi Plant badge (March 31, 2026)
- [x] Connection Type Filter in Sales Dashboard (March 28, 2026)
- [x] Accessory Sales Export Filter (March 28, 2026)
- [x] Sales Search Enhancement — Debounced real-time search (March 28, 2026)
- [x] Sales Data Sorting — Ascending date order (March 28, 2026)

### P2 (Complete)
- [x] Backend Modular Infrastructure — Created database.py, deps.py shared modules (March 31, 2026)
- [x] Route extraction from server.py into 15 APIRouter modules (April 2026) — server.py reduced from 8771 to 149 lines
- [x] Sales Dashboard Date Display Logic Enhancement (April 2026) — Default view shows current month (1st to today), quick filters: This Month, Last Month, Last 7 Days, date range indicator badge, consistent across exports and summary reports
- [x] Fix Current Month View race condition (April 2026) — startDate/endDate now initialized with computed values, added "Reset to Current Month" button, indicator shows "01 [Month] – Today" format
- [x] Fix timezone date bug (April 2026) — replaced toISOString() with local date formatting across all date range functions
- [x] Keyboard Shortcuts System (April 2026) — F1 New, F2 Existing, F10 Export, F11 Summary, Alt+Arrow pagination, Shift+? help modal, floating shortcut bar, role-based access, toast notifications

### P3 (Complete)
- [x] Dashboard Charts — Daily Sales Trend, Payment Pie, Connection Type Bar, Warehouse Bar (March 31, 2026)
- [x] Server-side Pagination — Sales entries with page/limit params (March 31, 2026)
- [x] Audit Logging — Customer edit/delete actions logged to audit_logs collection (March 31, 2026)

### P1 (Important)
- [ ] Complete Dynamic Search Integration - Add SearchBar.jsx to SalesDashboard, Reports, and all remaining data tables
- [ ] Admin UI to add new warehouses with credentials
- [ ] Admin UI to add new inventory stock items
- [ ] Sync warehouse 'refilling at plant' to Plant Hollongi's received empties

### Multi-Dashboard System (April 2026)
- [x] Dashboard Selector page with Inventory & HRMS options
- [x] Login page updated to show both dashboards (Inventory & HRMS cards on right panel)
- [x] Dashboard Selector always shows both options (no auto-redirect), highlights "Last Used"
- [x] HRMS Phase 1: Employee Master, Departments CRUD, Company Settings, HRMS Layout/Sidebar
- [x] HRMS Phase 2: Payroll System (Indian Statutory: PF, ESI, TDS) - April 2026
- [x] HRMS Phase 2: Time & Attendance (Manual entry, leave management) - April 2026
- [x] HRMS Attendance Enhancements: Employee-wise Overview with custom date range, PDF/Excel exports, Biometric API-ready endpoint, Late/OT/Leave tracking - April 2026
- [x] HRMS Phase 2: Performance Management (KPIs, Appraisals) - April 2026
- [x] HRMS Phase 2: Hire Analytics (Recruitment pipeline) - April 2026
- [x] HRMS Reports: A4/Arial PDF/Excel with Company Logo - April 2026
- [x] Salary Certificate & Experience Certificate PDF generation per employee - April 2026
- [x] Seed data populated: 17 employees, 4 departments, attendance/payroll/reviews/hiring data - April 2026
- [x] Employee Bulk Upload (Excel Import): Template download, .xlsx upload, validation (required fields, PAN/Aadhaar/date format, duplicates), preview with error report, skip/overwrite modes, upload logs - April 2026
- [x] Attendance Bulk Upload (Excel Import): Template with employee list, .xlsx upload, validation (employee lookup, date/status/leave-type checks, duplicate detection), preview, skip/overwrite, error report - April 2026
- [x] HRMS Smart Search: Real-time global search across Employees, Departments, Payroll, Hiring, Performance with keyword highlighting, module filters, Ctrl+K shortcut, click-to-navigate - April 2026
- [x] Data Handling Rules: All dates DD-MM-YYYY format (UI, reports, exports), all records sorted ascending date-wise across all HRMS modules - April 2026
- [x] HRMS Access Control System: 3 roles (Super Admin, HR Admin, Employee), auto-redirect to correct dashboard, role-based sidebar, employee self-service (own attendance only), dashboard restriction between Inventory/HRMS - April 2026
- [x] HRMS User Management Panel: Settings tab for HR Admin/Super Admin to create HRMS users (hr_admin/hrms_employee), link to employee records, reset passwords, deactivate users, view credentials - April 2026
- [x] HRMS UI/UX Enhancements - April 2026:
  - Enhanced Dashboard: Skeleton loader, clickable stat cards, Today's Attendance widget (real API data), keyboard shortcuts (Alt+1/2/3)
  - Payroll Pagination: Client-side pagination (10 items/page) with keyboard arrow key navigation
  - Responsive Design: 2-column grid on mobile for stat cards and attendance widget, responsive headers on Attendance/Payroll
  - Export Alignment: Verified PDF/Excel consistency with Arial font and proper column widths
  - New API: GET /api/hrms/attendance/today-stats for dashboard attendance summary
- [x] Post-Payroll Adjustment Module - April 2026:
  - Review & Adjust Payroll stage before finalization
  - Employee-wise adjustments: custom deductions (penalties, advances, recovery) and earnings (bonus, incentives, reimbursements)
  - Mandatory reason/audit trail with user log, timestamps
  - Negative net salary prevention
  - Before vs After salary comparison (4 summary cards)
  - Modified rows highlighted with amber indicator
  - Inline adjustment chips with edit/delete controls
  - Finalization recalculates totals including adjustments, then locks data
  - Adjustments included in payslip PDF breakdown
  - New APIs: GET review, POST/PUT/DELETE adjustments
- [x] Bulk Attendance Update (Multi-Date & Multi-Employee) - April 2026:
  - 4-step wizard: Select Employees -> Select Dates -> Grid Edit -> Review & Submit
  - Excel-like grid with Employee rows x Date columns, per-cell status dropdowns
  - Row quick-apply and Column quick-apply for fast editing
  - Two modes: Same Status for All or Grid Editing
  - 6 status types: Present, Absent, Half Day, Leave, Holiday, Week Off
  - Color-coded cells (green/red/amber/purple/blue/slate)
  - Mandatory reason for audit trail
  - Payroll period lock check (finalized periods skipped)
  - Undo Last Bulk Action before final save
  - Audit logs with old vs new status, timestamps, user info
  - New APIs: preview, apply, undo, logs endpoints

### P2 (Nice to Have)
- [x] Refactor hrms.py into modular routers (April 2026):
  - hrms_settings.py (110 lines) - Company Settings + Departments + Logo
  - hrms_employees.py (752 lines) - Employee CRUD + Bulk Upload + Increment + Photo
  - hrms_dashboard.py (67 lines) - Dashboard Stats + Preference
  - hrms_search.py (109 lines) - Smart Search
  - hrms_users.py (156 lines) - User Management
  - Old monolithic hrms.py (1164 lines) deleted
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
│   ├── server.py              # Slim orchestrator (149 lines) - includes routers
│   ├── models.py              # All Pydantic models (528 lines)
│   ├── helpers.py             # Shared helpers: format_inr, hash_password, log_audit, etc.
│   ├── deps.py                # Auth dependencies: get_current_user, require_admin
│   ├── database.py            # MongoDB connection
│   ├── routes/
│   │   ├── auth.py            # Auth, Settings, User Management
│   │   ├── warehouses.py      # Warehouse + Inventory CRUD
│   │   ├── reports.py         # Daily + Plant Reports
│   │   ├── plant.py           # Plant Cylinder Issuance
│   │   ├── dashboard.py       # Dashboard Charts + Stats
│   │   ├── stock.py           # Admin Stock Updates
│   │   ├── audit.py           # Audit Logs
│   │   ├── exports.py         # Daily Report PDF/Excel Exports
│   │   ├── dealers.py         # Dealer Management + Entries + Exports
│   │   ├── accessories.py     # Accessory Mgmt + Sales + Exports
│   │   ├── customers.py       # Customer Management + Exports
│   │   ├── sales.py           # Sales Dashboard + Summary + Exports
│   │   ├── orders.py          # Order Management + Exports
│   │   ├── analytics.py       # Connection & Refill Analytics + Exports
│   │   └── messaging.py       # Bulk Messaging (Simulated)
│   └── tests/
│       ├── test_refactored_routes.py
│       └── ... (other test files)
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
│       │   ├── SearchBar.jsx
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
│           ├── BulkMessaging.jsx
│           ├── SalesDashboard.jsx
│           ├── AccessorySales.jsx
│           ├── CustomerOrderReport.jsx
│           ├── Warehouses.jsx
│           ├── Users.jsx
│           ├── AuditLogs.jsx
│           ├── Settings.jsx
│           └── Login.jsx
├── memory/
│   └── PRD.md
└── test_reports/
    └── iteration_*.json
```

---

## CHANGELOG (May 2, 2026)

### Department Management + TDS Configuration (Phase A + Merge)
**Backend**:
- `GET /api/hrms/departments?status=all|active|inactive` — annotated with HOD name, active/total employee counts.
- `POST /api/hrms/departments` — creates v1 record + history entry, adds `code` and `hod_employee_id` fields.
- `PUT /api/hrms/departments/{id}` — edits name/code/HOD/description; increments version; uniqueness check; writes old→new snapshot to `hrms_department_versions` + audit log.
- `POST /api/hrms/departments/{id}/toggle-status` — blocks deactivation if active employees still assigned.
- `POST /api/hrms/departments/{id}/merge` — reassigns all employees to target, deactivates source, versions both sides.
- `GET /api/hrms/departments/{id}/history` — per-dept audit trail.
- `GET/PUT /api/hrms/payroll/tds-config` + `GET /api/hrms/payroll/tds-config/history` — versioned TDS config in `hrms_tds_config_versions`:
  - Separate slab arrays for **new** and **old** regimes
  - `default_regime`, `cess_percent`, `surcharge_percent`, `effective_date`, `reason` required on every update
  - Finalized-period lock: rejects `effective_date` that lands before/within a finalized payroll period
- `calc_tds_monthly()` rewritten — regime-aware progressive slab + surcharge + cess
- `run_payroll()` picks TDS version effective on period start and stamps `tds_config_version`, `tds_effective_date`, `default_regime_used` onto the payroll record
- `hrms_employees.update` now accepts `tax_regime` (per-employee override)

**Frontend**:
- `HRMSDepartments.jsx` — rewritten with Edit / Deactivate / Merge / History dialogs; HOD employee picker; code field; status badge; action toolbar
- `PayrollManagement.jsx` — Statutory Config dialog now has a **TDS Configuration** section with tabbed editable slab tables (New/Old regime), default-regime selector, cess/surcharge inputs, effective-date picker, mandatory reason, and a **TDS History** dialog
- All changes version-stamped; no retroactive impact on already-finalized payroll runs (TDS config snapshot stays with the run)

**Verified via screenshots + curl**:
- Dept edit persists v2 change with before/after diff in history modal
- TDS v2 saved with `effective_date=2026-08-01, reason="Revised slabs Aug 2026"`
- Payroll for Aug 2026 → `tds_config_version=2` · May 2026 → `tds_config_version=1` (regime picks correct version dynamically)

### Prior fixes in this session
- Fixed Bulk Attendance Update dual-toast bug (undefined fetchAttendance/fetchSummary)
- Added Audit Log Viewer UI at `/audit-logs`
- Dealer Integration in Plant Daily Entry with auto-sync to `dealer_entries`
- "Delivered Today" strip on Plant Hollongi dashboard (also fixed latent getDateRange key mismatch)
- Customer dashboard FY2024-25 sync-from-sales endpoint + robust bulk-upload date parser
- Removed 25 unused AI/cloud packages from requirements.txt (128 → 104 lines)
- OrderManagement: server-side customer search across full DB

### TDS is opt-in per employee (May 2, 2026 — follow-up)
Per user instruction, TDS is **never calculated by default**. Each employee's payroll record now respects a `tds_applicable` boolean flag:

*Last Updated: May 2, 2026 — TDS opt-in per employee*

- **Backend**: `compute_employee_payroll()` returns `tds=0` unless `emp.tds_applicable == True`; `hrms_employees.update` accepts `tds_applicable` + `tax_regime`; the payslip stamp still includes `tds_config_version` so audit stays intact.
- **Frontend**: added a "Deduct TDS for this employee" checkbox in the Employee edit dialog (Salary section). Toggling it reveals a small Regime (New/Old) selector. Visibly off by default — HR has to explicitly turn it on per employee.
- **Verified (curl)**: on 17-employee Aug 2026 payroll run with zero flags, every employee showed `tds=0`. Flagging a single employee resulted in exactly one `tds_applicable=true` record (math confirmed against v2 slabs).

---

## Session — June 30, 2026 — GST Item Master Bulk Update + Rate History (P0 COMPLETE)

**Feature**: Admin can now manage GST Item Master in bulk and audit historical rate changes.

**Frontend** (`/app/frontend/src/pages/GSTBilling.jsx`):
- Three new buttons on **Item Master** tab header: **Download Template**, **Bulk Upload**, **Rate History** (+ existing Add Item).
- Bulk Upload dialog: file picker (.xlsx / .xls / .csv) + `effective_from` default-date input + result panel showing Created / Updated / Rate-changes / Skipped + per-row error list.
- Rate History dialog: filters by Item / From / To dates with Excel download. Read-only table shows Item, HSN, Prev Rate, New Rate, GST %, Status, Effective From, Updated By, Reason, Updated At.
- Wired through existing `api.js` helpers: `downloadGstItemTemplate`, `bulkUploadGstItems`, `getGstItemHistory`, `downloadGstItemHistoryExcel`.

**Backend** (no changes this iteration — already complete from previous fork):
- `GET /api/gst/items/template/excel` — pre-filled Excel template of all items.
- `POST /api/gst/items/bulk-upload` (multipart) and `/bulk-update` (JSON) — create/update items, write `gst_item_history` rows, and cascade name/hsn/unit/gst_rate changes to `gst_plans.items` (rate snapshots in plans/invoices untouched).
- `GET /api/gst/items/history` + `/history/excel` — filterable history.
- All five endpoints admin-only (`require_admin`).

**Historical invariant**: Bulk rate updates only mutate `gst_items` + attribute fields on `gst_plans.items`. `gst_invoices.line_items` and `gst_plans.items.unit_price` remain pure snapshots — historical invoices/plans never recalculate.

**Testing** (`/app/test_reports/iteration_53.json`):
- Backend pytest: **15/15 pass** (`/app/backend/tests/test_gst_item_bulk_history.py`, ~3s).
- Frontend Playwright: all 3 buttons, dialogs, file upload, history filter+excel verified end-to-end. Regression on Invoices / Reports / Plans / Item Master tabs intact.

*Last Updated: June 30, 2026 — Item Master Bulk Update + Rate History*



---

## Session — June 30, 2026 — Polish Triple Pack ✅

### 1. Hydration Warning (P3, GSTBilling.jsx)
- Investigated React `<tr> cannot be a child of <span>` warning.
- **Root cause confirmed via support_agent**: platform dev-overlay script `https://assets.emergent.sh/scripts/emergent-main.js` injects a `<span data-ve-dynamic="true" style="display:contents">` around dynamic `.map()` output for inspection. Runtime span violates DOM nesting rules even though invisible at CSS level.
- **No app-side fix is possible**; production builds do not include the overlay → no warning in production.
- Still cleaned up the JSX to keep `.map()` direct children of `<tbody>` and moved loading/empty states outside the table — better readability and accessibility.

### 2. Branded Excel Header (P2, Customer / Sales / Plant exports)
- New module `/app/backend/export_helpers.py` with `embed_logo_openpyxl`, `embed_logo_xlsxwriter`, `get_company_info_for_export`, `cleanup_logo_tempfile`. Handles both openpyxl & xlsxwriter, gracefully skips when no logo is set, cleans up temp files safely.
- Added branded header (rows 1-3: logo + company name + tagline/address/helpline + title/period/timestamp, row 4 spacer, row 5 headers) to **6 endpoints**:
  - `/api/export/sales-excel`
  - `/api/export/sales-summary-excel`
  - `/api/export/customer-refill-excel`
  - `/api/export/customers-excel` (xlsxwriter)
  - `/api/export/excel?report_type=daily` (xlsxwriter)
  - `/api/export/excel?report_type=plant` (xlsxwriter — main + Warehouse Breakdown sheets)
- Also retro-fitted `/api/gst/items/history/excel` to use the shared helper for full consistency.

### 3. Refactor (P3, gst_billing.py)
- Extracted Item Master CRUD + Rate History + Bulk Update endpoints (424 lines) from `gst_billing.py` into a new `/app/backend/routes/gst_items.py` module with its own `APIRouter`, registered in `server.py` (`gst_items_router` at `/api`).
- `gst_billing.py`: **1810 → 1386 lines** (-23%). Now focuses on config / connection plans / invoices only.
- `_record_rate_history`, `_parse_bool`, `_apply_bulk_rows` helpers also moved.
- `ensure_seed` imported lazily inside `list_items()` to avoid circular import. Backend cold-starts cleanly. **Same URLs preserved** — no client-side changes.

### Testing — `/app/test_reports/iteration_54.json`
- Backend pytest: **41/41 pass** across 3 files (`test_excel_branded_exports.py` (NEW), `test_gst_item_bulk_history.py`, `test_gst_item_master_sync.py`).
- Frontend Playwright: 100% on all flows tested (login → GST Billing → Item Master / Plans / Invoices / Reports tabs all working; Rate History dialog with 13 rows rendered).
- No regressions found.

*Last Updated: June 30, 2026 — Hydration / Branded Exports / Refactor*

---

## Session — June 30, 2026 — Amount Mismatch & Discrepancy Invoice Detection ✅

**Feature**: System now auto-validates entered sales amounts against the configured rate (Connection Plan → Item Master fallback). Mismatch >₹1 is HARD BLOCKED until the user provides a justification. The invoice is then saved as a "Discrepancy Invoice" pending admin review.

### Backend
- `/app/backend/routes/gst_billing.py`:
  - `DISCREPANCY_TOLERANCE = 1.0`, `compute_expected_amount(payload)`, `discrepancy_payload(expected, actual)`, `validate_sale_discrepancy(sale, sale_type)`.
  - `POST /api/gst/invoices` and `PUT /api/gst/invoices/{id}` now raise HTTP 400 `{code: 'discrepancy_requires_reason', expected_amount, actual_amount, discrepancy_amount}` when amount mismatches and no `discrepancy_reason` is supplied.
  - `GET  /api/gst/discrepancies` (filter `?status=pending|approved|rejected|corrected|all`) — returns `{rows, summary}` with counts + total net difference.
  - `POST /api/gst/discrepancies/{id}/review` (action: approve/reject + note) — full audit log.
  - `POST /api/gst/discrepancies/{id}/correct` — admin edits line_items; status flips to `corrected` if mismatch resolved.
  - `auto_generate_invoice_from_sale` propagates `sale.discrepancy_reason` to the auto-created invoice.
- `/app/backend/routes/gst_reports.py`: new `discrepancy_invoices` report type with 11 columns (Invoice #, Date, Customer, Type, Expected, Actual, Difference, Reason, Status, Reviewed By, Review Note) + summary tiles.
- `/app/backend/routes/sales.py` (both endpoints) + `/app/backend/routes/accessories.py`: call `validate_sale_discrepancy` before insert; same hard-block rule applies; `discrepancy_reason` field added to `SalesEntryCreate` + `AccessorySaleCreate`.

### Frontend
- `/app/frontend/src/pages/GSTBilling.jsx`:
  - **New "Discrepancies" tab** (data-testid `tab-discrepancies`) between Invoices and Reports — 5 summary tiles, status filter, refresh, table with Approve/Reject/Correct actions per row.
  - **Discrepancy-reason dialog** (data-testid `discrepancy-reason-dialog`) auto-opens when invoice save returns the 400. Shows Expected/Entered/Difference + reason textarea; save disabled until reason provided.
  - **Discrepancy-review dialog** (data-testid `discrepancy-review-dialog`) for approve/reject with optional / required note respectively.
  - **Discrepancy badge** appears on invoice rows in the Invoices tab.
- `/app/frontend/src/pages/SalesDashboard.jsx`: mirror dialog (data-testid `sales-discrepancy-dialog`) triggered when add-sale returns the 400.
- `/app/frontend/src/lib/api.js`: `listGstDiscrepancies`, `reviewGstDiscrepancy`, `correctGstDiscrepancy`.

### Testing — `/app/test_reports/iteration_55.json`
- Backend pytest: **71/71 GST tests pass** (8 new in `test_discrepancy_invoices.py` + 4 in `test_discrepancy_extras.py` + 59 pre-existing regression).
- Frontend Playwright: end-to-end discrepancy create → list → approve flow verified; all testids resolved.
- **No regressions.**

### Pre-Deployment Cleanup (post-test)
- Hard-deleted 46 test invoices, 16 test sales entries, 73 test items + history. 15 production items + 11 plans remain.

*Last Updated: June 30, 2026 — Discrepancy Detection*

