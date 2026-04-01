stockiepilot/
│
├── manage.py
│
├── config/                      # Core project configuration
│   ├── __init__.py
│   ├── asgi.py
│   ├── wsgi.py
│   ├── urls.py
│   ├── celery.py               # Celery config
│   │
│   └── settings/
│       ├── __init__.py
│       ├── base.py             # Common settings
│       ├── dev.py              # Development
│       ├── prod.py             # Production
│
├── apps/                       # All domain apps (modular architecture)
│   ├── __init__.py
│
│   ├── users/                  # Authentication & user management
│   ├── companies/              # Multi-tenant logic
│   ├── subscriptions/          # Plans & subscription engine
│   ├── billing/                # Payments & invoices
│   ├── products/               # Product catalog
│   ├── inventory/              # Stock management
│   ├── sales/                  # Sales transactions
│   ├── analytics/              # Reporting & insights
│   ├── notifications/          # Emails, alerts
│   ├── audit/                  # Logs & tracking
│
├── core/                       # Shared logic across apps
│   ├── __init__.py
│   ├── middleware/             # Custom middleware
│   ├── permissions/            # RBAC logic
│   ├── utils/                  # Helpers
│   ├── services/               # Shared services
│   ├── constants/              # Global constants
│   ├── exceptions/             # Custom exceptions
│
├── api/                        # API layer (decoupled)
│   ├── __init__.py
│   ├── v1/
│       ├── __init__.py
│       ├── urls.py
│       ├── routers.py
│
├── templates/                  # HTML templates
├── static/                     # Static files
├── media/                      # Uploaded files
│
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   ├── prod.txt
│
├── .env
├── .env.example
├── .gitignore
│
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│
├── scripts/                    # DevOps scripts
│   ├── entrypoint.sh
│   ├── start.sh
│
└── docs/                       # Technical documentation