import secrets
from functools import wraps
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from .forms import RegistrationForm, BookingForm, PrescriptionForm, PrescriptionItemFormSet, PaymentForm
from .models import CustomUser, Appointment, Prescription, PrescriptionItem, Invoice


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")
            user_role = str(getattr(request.user, "role", "")).strip().upper()
            allowed_roles = {str(role).strip().upper() for role in roles}
            if user_role not in allowed_roles and not request.user.is_superuser:
                return HttpResponseForbidden(
                    f"You do not have permission to access this portal. "
                    f"Logged-in role: {user_role or 'NOT SET'}; required: {', '.join(allowed_roles)}"
                )
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard_redirect")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your CareConnect360 patient account is ready.")
        return redirect("patient_dashboard")
    return render(request, "core/register.html", {"form": form})


def user_logout(request):
    logout(request)
    return redirect("login")

@login_required
def dashboard_redirect(request):
    role = str(request.user.role).strip().upper()
    if role == CustomUser.Role.DOCTOR:
        return redirect("doctor_dashboard")
    if role == CustomUser.Role.ADMIN:
        return redirect("admin:index")
    return redirect("patient_dashboard")

@role_required("PATIENT")
def patient_dashboard(request):
    appointments = request.user.patient_appointments.select_related("doctor__doctor_profile", "invoice").order_by("-scheduled_at")
    return render(request, "core/dashboard_patient.html", {"appointments": appointments})

@role_required("DOCTOR")
def doctor_dashboard(request):
    """Doctor workspace: appointments are separated into today's/upcoming and completed work."""
    appointments = (request.user.doctor_appointments
                    .select_related("patient", "patient__patient_profile")
                    .prefetch_related("prescription")
                    .order_by("scheduled_at"))
    today = timezone.localdate()
    upcoming = appointments.filter(
        Q(status__in=("REQUESTED", "SCHEDULED", "ACCEPTED", "IN_PROGRESS"))
    ).exclude(scheduled_at__date__lt=today)
    completed = appointments.filter(status="COMPLETED").order_by("-scheduled_at")
    todays_appointments = appointments.filter(scheduled_at__date=today)
    counts = {
        "today_total": todays_appointments.count(),
        "pending": todays_appointments.filter(status__in=("REQUESTED", "SCHEDULED", "ACCEPTED")).count(),
        "today_completed": todays_appointments.filter(status="COMPLETED").count(),
    }
    return render(request, "core/dashboard_doctor.html", {
        "appointments": upcoming,
        "upcoming_appointments": upcoming,
        "completed_appointments": completed,
        "counts": counts,
    })

@role_required("PATIENT")
def doctors(request):
    doctors = CustomUser.objects.filter(role="DOCTOR", is_active=True).select_related("doctor_profile").order_by("doctor_profile__specialization")
    return render(request, "core/doctors.html", {"doctors": doctors})

@role_required("PATIENT")
def book_appointment(request):
    form = BookingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                appointment = form.save(commit=False)
                appointment.patient = request.user
                appointment.save()
                Invoice.objects.create(appointment=appointment,
                    amount=appointment.doctor.doctor_profile.consultation_fee)
            messages.success(request, "Appointment requested. Complete payment when prompted.")
            return redirect("patient_dashboard")
        except Exception as exc:
            messages.error(request, "That slot is unavailable or could not be booked. Please choose another time.")
    return render(request, "core/booking.html", {"form": form})

@role_required("DOCTOR")
@require_POST
@transaction.atomic
def update_appointment(request, pk, action):
    appointment = get_object_or_404(Appointment, pk=pk, doctor=request.user)
    allowed = {"accept": Appointment.Status.SCHEDULED, "reject": Appointment.Status.REJECTED,
               "complete": Appointment.Status.COMPLETED, "cancel": Appointment.Status.CANCELLED}
    if action in allowed:
        appointment.status = allowed[action]
        appointment.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Appointment marked {appointment.get_status_display().lower()}.")
    return redirect("doctor_dashboard")

