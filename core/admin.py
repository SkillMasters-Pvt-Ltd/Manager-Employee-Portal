from django.contrib import admin
from .models import Attendance, Department, Employee, LeaveRequest, SalaryDetail

for m in (Department, Employee, Attendance, LeaveRequest, SalaryDetail):
    admin.site.register(m)
