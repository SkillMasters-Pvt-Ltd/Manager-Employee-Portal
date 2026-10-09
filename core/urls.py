from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/<str:role>/", views.portal_login, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("scan/", views.scan, name="scan"),
    path("scan/submit/", views.scan_api, name="scan_api"),
    path("calendar/", views.calendar_view, name="calendar"),
    path("reports/", views.reports, name="reports"),
    path("leave/", views.leave, name="leave"),
    path("leave/review/", views.leave_review, name="leave_review"),
    path("leave/<int:pk>/<str:action>/", views.leave_action, name="leave_action"),
    path("employees/", views.employees, name="employees"),
    path("employees/new/", views.employee_edit, name="employee_new"),
    path("employees/<int:pk>/edit/", views.employee_edit, name="employee_edit"),
    path("employees/<int:pk>/salary/", views.salary_edit, name="salary_edit"),
    path("employees/<int:pk>/card/", views.id_card, name="id_card"),
    path("employees/<int:pk>/qr.svg", views.qr_image, name="qr_image"),
]
