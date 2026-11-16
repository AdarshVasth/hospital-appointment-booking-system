from datetime import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone


class Specialty(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "specialties"

    def __str__(self):
        return self.name


class Doctor(models.Model):
    account = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="doctor")
    name = models.CharField(max_length=120)
    specialty = models.ForeignKey(Specialty, on_delete=models.PROTECT)
    experience = models.PositiveSmallIntegerField(help_text="Years of experience")
    fee = models.DecimalField(max_digits=8, decimal_places=2)
    bio = models.CharField(max_length=500)

    class Meta:
        ordering = ["name"]
        constraints = [models.CheckConstraint(condition=models.Q(fee__gte=0), name="nonnegative_fee")]

    def __str__(self):
        return self.name


class Slot(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name="slots")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["date", "start_time", "id"]
        indexes = [models.Index(fields=["doctor", "date", "start_time"])]
        constraints = [models.CheckConstraint(
            condition=models.Q(end_time__gt=models.F("start_time")), name="slot_end_after_start",
        )]

    @property
    def starts_at(self):
        return timezone.make_aware(datetime.combine(self.date, self.start_time))

    def __str__(self):
        return f"{self.doctor} · {self.date} · {self.start_time:%H:%M}"


class Appointment(models.Model):
    class Status(models.TextChoices):
        BOOKED = "booked", "Booked"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    slot = models.ForeignKey(Slot, on_delete=models.PROTECT, related_name="appointments")
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="appointments")
    date = models.DateField(editable=False)
    start_time = models.TimeField(editable=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.BOOKED)
    reason = models.CharField(max_length=500)
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["date", "start_time", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["slot"], condition=~models.Q(status="cancelled"), name="one_visit_per_slot",
            ),
            models.UniqueConstraint(
                fields=["patient", "date", "start_time"],
                condition=~models.Q(status="cancelled"), name="one_visit_per_patient_start",
            ),
        ]

    def __str__(self):
        return f"{self.patient} · {self.slot} · {self.get_status_display()}"
