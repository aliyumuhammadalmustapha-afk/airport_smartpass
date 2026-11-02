from django.urls import path

from . import views

urlpatterns = [
    path("", views.gate_login, name="gate_login"),
    path("scanner/", views.gate_scanner, name="gate_scanner"),
    path("history/", views.staff_scan_history, name="gate_history"),
    path("verify/", views.verify_qr, name="gate_verify"),
    path("logs/", views.verification_logs, name="verification_logs"),
]
