from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.forms import inlineformset_factory
from django.utils import timezone
from .models import CustomUser, PatientProfile, DoctorProfile, Appointment, Prescription, PrescriptionItem, Invoice


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=20)
    dob = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    class Meta:
        model = CustomUser
        fields = ("username", "email", "first_name", "last_name", "phone", "dob", "password1", "password2")

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.phone = self.cleaned_data["phone"]
        user.role = CustomUser.Role.PATIENT
        if commit:
            user.save()
            PatientProfile.objects.create(user=user, dob=self.cleaned_data.get("dob"))
        return user


class DoctorRegistrationForm(RegistrationForm):
    specialization = forms.CharField(max_length=100)
    license_number = forms.CharField(max_length=50)
    consultation_fee = forms.DecimalField(min_value=0)

    @transaction.atomic
    def save(self, commit=True):
        user = super(RegistrationForm, self).save(commit=False)
        # Admin-created doctor accounts are normally used; public registration remains patient-only.
        user.role = CustomUser.Role.DOCTOR
        user.save()
        DoctorProfile.objects.create(user=user, specialization=self.cleaned_data["specialization"],
            license_number=self.cleaned_data["license_number"], consultation_fee=self.cleaned_data["consultation_fee"])
        return user


class BookingForm(forms.ModelForm):
    doctor = forms.ModelChoiceField(queryset=CustomUser.objects.filter(role="DOCTOR", is_active=True))
    scheduled_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))

    class Meta:
        model = Appointment
        fields = ("doctor", "scheduled_at", "reason")

    def clean_scheduled_at(self):
        scheduled_at = self.cleaned_data["scheduled_at"]
        if timezone.is_naive(scheduled_at):
            scheduled_at = timezone.make_aware(scheduled_at, timezone.get_current_timezone())
        if scheduled_at <= timezone.now():
            raise forms.ValidationError("Choose a future date and time.")
        return scheduled_at


class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ("diagnosis", "doctor_notes", "follow_up_date")
        widgets = {"diagnosis": forms.Textarea(attrs={"rows": 3}),
                   "doctor_notes": forms.Textarea(attrs={"rows": 3}),
                   "follow_up_date": forms.DateInput(attrs={"type": "date"})}


PrescriptionItemFormSet = inlineformset_factory(
    Prescription, PrescriptionItem, fields=("medicine_name", "dosage", "frequency", "duration", "instructions"),
    extra=1, can_delete=True, min_num=1, validate_min=True,
)


class PaymentForm(forms.Form):
    transaction_ref = forms.CharField(max_length=100, help_text="Enter a mock/reference payment ID, for example MOCK-12345")
