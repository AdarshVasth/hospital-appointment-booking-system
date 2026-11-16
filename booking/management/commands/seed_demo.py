from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from booking.models import Doctor, Slot, Specialty


class Command(BaseCommand):
    help = "Add fictional doctors, a patient and future slots to a local demo database."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        password = "ClearwayDemo!26"
        patient, created = User.objects.get_or_create(username="demo_patient")
        if created:
            patient.set_password(password)
            patient.save(update_fields=["password"])

        profiles = [
            ("demo_cardio", "Dr. Ananya Rao", "Cardiology", 12, "850.00",
             "Consultations for heart health, blood pressure, and follow-up care."),
            ("demo_skin", "Dr. Neel Sharma", "Dermatology", 8, "650.00",
             "Consultations for skin, hair, and nail concerns."),
            ("demo_child", "Dr. Meera Iyer", "Pediatrics", 10, "750.00",
             "Routine checkups and pediatric consultations for children and adolescents."),
        ]
        profiles.extend([
            ("demo_ortho", "Dr. Rohan Kapoor", "Orthopedics", 11, "900.00",
             "Bone, joint and sports injury consultations."),
            ("demo_neuro", "Dr. Kavya Menon", "Neurology", 14, "1200.00",
             "Headache, nerve and neurological care."),
            ("demo_ent", "Dr. Arjun Nair", "ENT", 9, "700.00",
             "Ear, nose, throat and sinus consultations."),
            ("demo_general", "Dr. Priya Shah", "General Medicine", 7, "500.00",
             "Preventive health, fever and routine consultations."),
        ])
        for username, name, specialty_name, experience, fee, bio in profiles:
            account, created = User.objects.get_or_create(username=username)
            if created:
                account.set_password(password)
                account.save(update_fields=["password"])
            specialty, _ = Specialty.objects.get_or_create(name=specialty_name)
            doctor, _ = Doctor.objects.get_or_create(account=account, defaults={
                "name": name, "specialty": specialty, "experience": experience, "fee": fee, "bio": bio,
            })
            for offset in range(0, 15):
                date = timezone.localdate() + timedelta(days=offset)
                for hour in (9, 10, 11, 14, 15, 16, 17):
                    start, end = time(hour), time(hour, 30)
                    candidate = Slot(doctor=doctor, date=date, start_time=start, end_time=end)
                    if candidate.starts_at <= timezone.now():
                        continue
                    if not doctor.slots.filter(date=date, start_time__lt=end, end_time__gt=start, withdrawn_at__isnull=True).exists():
                        candidate.save()
        self.stdout.write(self.style.SUCCESS("Demo ready. Sign in as demo_patient or demo_cardio with ClearwayDemo!26"))
