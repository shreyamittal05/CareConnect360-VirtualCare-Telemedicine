from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, PatientProfile, DoctorProfile, Appointment, Prescription, PrescriptionItem, Invoice

class PatientProfileInline(admin.StackedInline):
    model = PatientProfile
    can_delete = False


class DoctorProfileInline(admin.StackedInline):
    model = DoctorProfile
    can_delete = False


class PrescriptionItemInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 1

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = UserAdmin.fieldsets + (("CareConnect Role", {"fields": ("role", "phone", "date_of_birth")}),)
    inlines = [PatientProfileInline, DoctorProfileInline]

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "doctor", "scheduled_at", "status", "room_id")
    list_filter = ("status", "scheduled_at")
    search_fields = ("patient__username", "doctor__username")
    date_hierarchy = "scheduled_at"

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "appointment", "created_at")
    inlines = [PrescriptionItemInline]

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "appointment", "amount", "status", "paid_at")
    list_filter = ("status",)
    search_fields = ("invoice_number", "transaction_ref")

admin.site.register(PatientProfile)
admin.site.register(DoctorProfile)
