# apps/subscriptions/constants.py

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

    PRICES = {
        FREE: 0,
        BASIC: 2500,
        PRO: 5000,
        ENTERPRISE: 15000,
    }