from decimal import Decimal

class Plans:
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"

    CHOICES = [FREE, BASIC, PRO, ENTERPRISE]
    LABELS = {
        FREE: "Free",
        BASIC: "Basic",
        PRO: "Pro",
        ENTERPRISE: "Enterprise",
    }

    
class BillingCycle:
    MONTHLY = "monthly"
    ANNUAL = "annual"

    CHOICES = [MONTHLY, ANNUAL]


class AnalyticsLevel:
    NONE = "none"
    BASIC = "basic"
    FULL = "full"
    ADVANCED = "advanced"


PLAN_DEFINITIONS = {
    Plans.FREE: {
        "monthly": Decimal("0"),
        "annual": Decimal("0"),
        "trial_days": 30,
        "max_products": 2,
        "analytics_level": AnalyticsLevel.NONE,
        "reports_access": "limited",
        "email_notifications": False,
        "inventory_alerts": False,
        "multi_branch": False,
        "priority_support": False,
    },
    Plans.BASIC: {
        "monthly": Decimal("2500"),
        "annual": Decimal("20000"),
        "trial_days": 0,
        "max_products": 10,
        "analytics_level": AnalyticsLevel.BASIC,
        "reports_access": "basic",
        "email_notifications": True,
        "inventory_alerts": False,
        "multi_branch": False,
        "priority_support": False,
    },
    Plans.PRO: {
        "monthly": Decimal("5000"),
        "annual": Decimal("50000"),
        "trial_days": 0,
        "max_products": None,
        "analytics_level": AnalyticsLevel.FULL,
        "reports_access": "full",
        "email_notifications": True,
        "inventory_alerts": True,
        "multi_branch": False,
        "priority_support": False,
    },
    Plans.ENTERPRISE: {
        "monthly": Decimal("15000"),
        "annual": Decimal("150000"),
        "trial_days": 0,
        "max_products": None,
        "analytics_level": AnalyticsLevel.ADVANCED,
        "reports_access": "full",
        "email_notifications": True,
        "inventory_alerts": True,
        "multi_branch": True,
        "priority_support": True,
    },
}