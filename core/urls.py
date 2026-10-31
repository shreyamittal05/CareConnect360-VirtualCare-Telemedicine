from django.contrib.auth.views import LoginView
from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_redirect, name="home"),
    path("login/", LoginView.as_view(template_name="core/login.html"), name="login"),
    path("register/", views.register, name="register"),
    path("logout/", views.user_logout, name="logout"),
    path("dashboard/", views.dashboard_redirect, name="dashboard_redirect"),
    path("patient/dashboard/", views.patient_dashboard, name="patient_dashboard"),
    path("doctor/dashboard/", views.doctor_dashboard, name="doctor_dashboard"),
    path("doctors/", views.doctors, name="doctors"),
    path("appointments/book/", views.book_appointment, name="book_appointment"),
    path("appointments/<int:pk>/<str:action>/", views.update_appointment, name="update_appointment"),
    path("consultations/<int:pk>/room/", views.consultation_room, name="consultation_room"),
    path("consultations/room/<str:room_id>/", views.video_consultation_room, name="video_consultation_room"),
    path("appointments/<int:appointment_id>/prescription/submit/", views.submit_prescription, name="submit_prescription"),
    path("consultations/<int:pk>/workspace/", views.consultation, name="consultation"),
    path("prescriptions/<int:pk>/pdf/", views.prescription_pdf, name="prescription_pdf"),
    path("invoices/<int:appointment_id>/checkout/", views.checkout, name="checkout"),
    path("invoices/<int:appointment_id>/", views.invoice, name="invoice"),
]
