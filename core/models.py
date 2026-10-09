import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="employee")
    employee_code = models.CharField(max_length=20, unique=True)
    designation = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    phone = models.CharField(max_length=15, blank=True)
    is_manager = models.BooleanField(default=False)
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        ordering = ["employee_code"]

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def qr_payload(self):
        return f"ATTENDLY:{self.qr_token}"

    def __str__(self):
        return f"{self.employee_code} - {self.full_name}"


class Attendance(models.Model):
    IN, OUT = "IN", "OUT"
    STATUS_CHOICES = [(IN, "Check In"), (OUT, "Check Out")]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance")
    status = models.CharField(max_length=3, choices=STATUS_CHOICES)
    is_late = models.BooleanField(default=False)
    date_time = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-date_time"]

    def __str__(self):
        return f"{self.employee.employee_code} {self.status} {self.date_time:%Y-%m-%d %H:%M}"


class LeaveRequest(models.Model):
    PENDING, APPROVED, REJECTED = "PENDING", "APPROVED", "REJECTED"
    STATUS_CHOICES = [(PENDING, "Pending"), (APPROVED, "Approved"), (REJECTED, "Rejected")]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leaves")
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1


class SalaryDetail(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name="salary")
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    incentives = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    allowances = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    effective_from = models.DateField(default=timezone.localdate)

    @property
    def net_salary(self):
        return self.salary + self.incentives + self.allowances - self.deductions
