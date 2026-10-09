import calendar
import csv
import io
import json
import uuid
from datetime import date, datetime, time, timedelta
from functools import wraps

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access import can_access, get_profile, is_manager_user, scoped_employees
from .forms import EmployeeForm, LeaveForm, SalaryForm
from .models import Attendance, Employee, LeaveRequest, SalaryDetail


# ---------- helpers ----------
def day_range(d):
    """Start/end datetimes of a local day (avoids MySQL timezone-table lookups)."""
    start = timezone.make_aware(datetime.combine(d, time.min))
    return start, start + timedelta(days=1)


def parse_date(value, default):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return default


def manager_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_manager_user(request.user):
            messages.error(request, "Manager access is required for that page.")
            return redirect("dashboard")
        return view(request, *args, **kwargs)

    return login_required(wrapper)


# ---------- auth ----------
def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "home.html")


def portal_login(request, role):
    if role not in ("employee", "manager"):
        raise Http404
    if request.user.is_authenticated:
        return redirect("dashboard")
    data = None
    if request.method == "POST":
        data = request.POST.copy()
        ident = data.get("username", "").strip()
        if "@" in ident:  # allow sign-in with email
            u = User.objects.filter(email__iexact=ident).first()
            if u:
                data["username"] = u.username
    form = AuthenticationForm(request, data=data)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if role == "manager" and not is_manager_user(user):
            form.add_error(None, "This account does not have manager access.")
        elif role == "employee" and not get_profile(user):
            form.add_error(None, "No employee profile is linked to this account.")
        else:
            login(request, user)
            return redirect("dashboard")
    return render(request, "login.html", {"form": form, "role": role})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("home")


# ---------- dashboard ----------
@login_required
def dashboard(request):
    me = get_profile(request.user)
    mgr = is_manager_user(request.user)
    ctx = {}
    if me:
        records = me.attendance.all()
        ctx.update(
            record_count=records.count(),
            latest=records.first(),
            salary=SalaryDetail.objects.filter(employee=me).first(),
        )
    if mgr:
        emps = scoped_employees(request.user)
        start, end = day_range(timezone.localdate())
        today_in = Attendance.objects.filter(
            employee__in=emps, status=Attendance.IN, date_time__gte=start, date_time__lt=end
        )
        ctx.update(
            emp_count=emps.count(),
            present=today_in.values("employee").distinct().count(),
            late=today_in.filter(is_late=True).values("employee").distinct().count(),
            pending=LeaveRequest.objects.filter(
                employee__in=emps, status=LeaveRequest.PENDING
            ).count(),
            recent=Attendance.objects.filter(employee__in=emps).select_related("employee__user")[:8],
        )
    elif me:
        ctx["recent"] = me.attendance.select_related("employee__user")[:8]
        ctx["pending"] = me.leaves.filter(status=LeaveRequest.PENDING).count()
    return render(request, "dashboard.html", ctx)


# ---------- QR scanning ----------
@login_required
def scan(request):
    if not get_profile(request.user) and not is_manager_user(request.user):
        return redirect("dashboard")
    return render(request, "scan.html")


@login_required
@require_POST
def scan_api(request):
    try:
        payload = json.loads(request.body or b"{}").get("payload", "")
        if not payload.startswith("ATTENDLY:"):
            raise ValueError
        token = uuid.UUID(payload.split(":", 1)[1])
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"ok": False, "message": "That is not an Attendly ID card."}, status=400)

    emp = Employee.objects.select_related("user").filter(qr_token=token).first()
    if not emp:
        return JsonResponse({"ok": False, "message": "ID card not recognised."}, status=404)
    if not can_access(request.user, emp):
        return JsonResponse({"ok": False, "message": "This ID card belongs to someone else."}, status=403)

    now = timezone.localtime()
    start, end = day_range(now.date())
    today = Attendance.objects.filter(employee=emp, date_time__gte=start, date_time__lt=end)
    last = today.order_by("-date_time").first()
    if last and (now - last.date_time).total_seconds() < 60:
        return JsonResponse({"ok": False, "message": "Already scanned a moment ago. Wait a minute."})

    status = Attendance.OUT if last and last.status == Attendance.IN else Attendance.IN
    late = False
    if status == Attendance.IN and not today.filter(status=Attendance.IN).exists():
        h, m = (int(x) for x in settings.LATE_AFTER.split(":"))
        late = now.time() > time(h, m)
    Attendance.objects.create(employee=emp, status=status, is_late=late, date_time=now)
    label = "Checked in" if status == Attendance.IN else "Checked out"
    msg = f"{emp.full_name}: {label} at {now:%I:%M %p}" + (" (late)" if late else "")
    return JsonResponse({"ok": True, "message": msg})


