from django import forms
from django.contrib.auth.models import User
from django.db import transaction

from .access import get_profile
from .models import Department, Employee, LeaveRequest, SalaryDetail

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class LeaveForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ["start_date", "end_date", "reason"]
        widgets = {
            "start_date": DATE,
            "end_date": DATE,
            "reason": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cd = super().clean()
        s, e = cd.get("start_date"), cd.get("end_date")
        if s and e and e < s:
            self.add_error("end_date", "End date cannot be before the start date.")
        return cd


class SalaryForm(forms.ModelForm):
    class Meta:
        model = SalaryDetail
        fields = ["salary", "incentives", "allowances", "deductions", "effective_from"]
        widgets = {"effective_from": DATE}


class EmployeeForm(forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField()
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="Required for new employees. Leave blank to keep the current password.",
    )
    employee_code = forms.CharField(max_length=20, label="Employee ID")
    designation = forms.CharField(max_length=100)
    department = forms.ModelChoiceField(queryset=Department.objects.all())
    phone = forms.CharField(max_length=15, required=False)
    is_manager = forms.BooleanField(required=False, label="Manager access")

    def __init__(self, *args, request_user, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        if not request_user.is_superuser:
            p = get_profile(request_user)
            self.fields["department"].queryset = Department.objects.filter(pk=p.department_id)
            self.fields["department"].empty_label = None
            del self.fields["is_manager"]
        if instance and not self.is_bound:
            u = instance.user
            self.initial = {
                "username": u.username, "first_name": u.first_name, "last_name": u.last_name,
                "email": u.email, "employee_code": instance.employee_code,
                "designation": instance.designation, "department": instance.department_id,
                "phone": instance.phone, "is_manager": instance.is_manager,
            }

    def clean_username(self):
        v = self.cleaned_data["username"]
        qs = User.objects.filter(username__iexact=v)
        if self.instance:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError("This username is already taken.")
        return v

    def clean_employee_code(self):
        v = self.cleaned_data["employee_code"]
        qs = Employee.objects.filter(employee_code__iexact=v)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This employee ID already exists.")
        return v

    def clean(self):
        cd = super().clean()
        if not self.instance and not cd.get("password"):
            self.add_error("password", "Set a password for the new employee.")
        return cd

    @transaction.atomic
    def save(self):
        cd = self.cleaned_data
        emp = self.instance or Employee()
        user = emp.user if self.instance else User()
        user.username = cd["username"]
        user.first_name = cd["first_name"]
        user.last_name = cd.get("last_name", "")
        user.email = cd["email"]
        if cd.get("password"):
            user.set_password(cd["password"])
        user.save()
        emp.user = user
        emp.employee_code = cd["employee_code"]
        emp.designation = cd["designation"]
        emp.department = cd["department"]
        emp.phone = cd.get("phone", "")
        if "is_manager" in cd:
            emp.is_manager = cd["is_manager"]
        emp.save()
        return emp
