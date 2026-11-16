from django.contrib import admin

from .models import Appointment, Doctor, Slot, Specialty

admin.site.site_header = "Hospital Appointment Admin"
admin.site.register(Specialty)


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ["name", "specialty", "account", "experience", "fee"]
    list_filter = ["specialty"]
    search_fields = ["name", "account__username"]

    def get_readonly_fields(self, request, obj=None):
        return ["account"] if obj else []


class ScheduleAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Slot)
class SlotAdmin(ScheduleAdmin):
    list_display = ["doctor", "date", "start_time", "end_time", "withdrawn_at"]
    list_filter = ["doctor", "date"]


@admin.register(Appointment)
class AppointmentAdmin(ScheduleAdmin):
    list_display = ["patient", "slot", "status"]
    list_filter = ["status", "date"]