@role_required("PATIENT", "DOCTOR")
def consultation_room(request, pk):
    """Backward-compatible appointment-ID entry point."""
    appointment = get_object_or_404(Appointment, pk=pk)
    return redirect("video_consultation_room", room_id=appointment.room_id)


@role_required("PATIENT", "DOCTOR")
def video_consultation_room(request, room_id):
    """Authorize both sides of the call using the unguessable appointment room ID."""
    appointment = get_object_or_404(
        Appointment.objects.select_related(
            "patient", "patient__patient_profile", "doctor", "doctor__doctor_profile"
        ).prefetch_related("prescription__items"), room_id=room_id
    )
    if request.user != appointment.patient and request.user != appointment.doctor:
        return HttpResponseForbidden("This consultation room is private to its assigned participants.")

    allowed_statuses = (Appointment.Status.REQUESTED, Appointment.Status.SCHEDULED,
                        Appointment.Status.ACCEPTED, Appointment.Status.IN_PROGRESS,
                        Appointment.Status.COMPLETED)
    if appointment.status not in allowed_statuses:
        messages.warning(request, "This consultation is not currently available.")
        return redirect("dashboard_redirect")

    if request.user == appointment.doctor and appointment.status != Appointment.Status.COMPLETED:
        if appointment.status != Appointment.Status.IN_PROGRESS:
            appointment.status = Appointment.Status.IN_PROGRESS
            appointment.save(update_fields=["status", "updated_at"])

    patient_profile = getattr(appointment.patient, "patient_profile", None)
    prescription = getattr(appointment, "prescription", None)
    return render(request, "core/video_room.html", {
        "appointment": appointment,
        "patient_profile": patient_profile,
        "prescription": prescription,
        "jitsi_domain": settings.JITSI_DOMAIN,
        "display_name": request.user.get_full_name() or request.user.username,
        "room_name": room_id,
    })


@role_required("DOCTOR")
@require_POST
@transaction.atomic
def submit_prescription(request, appointment_id):
    appointment = get_object_or_404(Appointment, pk=appointment_id, doctor=request.user)
    diagnosis = request.POST.get("diagnosis", "").strip()
    if not diagnosis:
        messages.error(request, "Diagnosis is required.")
        return redirect("consultation", pk=appointment.pk)

    prescription, _ = Prescription.objects.get_or_create(
        appointment=appointment,
        defaults={"diagnosis": diagnosis},
    )
    prescription.diagnosis = diagnosis
    prescription.doctor_notes = request.POST.get("doctor_notes", "").strip()
    follow_up = request.POST.get("follow_up_date")
    prescription.follow_up_date = follow_up or None
    prescription.save()

    medicine_names = request.POST.getlist("medicine_name[]")
    dosages = request.POST.getlist("dosage[]")
    frequencies = request.POST.getlist("frequency[]")
    durations = request.POST.getlist("duration[]")
    prescription.items.all().delete()
    for medicine, dosage, frequency, duration in zip(medicine_names, dosages, frequencies, durations):
        if medicine.strip():
            PrescriptionItem.objects.create(
                prescription=prescription,
                medicine_name=medicine.strip(), dosage=dosage.strip(),
                frequency=frequency.strip(), duration=duration.strip(),
            )
    appointment.status = Appointment.Status.COMPLETED
    appointment.save(update_fields=["status", "updated_at"])
    messages.success(request, "Prescription submitted and consultation completed.")
    return redirect("doctor_dashboard")

