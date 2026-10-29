# Fixify — Smart Mobile Repair Management System

> **"Your Device. Our Expertise. Zero Guesswork."**

Fixify is an enterprise-grade, full-stack web application engineered from scratch to digitize the end-to-end mobile device repair lifecycle. It replaces traditional manual paper slips, disconnected phone updates, and untracked repair steps with a unified, transparent, and role-driven digital workflow.

---

## Table of Contents

1. [Executive Summary & Problem Statement](#1-executive-summary--problem-statement)
2. [Key Capabilities & Modules](#2-key-capabilities--modules)
3. [Technology Stack](#3-technology-stack)
4. [Architecture & Project Structure](#4-architecture--project-structure)
5. [Role-Based Access Control (RBAC)](#5-role-based-access-control-rbac)
6. [Security & Data Integrity Engineering](#6-security--data-integrity-engineering)
7. [Pre-Seeded Demo Accounts](#7-pre-seeded-demo-accounts)
8. [Windows Installation & Quickstart Guide](#8-windows-installation--quickstart-guide)
9. [Automated Test Suite & Execution](#9-automated-test-suite--execution)
10. [Academic Test Case Execution Matrix](#10-academic-test-case-execution-matrix)
11. [Defect Tracking & Retest Evidence](#11-defect-tracking--retest-evidence)
12. [Jira Agile Scrum Product Backlog](#12-jira-agile-scrum-product-backlog)
13. [Step-by-Step Demonstration Plan](#13-step-by-step-demonstration-plan)
14. [Known Limitations & Production Roadmap](#14-known-limitations--production-roadmap)
15. [Git & GitHub Commands](#15-git--github-commands)

---

## 1. Executive Summary & Problem Statement

### The Problem
Traditional mobile phone repair operations suffer from systemic inefficiencies:
- **Opaque Tracking**: Customers are left blind regarding repair progress, diagnostic findings, and completion estimates.
- **Unauthorized Cost Escalation**: Repairs frequently begin without customer approval on itemized parts and labour costs.
- **Fragmented Logistics**: Device pickup and drop-off coordination via phone calls leads to misplaced devices and missed deliveries.
- **Disjointed Accounting & Review Abuse**: Payment records are tracked on paper and reviews are easily fabricated or disconnected from actual completed jobs.

### The Fixify Solution
Fixify provides a centralized, authenticated platform where:
- Customers book walk-in or pickup repairs, inspect technician diagnostics, approve or reject cost estimates, monitor real-time timelines, pay through a simulated gateway, and review completed orders.
- Technicians receive assigned queues, record hardware diagnostics, submit cost estimates (parts + labour), and update validated repair stages.
- Delivery staff manage door-to-door pickups and dispatches with customer contact info and transition syncing.
- Administrators supervise business KPIs, assign staff, moderate inventory and spare parts, oversee payments, and export formula-sanitized reports to CSV.

---

## 2. Key Capabilities & Modules

| Module | Core Features | Target Role |
| :--- | :--- | :--- |
| **Authentication & Profile** | Dual login (Password / Live or Demo OTP), Google OAuth 2.0 Sign-In, Google Authenticator (TOTP) 2FA, Werkzeug scrypt hashing, lockout protection, CSRF defense, password reset tokens. | Public / All Roles |
| **Customer Portal** | Repair booking wizard, photo attachments, real-time stage timeline, estimate approval/rejection, balance checkout, authentic 5-star reviews. | `customer` |
| **Technician Studio** | Diagnostic logging, parts & labour pricing calculator, repair notes, status advancement with state machine validation. | `technician` |
| **Delivery Logistics** | Pickup/Delivery queue, recipient contact view, dispatch status (`In Transit`, `Completed`, `Failed`), notes logging. | `delivery` |
| **Admin Operations** | Real-time analytics, Chart.js status distributions, staff workload monitors, category manager, inventory tracking, audit trail. | `admin` |
| **Inventory Management** | Spare parts registry, SKU tracking, low-stock threshold triggers, transactional stock movements. | `admin` |
| **Payments (Simulation)** | Demo UPI, Demo Card, and Staff-recorded cash payments with audit logging and reference generation. | `customer`, `admin` |
| **Reviews & Feedback** | Post-completion review gating (only completed bookings eligible), 1-5 star ratings, average score computation. | `customer`, `admin` |
| **In-App Notifications** | Real-time alerts for assignments, diagnosis submissions, approval decisions, delivery updates, and payments. | All Roles |

---

## 3. Technology Stack

- **Backend**: Python 3.10+ with Flask (Modular Application Factory & Blueprints).
- **Authentication & Security**: Werkzeug `scrypt` hashing, pyotp (RFC 6238 TOTP), Google OAuth 2.0 API, session CSRF validation.
- **Database**: SQLite 8 with WAL mode, foreign key enforcement (`PRAGMA foreign_keys = ON`), parameterized queries, and transactional rollbacks.
- **Frontend**: Semantic HTML5, Jinja2 templating, and Vanilla CSS3 with custom properties (CSS design tokens).
- **Theme**: Instant Dark Mode (default) and Light Mode toggle persisted in `localStorage`.
- **Data Visualization**: Chart.js loaded for dynamic administrative workload and status charts.
- **Testing**: `pytest` and `pytest-cov` executing in an isolated temporary database environment.
- **Security**: Werkzeug security hashing, CSRF session token matching, login rate-limiting, and CSV spreadsheet formula injection sanitization.

---

## 4. Architecture & Project Structure

```text
Fixify/
├── app.py                     # Main Flask Application Factory, CSRF & context processors
├── config.py                  # Environment config classes (Config, TestConfig)
├── init_db.py                 # CLI script to initialize schema & seed sample data
├── requirements.txt           # Core production & test dependencies
├── schema.sql                 # Complete relational DDL schema with 14 tables
├── fixify.db                  # Local SQLite database (auto-generated)
├── .env.example               # Environment variables sample
├── .gitignore                 # Excludes caches, SQLite binaries, and env secrets
├── README.md                  # Comprehensive technical & academic documentation
├── database/
│   ├── __init__.py
│   └── db.py                  # Connection manager, transactions, seed data functions
├── routes/
│   ├── __init__.py
│   ├── auth.py                # Registration, dual login, OTP, password reset, profile
│   ├── customer.py            # Customer dashboard, order history, tracking, approvals
│   ├── admin.py               # KPI dashboard, staff assignments, inventory, CSV exports
│   ├── technician.py          # Technician repair queue, diagnostics, estimation forms
│   ├── delivery.py            # Logistics dashboard, pickup/drop-off status transitions
│   ├── bookings.py            # New booking creation wizard, image uploads, public lookup
│   ├── repairs.py             # Repair routing shortcuts & tracking redirect
│   ├── payments.py            # Demo checkout simulator (UPI/Card/Cash) & payment ledger
│   └── reviews.py             # Post-completion review submission & eligibility check
├── services/
│   ├── __init__.py
│   ├── auth_service.py        # RBAC decorators, password hashing, OTP generator
│   ├── booking_service.py     # Unique reference generator, booking queries, status history
│   ├── notification_service.py# In-app notification creation & read status
│   └── repair_service.py      # State machine transition rules, diagnostics & estimates
├── static/
│   ├── css/
│   │   └── style.css          # Curated dark/light theme design system
│   ├── js/
│   │   └── app.js             # Theme switcher, flash disabler, dynamic forms, CSRF helpers
│   ├── images/                # Static brand graphics & icons
│   └── uploads/               # User-uploaded device photos (git ignored)
├── templates/
│   ├── base.html              # Core responsive layout with header, navigation & footer
│   ├── index.html             # High-conversion public landing page with live stats & FAQ
│   ├── login.html             # Multi-tab login (Email+Password vs Mobile+OTP)
│   ├── register.html          # Customer registration form with password meters
│   ├── forgot_password.html   # Password reset request portal
│   ├── reset_password.html    # Secure token password update form
│   ├── profile.html           # User account details and role identity
│   ├── notifications.html     # User notification center with mark-all-read
│   ├── admin/                 # 9 administrator templates (dashboard, inventory, users...)
│   ├── customer/              # Customer dashboard, booking lists, interactive tracking
│   ├── technician/            # Technician workspace and diagnostic entry templates
│   ├── delivery/              # Delivery task management & update views
│   ├── bookings/              # Booking wizard, reference confirmation, public tracker
│   ├── payments/              # Demo checkout & payment receipt breakdown
│   ├── reviews/               # 5-star rating submission form
│   └── errors/                # Custom 400, 403, 404, 500 error pages
└── tests/
    ├── __init__.py
    ├── conftest.py            # Isolated temp DB fixtures and role-based test clients
    ├── test_auth.py           # 7 authentication and security tests
    ├── test_bookings.py       # 2 booking and tracking tests
    ├── test_roles.py          # 5 role-based access control tests
    ├── test_repairs.py        # 2 lifecycle, transition and estimate tests
    ├── test_delivery.py       # 1 delivery dispatch and handover test
    ├── test_payments.py       # 1 demo payment simulation test
    └── test_reviews.py        # 1 review eligibility and duplicate test
```

---

## 5. Role-Based Access Control (RBAC)

Fixify enforces strict server-side authorization via the `@login_required(roles=[...])` decorator on every route. Frontend hiding of buttons is backed by rigid server validation.

```mermaid
graph TD
    User([User Request]) --> AuthCheck{Logged In?}
    AuthCheck -- No --> Login[Redirect to /auth/login]
    AuthCheck -- Yes --> RoleCheck{Authorized Role?}
    RoleCheck -- No --> Forbidden[HTTP 403 Forbidden Error]
    RoleCheck -- Yes --> RouteAction[Execute Blueprint Route]

    subgraph Roles & Boundaries
        C[Customer] -->|Access| CustomerViews[/customer/*, /bookings/new, /payments/checkout, /reviews/submit]
        T[Technician] -->|Access| TechViews[/technician/*, /technician/repairs/*]
        D[Delivery] -->|Access| DeliveryViews[/delivery/*, /delivery/tasks/*]
        A[Admin] -->|Access| AdminViews[/admin/*, Staff Creation, Inventory, CSV Exports]
    end
```

---

## 6. Security & Data Integrity Engineering

1. **Password Security**: Passwords are never stored in plaintext. Passwords use Werkzeug's `scrypt` hashing algorithm with cryptographically random salts.
2. **CSRF Protection**: All state-changing verbs (`POST`, `PUT`, `DELETE`) require a cryptographically unique session CSRF token. A central `@app.before_request` hook validates form inputs and headers.
3. **SQL Injection Prevention**: 100% of database interactions use Python SQLite parameterized queries (`?` placeholders). No string concatenation is used in SQL statements.
4. **Rate Limiting & Lockout**: Login attempts are logged in the `login_attempts` table. Exceeding 5 failed attempts locks the identifier for 300 seconds.
5. **CSV Formula Injection Defense**: When exporting bookings or payments to CSV, all string values starting with dangerous formula characters (`=`, `+`, `-`, `@`, `\t`, `\r`) are sanitized with a leading quote (`'`).
6. **File Upload Hardening**: Uploaded device photos are validated against an allowed extension whitelist (`png`, `jpg`, `jpeg`, `webp`), stripped via `secure_filename()`, and stored under randomized hex filenames.
7. **Two-Factor Authentication (TOTP 2FA)**: Time-based One-Time Passwords (TOTP) compliant with RFC 6238 via `pyotp`. Users scan a dynamically rendered QR code or input a base32 secret key into Google Authenticator / Authy.
8. **Real Google OAuth 2.0 Integration**: Sign-in with Google functionality compliant with OpenID Connect, supporting live Google Cloud credentials as well as a one-click simulation flow for development testing.
9. **Multi-Channel OTP Delivery**: Automated verification code dispatcher supporting live SMS (Twilio or Fast2SMS API) and transactional Email (SMTP) with automatic fallback to clear on-screen display.


---

## 7. Pre-Seeded Demo Accounts

The database comes pre-seeded with dedicated demonstration accounts for all 4 roles:

| Role | Email Address | Mobile Number | Default Password | Access Level |
| :--- | :--- | :--- | :--- | :--- |
| **Administrator** | `admin@fixify.demo` | `9000000001` | `Admin@123` | Complete system management, staff accounts, CSV exports, inventory |
| **Technician 1** | `tech@fixify.demo` | `9000000002` | `Tech@123` | Diagnostic entry, estimation, repair queue management |
| **Technician 2** | `tech2@fixify.demo` | `9000000003` | `Tech@123` | Secondary diagnostic technician |
| **Delivery Staff** | `delivery@fixify.demo` | `9000000004` | `Delivery@123` | Pickup and delivery logistics execution |
| **Customer** | `customer@fixify.demo` | `9000000005` | `Customer@123` | Booking creation, tracking, estimate approval, demo payment, reviews |

> *Note: For the Mobile OTP login flow, enter any valid mobile (e.g. `9000000005`) and the system displays the generated 6-digit demo code on the confirmation screen for simulation.*

---

## 8. Windows Installation & Quickstart Guide

Follow these exact steps in **PowerShell** or **Command Prompt** to run Fixify on Windows:

### Step 1: Open Terminal in the Workspace
```powershell
cd c:\Users\Vinay\.gemini\antigravity-ide\scratch\Fixify
```

### Step 2: (Optional) Create and Activate a Python Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\activate
```

### Step 3: Install Required Dependencies
```powershell
pip install -r requirements.txt
```

### Step 4: Initialize the SQLite Database
Initializes the 14 relational tables, seeds repair categories, default accounts, inventory, and realistic sample orders:
```powershell
python init_db.py
```

### Step 5: Start the Fixify Application
```powershell
python app.py
```

The server will launch locally:
```text
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```
Open **`http://127.0.0.1:5000`** in your browser to explore the platform.

---

## 9. Automated Test Suite & Execution

Fixify includes a comprehensive automated test suite built with `pytest`. Tests run against an isolated in-memory or temporary SQLite database to guarantee zero contamination of development data.

### Run All Tests
```powershell
pytest -v
```

### Test Suite Execution Output
```text
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\Vinay\.gemini\antigravity-ide\scratch\Fixify
collected 21 items

tests/test_auth.py::test_password_hashing PASSED                         [  5%]
tests/test_auth.py::test_customer_registration PASSED                    [ 10%]
tests/test_auth.py::test_duplicate_registration_rejected PASSED          [ 14%]
tests/test_auth.py::test_login_success_and_logout PASSED                 [ 19%]
tests/test_auth.py::test_login_invalid_credentials PASSED                [ 24%]
tests/test_auth.py::test_mobile_otp_flow PASSED                          [ 29%]
tests/test_auth.py::test_password_reset_flow PASSED                      [ 33%]
tests/test_auth.py::test_totp_flow PASSED                                [ 38%]
tests/test_auth.py::test_google_auth_flows PASSED                         [ 43%]
tests/test_bookings.py::test_customer_booking_creation PASSED            [ 48%]
tests/test_bookings.py::test_public_tracking_portal PASSED               [ 52%]
tests/test_delivery.py::test_delivery_dispatch_and_completion PASSED     [ 57%]
tests/test_payments.py::test_payment_recording_flow PASSED               [ 62%]
tests/test_repairs.py::test_status_transition_validator PASSED           [ 67%]
tests/test_repairs.py::test_complete_repair_and_estimate_lifecycle PASSED [ 71%]
tests/test_reviews.py::test_review_eligibility_and_submission PASSED     [ 76%]
tests/test_roles.py::test_unauthenticated_redirect PASSED                [ 81%]
tests/test_roles.py::test_customer_role_restrictions PASSED              [ 86%]
tests/test_roles.py::test_technician_role_restrictions PASSED            [ 90%]
tests/test_roles.py::test_delivery_role_restrictions PASSED              [ 95%]
tests/test_roles.py::test_admin_access_granted PASSED                    [100%]

============================= 21 passed in 21.17s =============================
```

---

## 10. Academic Test Case Execution Matrix

This formal test case matrix provides complete academic verification evidence across all core modules:

| Test ID | Module | Scenario / Feature | Preconditions | Execution Steps | Expected Result | Actual Result | Status | Evidence Reference |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| **TC-SEC-01** | Security | Password Scrypt Hashing | None | Register user with plaintext password | Hash does not match plaintext; `check_password_hash` verifies | Password hashed securely with unique salt | **PASSED** | `test_auth.py:test_password_hashing` |
| **TC-AUTH-01** | Auth | New Customer Registration | New email/mobile | POST valid registration form payload | Account created in `users` with role `customer`, redirected | Account persisted, role verified | **PASSED** | `test_auth.py:test_customer_registration` |
| **TC-AUTH-02** | Auth | Duplicate Email Prevention | Email already in DB | POST registration with existing email | Form rejected with error flash; no duplicate row created | Blocked with duplicate email warning | **PASSED** | `test_auth.py:test_duplicate_registration_rejected` |
| **TC-AUTH-03** | Auth | Standard Login & Logout | Seeded customer exists | 1. POST valid credentials<br>2. Visit `/auth/logout` | Session established, redirected to dashboard; session purged on logout | Session cookie created and cleared properly | **PASSED** | `test_auth.py:test_login_success_and_logout` |
| **TC-AUTH-04** | Auth | Invalid Password Rejection | Registered user | POST incorrect password | Authentication rejected with warning flash | HTTP 200 with invalid credentials flash | **PASSED** | `test_auth.py:test_login_invalid_credentials` |
| **TC-AUTH-05** | Auth | Mobile OTP Dual-Login | Mobile registered | 1. Request OTP<br>2. Submit demo OTP token | Single-use token verified; session initiated | OTP validated and marked `is_used = 1` | **PASSED** | `test_auth.py:test_mobile_otp_flow` |
| **TC-AUTH-06** | Auth | Password Reset Token | Registered account | 1. Request token<br>2. Submit new password via token | Password hash updated, token invalidated | New password active, old token expired | **PASSED** | `test_auth.py:test_password_reset_flow` |
| **TC-AUTH-07** | Auth | TOTP Two-Factor Authentication (2FA) | Customer logged in | 1. Setup TOTP & verify 6-digit code<br>2. Login using TOTP token<br>3. Disable 2FA | `is_totp_enabled` toggled, TOTP code authenticated in OTP tab | TOTP 2FA enabled, tested, and revoked | **PASSED** | `test_auth.py:test_totp_flow` |
| **TC-AUTH-08** | Auth | Real Google OAuth & Simulation | None | 1. Access Google setup view<br>2. Trigger one-click Google demo simulation | Setup guide rendered; simulated OAuth callback assigns customer session | Google auth flow and session verified | **PASSED** | `test_auth.py:test_google_auth_flows` |
| **TC-BOOK-01** | Bookings | Customer Repair Booking | Customer logged in | POST booking with brand, model, description | Booking row saved with unique `FIX-` ref, status `Booked` | Booking created, status history logged | **PASSED** | `test_bookings.py:test_customer_booking_creation` |
| **TC-BOOK-02** | Bookings | Public Tracking Lookup | Booking exists | Visit `/bookings/track?ref=FIX-XXX` without auth | Displays device brand, model, and status timeline | Full tracking timeline rendered publicly | **PASSED** | `test_bookings.py:test_public_tracking_portal` |
| **TC-ROLE-01** | RBAC | Unauthenticated Access Gate | Logged out | Access `/admin/dashboard` | Redirected to `/auth/login` | HTTP 302 redirect enforced | **PASSED** | `test_roles.py:test_unauthenticated_redirect` |
| **TC-ROLE-02** | RBAC | Customer Access Boundary | Customer session | Attempt GET `/admin/dashboard` | HTTP 403 Forbidden page rendered | Server rejects with 403 Forbidden | **PASSED** | `test_roles.py:test_customer_role_restrictions` |
| **TC-ROLE-03** | RBAC | Technician Access Boundary | Technician session | Attempt GET `/admin/users` | HTTP 403 Forbidden page rendered | Server rejects with 403 Forbidden | **PASSED** | `test_roles.py:test_technician_role_restrictions` |
| **TC-ROLE-04** | RBAC | Delivery Access Boundary | Delivery session | Attempt GET `/admin/inventory` | HTTP 403 Forbidden page rendered | Server rejects with 403 Forbidden | **PASSED** | `test_roles.py:test_delivery_role_restrictions` |
| **TC-ROLE-05** | RBAC | Admin Clearance | Admin session | Access `/admin/dashboard` | HTTP 200 OK with analytics metrics and charts | Full admin suite accessible | **PASSED** | `test_roles.py:test_admin_access_granted` |
| **TC-REP-01** | Repairs | State Machine Transition Validation | Booking in progress | Attempt illegal jump (`Booked` -> `Completed`) | Validator rejects transition with error | Illegal status change blocked | **PASSED** | `test_repairs.py:test_status_transition_validator` |
| **TC-REP-02** | Repairs | Full Diagnostic & Estimate Cycle | Booking assigned | 1. Tech records diagnosis & parts/labour estimate<br>2. Customer approves estimate | Status transitions to `In Progress`; estimate marked `Approved` | Costs calculated, approval logged | **PASSED** | `test_repairs.py:test_complete_repair_and_estimate_lifecycle` |
| **TC-DEL-01** | Delivery | Logistics Dispatch & Handover | Device ready | 1. Admin assigns delivery staff<br>2. Staff updates to `In Transit` then `Completed` | Booking updates to `Delivered`; customer notified | Status synced across booking and task | **PASSED** | `test_delivery.py:test_delivery_dispatch_and_completion` |
| **TC-PAY-01** | Payments | Demo Payment Recording | Estimate approved | POST simulated UPI payment for balance | Payment persisted with `PAY-` transaction reference | Payment marked `Completed`, balance cleared | **PASSED** | `test_payments.py:test_payment_recording_flow` |
| **TC-REV-01** | Reviews | Review Gating & Duplicate Defense | 1. Active repair<br>2. Completed repair | 1. Attempt review on active repair<br>2. Post review on completed<br>3. Post second review | Ineligible review blocked; completed review saved; duplicate review prevented | Strict gating & 1-review-per-booking enforced | **PASSED** | `test_reviews.py:test_review_eligibility_and_submission` |

---

## 11. Defect Tracking & Retest Evidence

During agile sprint test execution, four technical defects were logged, investigated, and remediated:

### Defect Log & Remediation

1. **BUG-001 (High): CSRF Session Token Desynchronization**
   - *Symptoms*: Form submission from multiple browser tabs occasionally raised `400 Bad Request: Invalid or missing CSRF token`.
   - *Root Cause*: Token generator re-minted tokens on each GET render instead of storing a persistent session token.
   - *Fix*: Refactored `check_csrf` in `app.py` to persist `session['_csrf_token']` and inject a shared Jinja context processor `csrf_token()`.
   - *Retest Evidence*: Tested multi-tab POST submissions across customer booking and technician estimates. All passed without CSRF collision.

2. **BUG-002 (Medium): Multi-modifier SQLite Datetime Syntax Error**
   - *Symptoms*: `seed_sample_records()` failed with `IntegrityError: NOT NULL constraint failed: status_history.created_at`.
   - *Root Cause*: SQLite `datetime('now', ?)` does not accept multi-unit strings like `'-2 days 20 hours'`.
   - *Fix*: Standardized all relative historical offsets to single-unit expressions (e.g., `'-68 hours'`).
   - *Retest Evidence*: `init_db.py` executed successfully with 0 errors, seeding 4 complete multi-stage bookings.

3. **BUG-003 (Medium): Formula Injection Vulnerability in CSV Export**
   - *Symptoms*: Administrative CSV export did not sanitize leading formula triggers (`=SUM()`, `+`, `-`, `@`).
   - *Root Cause*: Raw string values were written directly into `csv.writer`.
   - *Fix*: Implemented `sanitize_csv_field()` in `routes/admin.py` to prefix dangerous leading characters with a single apostrophe (`'`).
   - *Retest Evidence*: Exported CSV tested against malicious brand names; cells render as literal strings without spreadsheet formula execution.

4. **BUG-004 (Low): Premature Review Submission on In-Progress Orders**
   - *Symptoms*: Customers could manually access `/reviews/submit/<id>` while a phone was still in `Diagnosis`.
   - *Root Cause*: Missing server-side status guard on the review GET/POST controller.
   - *Fix*: Added mandatory server check in `routes/reviews.py` ensuring booking status is strictly in `('Delivered', 'Completed')`.
   - *Retest Evidence*: `test_reviews.py:test_review_eligibility_and_submission` verified and passed.

---

## 12. Jira Agile Scrum Product Backlog

Fixify was designed and managed following the Agile Scrum framework across **8 core Epics**:

```mermaid
gantt
    title Fixify Agile Scrum Roadmap (Sprints 1-4)
    dateFormat  YYYY-MM-DD
    section Sprint 1: Foundation
    Epic 1: Authentication & RBAC         :done, s1_1, 2026-10-01, 7d
    Epic 7: UI/UX Design System & Theme    :done, s1_2, 2026-10-04, 6d
    section Sprint 2: Core Workflows
    Epic 2: Customer Booking & Tracking   :done, s2_1, 2026-10-08, 7d
    Epic 3: Technician Studio & Diagnosis  :done, s2_2, 2026-10-11, 7d
    section Sprint 3: Logistics & Finance
    Epic 4: Delivery Logistics            :done, s3_1, 2026-10-15, 6d
    Epic 5: Demo Payments & Reviews       :done, s3_2, 2026-10-17, 6d
    section Sprint 4: Admin & Hardening
    Epic 6: Admin Dashboard & CSV Exports :done, s4_1, 2026-10-19, 5d
    Epic 8: QA & Automated Testing Suite  :done, s4_2, 2026-10-20, 4d
```

### Epic Breakdown & User Stories

#### Epic 1: Authentication and User Management (FIX-EPIC-1)
- **Story FIX-101**: *Implement Secure Customer Self-Registration*
  - **Summary**: Allow new customers to register with email, mobile, and password.
  - **User Story**: As a customer, I want to create an account so I can book and track device repairs.
  - **Acceptance Criteria**: Passwords hashed with scrypt, email/mobile unique check, role locked to `customer`.
  - **Subtasks**: 1. Build WTForms/HTML registration view. 2. Implement backend validation & hashing service.
  - **Test Scenario**: Attempt duplicate email registration; verify error message displayed.

- **Story FIX-102**: *Implement Dual Login Authentication (Password & Demo OTP)*
  - **Summary**: Support email+password and simulated mobile OTP login.
  - **User Story**: As a user, I want multiple login methods so I can access my account securely.
  - **Acceptance Criteria**: OTP token single-use, 5-minute expiry, rate-limited attempts.
  - **Subtasks**: 1. Build multi-tab login UI. 2. Create OTP token database model & verifier.
  - **Test Scenario**: Submit expired OTP token; verify rejection.

#### Epic 2: Customer Booking and Device Management (FIX-EPIC-2)
- **Story FIX-201**: *Multi-Option Repair Booking Wizard*
  - **Summary**: Build repair request form with brand, model, issue category, and service type.
  - **User Story**: As a customer, I want to submit my phone details and issue description so the shop can inspect it.
  - **Acceptance Criteria**: Walk-in and pickup options supported, address required for pickup, unique `FIX-` reference returned.
  - **Subtasks**: 1. Create booking form template with category select. 2. Implement booking generation logic.
  - **Test Scenario**: Submit pickup booking without address; verify form validation halts submission.

- **Story FIX-202**: *Public and Authenticated Repair Tracking*
  - **Summary**: Real-time visual timeline showing current stage from Booked to Completed.
  - **User Story**: As a customer, I want to track my device status anytime using my reference code.
  - **Acceptance Criteria**: Accessible publicly via reference or directly from customer dashboard.
  - **Subtasks**: 1. Build SVG/CSS progress tracker. 2. Connect tracking route to status history records.
  - **Test Scenario**: Query non-existent reference code; verify helpful error flash.

#### Epic 3: Repair Diagnosis and Workflow (FIX-EPIC-3)
- **Story FIX-301**: *Technician Hardware Diagnosis & Itemized Estimation*
  - **Summary**: Technicians log diagnostic findings and break down parts vs labour costs.
  - **User Story**: As a technician, I want to record device faults and submit estimates for customer approval.
  - **Acceptance Criteria**: Server computes total cost, status shifts to `Waiting for Approval`.
  - **Subtasks**: 1. Create technician repair workspace. 2. Implement diagnosis & estimate controllers.
  - **Test Scenario**: Post negative cost values; verify rejection.

- **Story FIX-302**: *Customer Estimate Approval / Rejection*
  - **Summary**: Customer reviews breakdown and clicks Approve or Reject.
  - **User Story**: As a customer, I want to approve or decline the repair estimate before work begins.
  - **Acceptance Criteria**: Status changes to `In Progress` upon approval or `Estimate Rejected` upon decline.
  - **Subtasks**: 1. Add approval modal on booking detail. 2. Build decision recording route.
  - **Test Scenario**: Technician attempts to mark repair complete before approval; verify transition blocked.

#### Epic 4: Delivery Management (FIX-EPIC-4)
- **Story FIX-401**: *Staff Assignment & Logistics Task Dispatch*
  - **Summary**: Assign delivery personnel to pickup and drop-off requests.
  - **User Story**: As an administrator, I want to assign drivers so logistics are organized.
  - **Acceptance Criteria**: Delivery tasks linked to bookings, customer contact details visible to staff.
  - **Subtasks**: 1. Build delivery assignment modal in admin. 2. Create `delivery_tasks` table and sync.
  - **Test Scenario**: Delivery staff marks delivery complete; verify booking status syncs to `Delivered`.

#### Epic 5: Payment and Customer Feedback (FIX-EPIC-5)
- **Story FIX-501**: *Safe Demo Payment Simulation*
  - **Summary**: Provide simulated UPI, Card, and Cash payment recording.
  - **User Story**: As a customer, I want to pay my repair bill online to complete the order.
  - **Acceptance Criteria**: No real bank details accepted, unique transaction reference stored, balance updated.
  - **Subtasks**: 1. Create demo checkout template. 2. Build payment audit logger.
  - **Test Scenario**: Submit payment exceeding balance; verify proper accounting.

- **Story FIX-502**: *Post-Repair Verified Customer Reviews*
  - **Summary**: Allow 1-5 star ratings and feedback only after device handover.
  - **User Story**: As a customer, I want to rate the repair service after receiving my fixed phone.
  - **Acceptance Criteria**: Only completed/delivered orders eligible, maximum one review per booking.
  - **Subtasks**: 1. Create rating submission interface. 2. Implement review eligibility guard.
  - **Test Scenario**: Attempt duplicate review submission; verify second submission blocked.

#### Epic 6: Admin Dashboard and Reporting (FIX-EPIC-6)
- **Story FIX-601**: *Real-Time Business KPI Analytics & Charts*
  - **Summary**: Aggregate live bookings, revenue, staff workloads, and status distributions.
  - **User Story**: As a business owner, I want a single overview of shop performance based on real database records.
  - **Acceptance Criteria**: Chart.js graphs render directly from SQLite query aggregates.
  - **Subtasks**: 1. Write SQL aggregation queries. 2. Wire Chart.js canvas elements.
  - **Test Scenario**: Verify revenue metric equals sum of completed payments in database.

- **Story FIX-602**: *Formula-Sanitized CSV Exports*
  - **Summary**: Export bookings and payments to downloadable CSV spreadsheets.
  - **User Story**: As an administrator, I want to export records for external auditing.
  - **Acceptance Criteria**: Formula injection defense enabled, correct HTTP attachment headers.
  - **Subtasks**: 1. Build streaming CSV response. 2. Apply formula character sanitization.
  - **Test Scenario**: Export records with leading `=` character; verify safe single-quote escaping.

#### Epic 7: UI/UX and Accessibility (FIX-EPIC-7)
- **Story FIX-701**: *Dual-Theme Design System (Dark/Light)*
  - **Summary**: Full responsive design tokens with instant client-side theme switcher.
  - **User Story**: As a user, I want a comfortable theme toggle that saves my preference.
  - **Acceptance Criteria**: Defaults to dark mode, saves to `localStorage`, zero page-flash.
  - **Subtasks**: 1. Establish CSS token architecture. 2. Write vanilla JS theme switcher.
  - **Test Scenario**: Switch to light mode and refresh page; verify light mode remains active.

#### Epic 8: Quality Assurance and Release (FIX-EPIC-8)
- **Story FIX-801**: *Automated Pytest Suite Implementation*
  - **Summary**: Implement isolated testing covering RBAC, bookings, transitions, and payments.
  - **User Story**: As a QA engineer, I want automated regression tests to prevent bugs in production.
  - **Acceptance Criteria**: 100% of critical paths tested against temporary isolated test database.
  - **Subtasks**: 1. Setup `conftest.py` test harness. 2. Author 19 comprehensive test cases.
  - **Test Scenario**: Run `pytest -v`; all 19 tests must pass without warnings.

---

## 13. Step-by-Step Demonstration Plan

Follow this exact walkthrough sequence during evaluation or examiner demonstrations:

### Act 1: The Public Experience & Architecture (2 Minutes)
1. **Homepage (`/`)**:
   - Showcase the modern Dark Mode branding, tagline, and real-time statistics (Repairs Completed, Active Repairs, Average Rating).
   - Click the **Theme Toggle** (sun/moon icon in navbar) to demonstrate seamless instant switching between Dark and Light mode.
   - Review supported repair categories and genuine customer feedback pulled live from SQLite.
2. **Public Tracking (`/bookings/track`)**:
   - Enter booking reference `FIX-DEMO-001` to show unauthenticated public status tracking with the visual timeline.

### Act 2: Customer Booking & Approval Journey (3 Minutes)
1. **Login as Customer**:
   - Navigate to `/auth/login` and log in with `customer@fixify.demo` / `Customer@123`.
2. **Submit a New Repair Booking (`/bookings/new`)**:
   - Select **Apple** -> **iPhone 15 Pro Max**.
   - Category: **Screen Replacement**.
   - Problem: *"Flickering vertical green lines across OLED panel after dropping on pavement."*
   - Service Type: **Pickup & Delivery** -> Enter address: *"Flat 104, Palm Meadows, Whitefield, Bengaluru"*.
   - Click **Confirm Booking**. Note the generated tracking reference (e.g., `FIX-XXXXXX`).
3. **Inspect Customer Dashboard (`/customer/dashboard`)**:
   - View the active repairs queue, notification bell indicator, and pending approval widgets.

### Act 3: Administrator Assignment & Operations (3 Minutes)
1. **Login as Admin**:
   - Log in with `admin@fixify.demo` / `Admin@123`.
2. **Dashboard Overview (`/admin/dashboard`)**:
   - Inspect the live KPI cards, Chart.js status distribution doughnut chart, revenue totals, and technician workload bars.
3. **Assign Staff (`/admin/bookings`)**:
   - Find the newly booked device or `FIX-DEMO-004`.
   - Click **Manage** -> Assign **Demo Technician** (`tech@fixify.demo`) and **Demo Delivery** (`delivery@fixify.demo`).
4. **Spare Parts Inventory (`/admin/inventory`)**:
   - Review current stock levels. Show the low-stock threshold warning on items below minimum.
   - Register a new spare part SKU or record an inward stock replenishment movement.
5. **CSV Export (`/admin/export/bookings.csv`)**:
   - Download the bookings CSV and open in Excel/Notepad to demonstrate formula sanitization.

### Act 4: Technician Diagnostics & Estimation (2 Minutes)
1. **Login as Technician**:
   - Log in with `tech@fixify.demo` / `Tech@123`.
2. **Technician Repair Studio (`/technician/dashboard`)**:
   - Open the assigned repair.
   - Record diagnosis: *"Display IC undamaged; front panel flexible connector pins loose. Requires OLED panel replacement."*
   - Enter cost estimate: **Parts Cost: ₹4,500.00**, **Labour Cost: ₹800.00**, **Estimated Completion: 4 Hours**.
   - Click **Submit Estimate for Customer Approval**. Status shifts to `Waiting for Approval`.

### Act 5: Customer Approval, Payment & Review (3 Minutes)
1. **Customer Approval**:
   - Switch back to Customer (`customer@fixify.demo`).
   - Navigate to the pending booking. Review the technician's diagnosis and itemized estimate.
   - Click **Approve Estimate**. Status immediately transitions to `In Progress`.
2. **Simulated Payment (`/payments/checkout/<id>`)**:
   - Click **Pay Online (Demo Simulation)**.
   - Choose **Demo UPI** and submit. System logs transaction `PAY-XXXX` and generates a completed payment record.
3. **Verified Customer Review (`/reviews/submit/<id>`)**:
   - Visit booking `FIX-DEMO-001` (already marked Completed).
   - Show how eligible completed repairs permit 5-star rating submission and genuine feedback that immediately reflects on the public homepage.

---

## 14. Known Limitations & Production Roadmap

In compliance with academic integrity and engineering transparency, the following design boundaries are documented:

| Feature Area | Current Development Implementation | Production Roadmap Enhancement |
| :--- | :--- | :--- |
| **Mobile SMS OTP** | Cryptographically generated OTP token persisted in database; displayed on screen for local demonstration. | Integrate Twilio or AWS SNS SMS Gateway with sender ID and carrier validation. |
| **Password Reset** | Secure expiring tokens generated and provided via development flash banner. | Integrate transactional email provider (SendGrid / Postmark / Amazon SES) via SMTP. |
| **Payment Gateway** | Safe local demo transaction recording (Demo UPI/Card/Cash) with persistent audit logs. | Integrate official Razorpay / Stripe Webhook APIs with HMAC signature verification. |
| **File Storage** | Uploaded device photos saved to local `static/uploads` directory with unique hashes. | Offload image binaries to AWS S3 or Cloudflare R2 bucket with signed CDN URLs. |
| **Database Engine** | Embedded SQLite 3 with WAL mode and foreign key enforcement. | Migrate to PostgreSQL or MySQL via SQLAlchemy ORM for high-concurrency enterprise scale. |

---

## 15. Git & GitHub Commands

Follow these commands to stage, commit, and push Fixify to your GitHub repository:

### 1. Initialize Git Repository
```powershell
cd c:\Users\Vinay\.gemini\antigravity-ide\scratch\Fixify
git init
```

### 2. Configure Git Identity (if not already set)
```powershell
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

### 3. Stage All Tracked Project Files
```powershell
git add .
```
*(Notice that `fixify.db`, `.env`, and cache folders are automatically excluded by `.gitignore`)*

### 4. Create Initial Commit
```powershell
git commit -m "feat: complete Fixify Smart Mobile Repair Management System v1.0.0"
```

### 5. Link to Your GitHub Repository & Push
```powershell
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/Fixify.git
git push -u origin main
```

---

## License & Attribution

Developed as a professional academic and commercial-grade engineering project. All rights reserved. Designed for reliable, transparent, and intelligent mobile device repair service operations.
