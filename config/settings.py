from pathlib import Path
import os

MRP_VERSION = "1.0.8"

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "drf_spectacular",
    "apps.common",
    "apps.masterdata",
    "apps.inventory",
    "apps.demand",
    "apps.production",
    "apps.purchasing",
    "apps.planning",
    "apps.engineering",
    "apps.traceability",
    "apps.quality",
    "apps.recall",
    "apps.costing",
    "apps.shopfloor",
    "apps.maintenance",
    "apps.integrated_scheduling",
    "apps.ui",
    "apps.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.common.middleware.RequestContextMiddleware",
    "apps.common.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.ui.context_processors.ui_context",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

if os.getenv("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "mrp"),
            "USER": os.getenv("POSTGRES_USER", "mrp"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "mrp"),
            "HOST": os.getenv("POSTGRES_HOST", "db"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("POSTGRES_CONN_MAX_AGE", "60")),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "application_name": os.getenv("POSTGRES_APPLICATION_NAME", "mrp-django"),
                "options": f"-c statement_timeout={int(os.getenv('POSTGRES_STATEMENT_TIMEOUT_MS', '30000'))}",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "apps.common.permissions.MRPModelPermission",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "MRP API",
    "DESCRIPTION": "Planejamento de materiais, capacidade, produção, compras e estoque.",
    "VERSION": MRP_VERSION,
    "SERVE_INCLUDE_SCHEMA": False,
}


# Segurança e observabilidade configuráveis por ambiente.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if os.getenv("DJANGO_TRUST_PROXY", "0") == "1" else None
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "0") == "1"
SESSION_COOKIE_SECURE = os.getenv("DJANGO_SESSION_COOKIE_SECURE", "0") == "1"
CSRF_COOKIE_SECURE = os.getenv("DJANGO_CSRF_COOKIE_SECURE", "0") == "1"
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = os.getenv("DJANGO_SECURE_HSTS_PRELOAD", "0") == "1"

SPECTACULAR_SETTINGS = {
    "TITLE": "MRP API",
    "DESCRIPTION": "Planejamento de materiais, capacidade, produção, compras e estoque.",
    "VERSION": MRP_VERSION,
    "SERVE_INCLUDE_SCHEMA": False,

    "ENUM_NAME_OVERRIDES": {
        "ReservationStatusEnum": [
            ("OPEN", "Aberta"),
            ("CONSUMED", "Consumida"),
            ("CANCELLED", "Cancelada"),
        ],

        "PlanningRunStatusEnum": [
            ("DRAFT", "Rascunho"),
            ("RUNNING", "Executando"),
            ("COMPLETED", "Concluída"),
            ("FAILED", "Falhou"),
        ],

        "OptimizationRunStatusEnum": [
            ("DRAFT", "Rascunho"),
            ("RUNNING", "Executando"),
            ("COMPLETED", "Concluído"),
            ("FAILED", "Falhou"),
        ],

        "ApprovalDecisionEnum": [
            ("PENDING", "Pendente"),
            ("APPROVED", "Aprovada"),
            ("REJECTED", "Rejeitada"),
        ],

        "EngineeringRevisionStatusEnum": [
            ("DRAFT", "Rascunho"),
            ("RELEASED", "Liberada"),
            ("OBSOLETE", "Obsoleta"),
        ],

        "ActionStatusEnum": [
            ("OPEN", "Aberta"),
            ("IN_PROGRESS", "Em andamento"),
            ("DONE", "Concluída"),
            ("CANCELLED", "Cancelada"),
        ],

        "MaintenancePriorityEnum": [
            ("LOW", "Baixa"),
            ("NORMAL", "Normal"),
            ("HIGH", "Alta"),
            ("EMERGENCY", "Emergência"),
        ],

        "BusinessCriticalityEnum": [
            ("LOW", "Baixa"),
            ("MEDIUM", "Média"),
            ("HIGH", "Alta"),
            ("CRITICAL", "Crítica"),
        ],

        "ComplianceStatusEnum": [
            ("OPEN", "Aberto"),
            ("ACKNOWLEDGED", "Reconhecido"),
            ("RESOLVED", "Resolvido"),
        ],

        "PreferredChannelEnum": [
            ("EMAIL", "E-mail"),
            ("API", "API"),
            ("MANUAL", "Manual"),
        ],

        "RCCPSeverityEnum": [
            ("INFO", "Informação"),
            ("WARNING", "Atenção"),
            ("CRITICAL", "Crítica"),
        ],

        "FinancialCashFlowCategoryEnum": [
            ("PURCHASE_CASH", "Desembolso de compras"),
            ("LABOR", "Mão de obra"),
            ("MACHINE", "Máquina"),
            ("OVERHEAD", "Overhead/setup"),
            ("TOTAL_CASH", "Caixa operacional total"),
            ("INVENTORY_VALUE", "Estoque em valor"),
        ],

        "DecisionAuthorityLevelEnum": [
            ("MANAGER", "Gerente"),
            ("DIRECTOR", "Diretor"),
            ("EXECUTIVE_COMMITTEE", "Comitê executivo"),
        ],

        "ComplianceEscalationLevelEnum": [
            ("TEAM", "Equipe"),
            ("MANAGER", "Gerente"),
            ("DIRECTOR", "Diretor"),
            ("EXECUTIVE", "Executivo"),
        ],
    },
}

LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "apps.common.logging.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_DB_LOG_LEVEL", "WARNING").upper(),
            "propagate": False,
        },
        "mrp": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"



# Celery / solver assíncrono (0.6.6)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "7200"))
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "7000"))
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# 0.7.1 — scans operacionais para recovery scheduling
CELERY_BEAT_SCHEDULE = {
    "mps-compliance-escalation-15min": {
        "task": "integrated_scheduling.run_mps_compliance_escalation",
        "schedule": 900.0,
    },
    "mps-security-compliance-hourly": {
        "task": "integrated_scheduling.run_mps_security_compliance",
        "schedule": 3600.0,
    },
    "mps-decision-anchor-policy-daily": {
        "task": "integrated_scheduling.run_mps_anchor_policy",
        "schedule": 86400.0,
    },
    "scan-published-schedule-material-shortages": {
        "task": "integrated_scheduling.scan_material_shortages",
        "schedule": 300.0,
        "kwargs": {"lookahead_hours": int(os.getenv("RESCHEDULE_MATERIAL_LOOKAHEAD_HOURS", "24"))},
    },
}


# 0.7.5 — comunicação comercial. Em desenvolvimento, grava e-mails no console.
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "mrp@example.invalid")

# 0.9.4 external tamper-evident anchor storage. Mount this path on independent/WORM storage in production.
MPS_AUDIT_ANCHOR_DIR = os.getenv("MPS_AUDIT_ANCHOR_DIR", "/var/lib/mrp/audit_anchors")
MPS_AUDIT_ANCHOR_SECONDARY_DIR = os.getenv("MPS_AUDIT_ANCHOR_SECONDARY_DIR", "/var/lib/mrp/audit_anchors_secondary")
