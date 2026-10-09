from .models import Employee


def get_profile(user):
    if not user.is_authenticated:
        return None
    return Employee.objects.select_related("user", "department").filter(user=user).first()


def is_manager_user(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    p = get_profile(user)
    return bool(p and p.is_manager)


def scoped_employees(user):
    """Employees this user may manage: everyone for admins, own department for managers."""
    qs = Employee.objects.select_related("user", "department")
    if user.is_superuser:
        return qs
    p = get_profile(user)
    if p and p.is_manager:
        return qs.filter(department=p.department)
    return qs.none()


def can_access(user, emp):
    if user.is_superuser:
        return True
    p = get_profile(user)
    if not p:
        return False
    return p.pk == emp.pk or (p.is_manager and p.department_id == emp.department_id)
