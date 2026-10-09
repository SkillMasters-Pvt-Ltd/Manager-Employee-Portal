from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import Department, Employee, SalaryDetail

DEMO_PASSWORD = "SkillMasters"  # password given to every demo account below


class Command(BaseCommand):
    help = "Create a demo department, one manager and two employees."

    def handle(self, *args, **opts):
        dept, _ = Department.objects.get_or_create(name="Engineering")
        people = [
            ("manager1", "Anitha", "R", "EMP001", "Engineering Manager", True, "60000"),
            ("priyadharshini", "Priyadharshini", "K", "EMP002", "Software Developer", False, "24999.97"),
            ("employee2", "Karthik", "S", "EMP003", "QA Analyst", False, "22000"),
        ]
        for username, first, last, code, desig, mgr, sal in people:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": first, "last_name": last, "email": f"{username}@example.com"},
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            emp, _ = Employee.objects.get_or_create(
                user=user,
                defaults={"employee_code": code, "designation": desig, "department": dept, "is_manager": mgr},
            )
            SalaryDetail.objects.get_or_create(
                employee=emp,
                defaults={
                    "salary": Decimal(sal), "incentives": Decimal("1000.00"),
                    "allowances": Decimal("499.99"), "deductions": Decimal("99.98"),
                    "effective_from": date.today().replace(day=1),
                },
            )
        self.stdout.write(self.style.SUCCESS("Demo data ready. Usernames: manager1, priyadharshini, employee2"))
