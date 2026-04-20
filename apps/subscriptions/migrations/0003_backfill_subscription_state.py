from datetime import timedelta

from django.db import migrations
from django.utils import timezone


PLAN_MONTHLY = {
    "free": 0,
    "basic": 2500,
    "pro": 5000,
    "enterprise": 15000,
}


def forwards(apps, schema_editor):
    Company = apps.get_model("companies", "Company")
    Subscription = apps.get_model("subscriptions", "Subscription")

    now = timezone.now()

    for sub in Subscription.objects.all().order_by("id"):
        plan_name = (sub.plan.name.lower() if getattr(sub, "plan", None) else None) or "free"
        sub.plan_name = plan_name

        if sub.status == "trial":
            sub.status = "trialing"
        elif sub.status == "cancelled":
            sub.status = "canceled"

        if sub.billing_cycle == "yearly":
            sub.billing_cycle = "annual"

        sub.started_at = sub.start_date or sub.created_at or now
        sub.current_period_start = sub.current_period_start or sub.start_date or sub.started_at

        if sub.status == "trialing":
            trial_end = sub.trial_end_date or sub.end_date or (sub.started_at + timedelta(days=30))
            sub.trial_start = sub.trial_start or sub.started_at
            sub.trial_end = sub.trial_end or trial_end
            sub.current_period_end = sub.current_period_end or trial_end
            sub.auto_renew = False
            sub.amount = 0
        else:
            sub.current_period_end = sub.current_period_end or sub.end_date
            sub.amount = sub.amount or PLAN_MONTHLY.get(plan_name, 0)

        if sub.current_period_end:
            sub.end_date = sub.current_period_end
        sub.trial_end_date = sub.trial_end
        sub.save()

    for company in Company.objects.all():
        latest = Subscription.objects.filter(company=company).order_by("-created_at").first()
        if latest:
            if hasattr(company, "subscription_plan"):
                company.subscription_plan = latest.plan_name
                company.save(update_fields=["subscription_plan"])
            continue

        trial_end = now + timedelta(days=30)
        created = Subscription.objects.create(
            company=company,
            plan_name="free",
            billing_cycle="monthly",
            amount=0,
            status="trialing",
            auto_renew=False,
            started_at=now,
            current_period_start=now,
            current_period_end=trial_end,
            trial_start=now,
            trial_end=trial_end,
            start_date=now,
            end_date=trial_end,
            trial_end_date=trial_end,
        )
        if hasattr(company, "subscription_plan"):
            company.subscription_plan = created.plan_name
            company.save(update_fields=["subscription_plan"])


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0002_subscription_amount_subscription_canceled_at_and_more"),
        ("companies", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
