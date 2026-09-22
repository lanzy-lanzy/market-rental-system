from django.core.management.base import BaseCommand

from core.helpers import apply_overdue_penalties


class Command(BaseCommand):
    help = 'Apply overdue status and retroactive penalties to unpaid billings (grace-aware).'

    def handle(self, *args, **options):
        overdue, penalized = apply_overdue_penalties()
        self.stdout.write(self.style.SUCCESS(
            f'Overdue marked: {overdue}, penalties applied: {penalized}'
        ))