# ---------- calendar ----------
@login_required
def calendar_view(request):
    me = get_profile(request.user)
    mgr = is_manager_user(request.user)
    choices = list(scoped_employees(request.user).order_by("employee_code")) if mgr else ([me] if me else [])
    if not choices:
        messages.info(request, "No employee records to show yet.")
        return redirect("dashboard")
    emp = me or choices[0]
    sel = request.GET.get("emp", "")
    if mgr and sel.isdigit():
        emp = next((e for e in choices if e.pk == int(sel)), emp)

    today = timezone.localdate()
    try:
        y, m = (int(x) for x in request.GET.get("month", "").split("-"))
        first = date(y, m, 1)
    except ValueError:
        first = today.replace(day=1)
    last = date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
    prev_month = (first - timedelta(days=1)).replace(day=1)
    next_month = last + timedelta(days=1)

    start, _ = day_range(first)
    _, end = day_range(last)
    seen = {}
    for r in Attendance.objects.filter(employee=emp, status=Attendance.IN, date_time__gte=start, date_time__lt=end):
        d = timezone.localtime(r.date_time).date()
        seen[d] = seen.get(d, False) or r.is_late
    leave_days = set()
    for lv in LeaveRequest.objects.filter(
        employee=emp, status=LeaveRequest.APPROVED, start_date__lte=last, end_date__gte=first
    ):
        d = lv.start_date
        while d <= lv.end_date:
            leave_days.add(d)
            d += timedelta(days=1)

    counts = {"present": 0, "late": 0, "leave": 0, "absent": 0}
    weeks = []
    for week in calendar.Calendar(firstweekday=6).monthdatescalendar(first.year, first.month):
        row = []
        for d in week:
            if d.month != first.month:
                state = "out"
            elif d in leave_days:
                state = "leave"
            elif d > today:
                state = "future"
            elif d in seen:
                state = "late" if seen[d] else "present"
            elif d.weekday() >= 5:
                state = "weekend"
            else:
                state = "absent"
            if state in counts:
                counts[state] += 1
            row.append({"day": d.day, "state": state, "today": d == today})
        weeks.append(row)
    ctx = {
        "weeks": weeks, "counts": counts, "emp": emp, "choices": choices if mgr else [],
        "month_label": first.strftime("%B %Y"),
        "prev": prev_month.strftime("%Y-%m"), "next": next_month.strftime("%Y-%m"),
    }
    return render(request, "calendar.html", ctx)


# ---------- reports ----------
@login_required
def reports(request):
    me = get_profile(request.user)
    mgr = is_manager_user(request.user)
    if mgr:
        emps = scoped_employees(request.user)
    elif me:
        emps = Employee.objects.filter(pk=me.pk)
    else:
        emps = Employee.objects.none()
    today = timezone.localdate()
    d_from = parse_date(request.GET.get("from"), today.replace(day=1))
    d_to = parse_date(request.GET.get("to"), today)
    sel = request.GET.get("emp", "")
    if mgr and sel.isdigit():
        emps = emps.filter(pk=int(sel))
    start, _ = day_range(d_from)
    _, end = day_range(d_to)
    qs = Attendance.objects.filter(
        employee__in=emps, date_time__gte=start, date_time__lt=end
    ).select_related("employee__user", "employee__department")

    if request.GET.get("export") == "csv":
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="attendance_{d_from}_{d_to}.csv"'
        w = csv.writer(resp)
        w.writerow(["Employee ID", "Name", "Department", "Date", "Time", "Status", "Late"])
        for r in qs:
            t = timezone.localtime(r.date_time)
            w.writerow([r.employee.employee_code, r.employee.full_name, r.employee.department.name,
                        t.date(), t.strftime("%H:%M:%S"), r.get_status_display(), "Yes" if r.is_late else "No"])
        return resp

    rows = list(qs[:500])
    days = {(r.employee_id, timezone.localtime(r.date_time).date()) for r in rows if r.status == Attendance.IN}
    ctx = {
        "rows": rows, "d_from": d_from, "d_to": d_to, "sel": sel,
        "employees": scoped_employees(request.user).order_by("employee_code") if mgr else [],
        "days_present": len(days), "late_count": sum(1 for r in rows if r.is_late and r.status == Attendance.IN),
    }
    return render(request, "reports.html", ctx)


