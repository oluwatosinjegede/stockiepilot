from django.core.management.base import BaseCommand
from apps.companies.models import Company


class Command(BaseCommand):
    help = "Fix duplicate companies"

    def handle(self, *args, **kwargs):

        seen = {}

        for c in Company.objects.all():
            key = c.name.lower()

            if key in seen:
                self.stdout.write(f"Deleting duplicate: {c.id} {c.name}")
                c.delete()
            else:
                seen[key] = c.id

        self.stdout.write("Done fixing duplicates")