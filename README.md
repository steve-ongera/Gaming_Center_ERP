# Gaming Lounge ERP — Backend

A production-oriented backend for a walk-in PS4/PS5 gaming lounge, built with
**Django 5**, **Django REST Framework**, and **PostgreSQL**, designed from day
one to grow into a full Gaming Betting Platform without an architectural
rewrite.

The backend deliberately uses a **single Django app (`api`)** with one file
per concern (`models.py`, `serializers.py`, `views.py`, `services.py`, etc.)
rather than being split into many small apps — as requested — while still
keeping a clean **service-layer architecture**: views stay thin, and all
business rules live in `api/services.py`.

---

## 1. Tech Stack

| Layer          | Technology |
|----------------|------------|
| Language        | Python 3.11+ |
| Framework       | Django 5 + Django REST Framework |
| Database        | PostgreSQL |
| Auth            | JWT (`djangorestframework-simplejwt`) |
| Docs            | OpenAPI/Swagger via `drf-spectacular` |
| Filtering       | `django-filter` |
| Caching/Queue   | Redis + Celery (for scheduled jobs / async notifications) |
| Static files    | WhiteNoise |

---

## 2. Project Structure

```
backend/
├── manage.py
├── requirements.txt
├── .env.example
├── config/
│   ├── settings.py        # all Django settings
│   ├── urls.py             # root URL conf (admin, api/, swagger)
│   ├── asgi.py
│   └── wsgi.py
└── api/
    ├── models.py           # every DB model (UUID PK, soft delete, audit-ready)
    ├── serializers.py      # every DRF serializer
    ├── views.py             # every ViewSet / APIView
    ├── urls.py               # every route (DRF router + explicit paths)
    ├── services.py           # ALL business logic (atomic transactions live here)
    ├── utils.py               # response envelope, pagination, helpers
    ├── permissions.py         # RBAC permission classes
    ├── filters.py              # django-filter FilterSets
    ├── admin.py                 # Django admin registrations
    ├── signals.py                # audit logging + side-effect hooks
    ├── middleware.py              # thread-local actor tracking for audit logs
    ├── tests.py                    # core service-layer test coverage
    └── migrations/
```

