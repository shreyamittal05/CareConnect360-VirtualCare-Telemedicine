import secrets
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        PATIENT = "PATIENT", "Patient"
        DOCTOR = "DOCTOR", "Doctor"
        ADMIN = "ADMIN", "Administrator"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.PATIENT)
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    def clean(self):
        if self.role == self.Role.ADMIN:
            self.is_staff = True


class PatientProfile(models.Model):
    BLOOD_GROUPS = [(x, x) for x in ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")]
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="patient_profile")
    dob = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUPS, blank=True)
    allergies = models.TextField(blank=True)
    medical_history = models.TextField(blank=True)

    def __str__(self):
        return f"Patient profile - {self.user.get_full_name() or self.user.username}"


class DoctorProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="doctor_profile")
    specialization = models.CharField(max_length=100)
    license_number = models.CharField(max_length=50, unique=True)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=500)
    years_of_experience = models.PositiveSmallIntegerField(default=0)
    bio = models.TextField(blank=True)

    def __str__(self):
        return f"Dr. {self.user.get_full_name()} - {self.specialization}"


class Appointment(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        SCHEDULED = "SCHEDULED", "Scheduled"
        ACCEPTED = "ACCEPTED", "Accepted"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        REJECTED = "REJECTED", "Rejected"

    patient = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name="patient_appointments", limit_choices_to={"role": "PATIENT"})
    doctor = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name="doctor_appointments", limit_choices_to={"role": "DOCTOR"})
    scheduled_at = models.DateTimeField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    room_id = models.CharField(max_length=80, unique=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_at"]
        constraints = [models.UniqueConstraint(fields=["doctor", "scheduled_at"], name="unique_doctor_slot")]

    def save(self, *args, **kwargs):
        if not self.room_id:
            self.room_id = f"CareConnect360-{secrets.token_urlsafe(24)}"
        super().save(*args, **kwargs)

    def clean(self):
        if self.scheduled_at and self.scheduled_at <= timezone.now():
            raise ValidationError("Appointment time must be in the future.")

    def __str__(self):
        return f"{self.patient} with {self.doctor} at {self.scheduled_at}"


class Prescription(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.PROTECT, related_name="prescription")
    diagnosis = models.TextField()
    doctor_notes = models.TextField(blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Prescription #{self.pk}"


class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name="items")
    medicine_name = models.CharField(max_length=150)
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)
    duration = models.CharField(max_length=100)
    instructions = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.medicine_name


class Invoice(models.Model):
    class Status(models.TextChoices):
        UNPAID = "UNPAID", "Unpaid"
        PAID = "PAID", "Paid"
        REFUNDED = "REFUNDED", "Refunded"

    appointment = models.OneToOneField(Appointment, on_delete=models.PROTECT, related_name="invoice")
    invoice_number = models.CharField(max_length=30, unique=True, editable=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UNPAID)
    transaction_ref = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = f"INV-{timezone.now():%Y%m%d}-{secrets.token_hex(4).upper()}"
        if not self.amount:
            self.amount = self.appointment.doctor.doctor_profile.consultation_fee
        super().save(*args, **kwargs)

    def mark_paid(self, reference):
        self.status = self.Status.PAID
        self.transaction_ref = reference
        self.paid_at = timezone.now()
        self.save(update_fields=["status", "transaction_ref", "paid_at"])