# ---------- leave ----------
@login_required
def leave(request):
    me = get_profile(request.user)
    if not me:
        messages.info(request, "Leave requests are for employee accounts.")
        return redirect("dashboard")
    form = LeaveForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.employee = me
        obj.save()
        messages.success(request, "Leave request submitted.")
        return redirect("leave")
    return render(request, "leave.html", {"form": form, "leaves": me.leaves.all()})


@manager_required
def leave_review(request):
    leaves = LeaveRequest.objects.filter(
        employee__in=scoped_employees(request.user)
    ).select_related("employee__user")
    return render(request, "leave_review.html", {"leaves": leaves})


@manager_required
@require_POST
def leave_action(request, pk, action):
    if action not in ("approve", "reject"):
        raise Http404
    lv = get_object_or_404(
        LeaveRequest.objects.select_related("employee__user"),
        pk=pk, employee__in=scoped_employees(request.user),
    )
    if lv.employee.user_id == request.user.id and not request.user.is_superuser:
        messages.error(request, "You cannot review your own leave request.")
    else:
        lv.status = LeaveRequest.APPROVED if action == "approve" else LeaveRequest.REJECTED
        lv.save()
        messages.success(request, f"Leave {lv.get_status_display().lower()} for {lv.employee.full_name}.")
    return redirect("leave_review")


# ---------- employee management ----------
@manager_required
def employees(request):
    rows = list(scoped_employees(request.user))
    sal = {s.employee_id: s for s in SalaryDetail.objects.filter(employee__in=rows)}
    for e in rows:
        e.salary_obj = sal.get(e.pk)
    return render(request, "employees.html", {"rows": rows})


@manager_required
def employee_edit(request, pk=None):
    inst = get_object_or_404(scoped_employees(request.user), pk=pk) if pk else None
    form = EmployeeForm(request.POST or None, request_user=request.user, instance=inst)
    if request.method == "POST" and form.is_valid():
        emp = form.save()
        messages.success(request, f"Saved {emp.full_name}.")
        return redirect("employees")
    return render(request, "employee_form.html", {"form": form, "inst": inst})


@manager_required
def salary_edit(request, pk):
    emp = get_object_or_404(scoped_employees(request.user), pk=pk)
    form = SalaryForm(request.POST or None, instance=SalaryDetail.objects.filter(employee=emp).first())
    if request.method == "POST" and form.is_valid():
        s = form.save(commit=False)
        s.employee = emp
        s.save()
        messages.success(request, f"Salary updated for {emp.full_name}.")
        return redirect("employees")
    return render(request, "salary_form.html", {"form": form, "emp": emp})


# ---------- ID card + QR ----------
@login_required
def id_card(request, pk):
    emp = get_object_or_404(Employee.objects.select_related("user", "department"), pk=pk)
    if not can_access(request.user, emp):
        raise Http404
    return render(request, "id_card.html", {"emp": emp})


@login_required
def qr_image(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    if not can_access(request.user, emp):
        raise Http404
    img = qrcode.make(emp.qr_payload, image_factory=qrcode.image.svg.SvgPathImage, box_size=10)
    buf = io.BytesIO()
    img.save(buf)
    return HttpResponse(buf.getvalue(), content_type="image/svg+xml")