**Why a service layer inside one app?** Views only: parse input, call a
`services.py` function, and return `success_response(...)` /
`error_response(...)`. This keeps transactions, validation, and cross-model
side effects (e.g. "starting a session also flips the console to occupied
and fires a notification") in one testable place instead of scattered
across viewsets.

---

## 3. Core Domain Model

- **Consoles** — PS4/PS5/Xbox/Switch inventory, hourly rate, maintenance
  status. A partial unique constraint guarantees **only one active/paused
  session per console** at the database level, not just in application code.
- **Gaming Sessions** — the billable unit. Charges = hourly rate × duration
  (+ extra minutes) − discount/promotion, computed by
  `services.calculate_session_charges()` and snapshotted on stop.
- **Walk-ins vs. Customers** — anyone can start a session with just a name;
  `WalkInCustomer` is auto-created. `services.convert_walkin_to_customer()`
  upgrades them to a full `Customer` later and re-points their history.
- **Inventory & Sales** — `InventoryItem` + `StockMovement` give a full
  audit trail of every stock change; `services.create_sale()` deducts stock
  atomically and generates a receipt number.
- **Payments** — Cash, M-Pesa, Card, Bank Transfer today; `Payment.Method`
  already includes `WALLET` for when digital wallets go live.
- **Tournaments → Future Betting** — `Tournament` → `TournamentMatch` →
  `BettingMarket` → `Bet` is fully modeled now (wallets, odds, stakes,
  payouts, settlement) but the betting endpoints are gated behind
  `IsAdminOrManager` until the feature is switched on for the public — no
  schema changes will be needed at launch.
- **Audit Logs** — `AuditLog` is intentionally *not* soft-deletable; writes
  happen automatically via `signals.py` for sensitive models, using the
  current request's user/IP captured by `middleware.py`.

---

## 4. RBAC Roles

| Role | Typical access |
|------|------------------|
| `super_admin` | Everything, including system settings |
| `admin` | Full operational + reporting access |
| `manager` | Operations, reports, inventory, tournaments |
| `cashier` | Sessions, sales, payments, expenses |
| `attendant` | Sessions, bookings, walk-ins (no financial reports) |

See `api/permissions.py` for the composable permission classes
(`IsStaffRole`, `IsAdminOrManager`, `CanManageFinance`, `ReadOnlyOrStaff`, …).

---

## 5. Getting Started

```bash
# 1. Clone & enter the backend
cd backend

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# edit .env with your PostgreSQL credentials, SECRET_KEY, etc.

# 5. Create the database (PostgreSQL must be running)
createdb gaming_lounge_db

# 6. Run migrations
python manage.py makemigrations
python manage.py migrate

# 7. Create a superuser (role defaults to attendant — set role=super_admin in shell/admin)
python manage.py createsuperuser

# 8. Run the dev server
python manage.py runserver
```

API base URL: `http://localhost:8000/api/`
Swagger UI: `http://localhost:8000/api/docs/`
ReDoc: `http://localhost:8000/api/redoc/`
Django admin: `http://localhost:8000/admin/`

Run tests:

```bash
python manage.py test
```

---

## 6. Authentication

JWT-based. All endpoints except `/api/auth/login/` and public
(`ReadOnlyOrStaff`) GET endpoints require `Authorization: Bearer <token>`.

```
POST /api/auth/login/          { "username": "...", "password": "..." } -> access + refresh + user
POST /api/auth/refresh/        { "refresh": "..." } -> new access token
POST /api/auth/logout/         { "refresh": "..." } -> blacklists the refresh token
GET  /api/auth/me/             current user profile
PATCH /api/auth/me/            update current user profile
POST /api/auth/change-password/
```

---

## 7. Key Endpoints (non-exhaustive — see `/api/docs/` for the full schema)

| Area | Endpoint |
|------|----------|
| Dashboard | `GET /api/dashboard/summary/` |
| Start a session | `POST /api/gaming-sessions/start/` |
| Stop a session | `POST /api/gaming-sessions/{id}/stop/` |
| Live charge preview | `GET /api/gaming-sessions/{id}/preview_charges/` |
| Convert walk-in | `POST /api/walk-in-customers/convert/` |
| Record a sale | `POST /api/sales/` |
| Adjust stock | `POST /api/inventory-items/adjust_stock/` |
| Record a payment | `POST /api/payments/` |
| Register for tournament | `POST /api/tournaments/register_participant/` |
| Place a bet (future) | `POST /api/bets/` |
| Revenue report | `GET /api/reports/revenue/?period=month` |
| Console utilization | `GET /api/reports/console-utilization/?period=today` |
| Best sellers | `GET /api/reports/best-selling-products/?period=month` |
| Most played games | `GET /api/reports/most-played-games/?period=month` |
| Audit trail | `GET /api/audit-logs/` |

All responses use a standardized envelope:

```json
{
  "success": true,
  "message": "Request successful",
  "data": { "...": "..." },
  "errors": null
}
```

List endpoints add a `pagination` block (`count`, `num_pages`,
`current_page`, `next`, `previous`).

---

## 8. Reports & Exports

Revenue, expenses, profit, session, console-utilization, customer activity,
inventory valuation, low-stock, best-sellers, most-played-games, and
tournament/betting performance reports are all available via
`api/services.py` report functions and exposed as JSON through
`/api/reports/*`. PDF/Excel/CSV export endpoints can be layered on top of
these same service functions using `reportlab` and `openpyxl` (already in
`requirements.txt`).

---

## 9. Extending Toward the Betting Platform

No new apps or schema migrations are needed to switch on public betting:

1. Flip the `BettingMarketViewSet` / `BetViewSet` permission classes from
   `IsAdminOrManager` to a public/customer-facing permission.
2. Wire `services.place_bet()` and `services.settle_betting_market()` up to
   customer-facing auth (currently staff-only for safety).
3. Add a Celery beat task to auto-settle markets when
   `TournamentMatch.status` becomes `finished`.

---

## 10. Production Notes

- Set `DEBUG=False` and a real `SECRET_KEY` in production.
- Put PostgreSQL, Redis, and the Django app behind Gunicorn + a reverse
  proxy (Nginx). `gunicorn` and `whitenoise` are already in
  `requirements.txt`.
- Run `python manage.py collectstatic` before deploying.
- Point Celery workers/beat at the same `REDIS_URL` for background jobs
  (low-stock digest emails, booking reminders, tournament settlement).