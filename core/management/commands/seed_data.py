from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.models import DoctorProfile, PatientProfile, Appointment, Invoice

class Command(BaseCommand):
    help = "Seed demo doctors, patients and future appointments"

    def handle(self, *args, **options):
        User = get_user_model()
        password = "Demo@123456"
        admin, _ = User.objects.get_or_create(username="admin", defaults={"email": "admin@careconnect360.local", "role": "ADMIN", "is_staff": True, "is_superuser": True})
        admin.set_password("Admin@123456"); admin.role = "ADMIN"; admin.is_staff = True; admin.is_superuser = True; admin.save()
        doctors = []
        specs = [("dr.sharma", "Aarav", "Sharma", "Cardiology", "LIC-CARD-1001", 1200),
                 ("dr.patel", "Diya", "Patel", "Dermatology", "LIC-DERM-1002", 900),
                 ("dr.roy", "Kabir", "Roy", "General Medicine", "LIC-GEN-1003", 700)]
        for username, first, last, spec, license_no, fee in specs:
            u, created = User.objects.get_or_create(username=username, defaults={"first_name": first, "last_name": last, "email": f"{username}@careconnect360.local", "role": "DOCTOR"})
            u.role = "DOCTOR"; u.first_name = first; u.last_name = last; u.set_password(password); u.save()
            DoctorProfile.objects.update_or_create(user=u, defaults={"specialization": spec, "license_number": license_no, "consultation_fee": fee, "years_of_experience": 10})
            doctors.append(u)
        patient, _ = User.objects.get_or_create(username="patient1", defaults={"first_name": "Riya", "last_name": "Verma", "email": "riya@example.com", "role": "PATIENT"})
        patient.role = "PATIENT"; patient.first_name = "Riya"; patient.last_name = "Verma"; patient.set_password(password); patient.save()
        profile, _ = PatientProfile.objects.get_or_create(user=patient, defaults={"blood_group": "O+", "allergies": "Penicillin", "medical_history": "Seasonal asthma"})
        profile.save()
        for i, doctor in enumerate(doctors):
            slot = timezone.now() + timedelta(days=i + 1, hours=10)
            slot = slot.replace(minute=30, second=0, microsecond=0)
            appointment, created = Appointment.objects.get_or_create(patient=patient, doctor=doctor, scheduled_at=slot, defaults={"reason": "Virtual consultation", "status": "ACCEPTED" if i == 0 else "REQUESTED"})
            if not hasattr(appointment, "invoice"):
                Invoice.objects.create(appointment=appointment, amount=doctor.doctor_profile.consultation_fee)
        self.stdout.write(self.style.SUCCESS("Seed data created. Patient: patient1 / " + password + " | Doctor: dr.sharma / " + password))