@role_required("DOCTOR")
@transaction.atomic
def consultation(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk, doctor=request.user)
    prescription = getattr(appointment, "prescription", None)
    form = PrescriptionForm(request.POST or None, instance=prescription)
    if prescription:
        formset = PrescriptionItemFormSet(request.POST or None, instance=prescription)
    else:
        placeholder = Prescription(appointment=appointment)
        formset = PrescriptionItemFormSet(request.POST or None, instance=placeholder)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        prescription = form.save(commit=False)
        prescription.appointment = appointment
        prescription.save()
        formset.instance = prescription
        formset.save()
        messages.success(request, "Consultation and e-prescription saved securely.")
        return redirect("consultation", pk=appointment.pk)
    return render(request, "core/prescription_form.html", {"appointment": appointment, "form": form, "formset": formset})

@role_required("PATIENT", "DOCTOR")
def prescription_pdf(request, pk):
    prescription = get_object_or_404(Prescription.objects.select_related("appointment__patient", "appointment__doctor"), pk=pk)
    appointment = prescription.appointment
    if request.user not in (appointment.patient, appointment.doctor) and not request.user.is_superuser:
        return HttpResponseForbidden()
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename=prescription_{prescription.pk}.pdf"
    pdf = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    pdf.setTitle(f"CareConnect360 Prescription #{prescription.pk}")
    pdf.setFont("Helvetica-Bold", 18); pdf.drawString(40, height-50, "CareConnect360 VirtualCare")
    pdf.setFont("Helvetica", 10); pdf.drawString(40, height-68, "CONFIDENTIAL MEDICAL DOCUMENT")
    pdf.line(40, height-78, width-40, height-78)
    pdf.setFont("Helvetica-Bold", 11); pdf.drawString(40, height-105, "Patient:")
    pdf.setFont("Helvetica", 11); pdf.drawString(95, height-105, str(appointment.patient))
    pdf.setFont("Helvetica-Bold", 11); pdf.drawString(40, height-125, "Doctor:")
    pdf.setFont("Helvetica", 11); pdf.drawString(95, height-125, str(appointment.doctor))
    y = height - 165
    pdf.setFont("Helvetica-Bold", 12); pdf.drawString(40, y, "Diagnosis")
    pdf.setFont("Helvetica", 11); y -= 18
    for line in prescription.diagnosis.splitlines() or ["—"]:
        pdf.drawString(40, y, line[:110]); y -= 15
    y -= 10; pdf.setFont("Helvetica-Bold", 12); pdf.drawString(40, y, "Prescription")
    y -= 22; pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, "Medicine"); pdf.drawString(200, y, "Dosage"); pdf.drawString(300, y, "Frequency"); pdf.drawString(400, y, "Duration")
    pdf.setFont("Helvetica", 10); y -= 18
    for item in prescription.items.all():
        pdf.drawString(40, y, item.medicine_name[:25]); pdf.drawString(200, y, item.dosage[:15])
        pdf.drawString(300, y, item.frequency[:15]); pdf.drawString(400, y, item.duration[:15])
        y -= 18
    pdf.setFont("Helvetica-Bold", 11); pdf.drawString(40, 70, "Notes: "); pdf.setFont("Helvetica", 10); pdf.drawString(80, 70, prescription.doctor_notes[:90])
    pdf.drawRightString(width-40, 45, f"Generated {timezone.localtime().strftime('%d-%m-%Y %H:%M')}")
    pdf.showPage(); pdf.save()
    return response

@role_required("PATIENT")
def checkout(request, appointment_id):
    invoice = get_object_or_404(Invoice.objects.select_related("appointment"), appointment_id=appointment_id, appointment__patient=request.user)
    form = PaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        invoice.mark_paid(form.cleaned_data["transaction_ref"])
        messages.success(request, "Payment completed successfully in mock checkout.")
        return redirect("invoice", appointment_id=appointment_id)
    return render(request, "core/checkout.html", {"invoice": invoice, "form": form})

@role_required("PATIENT")
def invoice(request, appointment_id):
    invoice = get_object_or_404(Invoice.objects.select_related("appointment__patient", "appointment__doctor__doctor_profile"), appointment_id=appointment_id, appointment__patient=request.user)
    return render(request, "core/invoice.html", {"invoice": invoice})
