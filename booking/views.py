from datetime import timedelta
from functools import wraps

from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Appointment, Doctor, Slot, Specialty
from .serializers import (
    AvailabilitySerializer, BookSerializer, CompleteSerializer, DoctorSerializer,
    SlotSerializer, SpecialtySerializer,
)

Status = Appointment.Status


def role(user):
    if not user.is_authenticated:
        return None
    if user.is_staff or user.is_superuser:
        return "admin"
    return "doctor" if hasattr(user, "doctor") else "patient"


def require_role(expected):
    def decorator(view):
        @wraps(view)
        def checked(request, *args, **kwargs):
            if role(request.user) != expected:
                return Response({"detail": f"Only {expected}s can use this endpoint."}, status=403)
            return view(request, *args, **kwargs)
        return checked
    return decorator


@ensure_csrf_cookie
def home(request):
    return render(request, "booking/index.html")


@api_view(["GET"])
@permission_classes([AllowAny])
def session(request):
    return Response({"role": role(request.user), "username": request.user.get_username() or None})


@api_view(["POST"])
@permission_classes([AllowAny])
def auth(request, action):
    # The page shell issues the CSRF cookie. Validate it even before login.
    SessionAuthentication().enforce_csrf(request)

    if action == "logout":
        logout(request)
        return Response({"role": None})
    if action not in {"login", "register"}:
        return Response({"detail": "Unknown action."}, status=404)
    if request.user.is_authenticated:
        return Response({"detail": "Sign out before switching accounts."}, status=409)

    if action == "register":
        form = UserCreationForm(data=request.data)
    else:
        form = AuthenticationForm(request, data=request.data)
    if not form.is_valid():
        return Response(form.errors.get_json_data(), status=400)
    try:
        user = form.save() if action == "register" else form.get_user()
    except IntegrityError:
        return Response({"detail": "This username is already in use."}, status=409)
    login(request, user)
    return Response({"role": role(user), "username": user.username}, status=201 if action == "register" else 200)


@api_view(["GET"])
@permission_classes([AllowAny])
def directory(request):
    if role(request.user) in {"doctor", "admin"}:
        return Response({"detail": "The booking directory is for patients."}, status=403)
    doctors = Doctor.objects.filter(account__is_active=True).select_related("specialty")
    if "specialty" in request.query_params:
        try:
            specialty = int(request.query_params["specialty"])
        except ValueError:
            return Response({"detail": "Choose a valid specialty."}, status=400)
        doctors = doctors.filter(specialty_id=specialty)
    return Response({
        "specialties": SpecialtySerializer(Specialty.objects.all(), many=True).data,
        "doctors": DoctorSerializer(doctors, many=True).data,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def availability(request):
    if role(request.user) in {"doctor", "admin"}:
        return Response({"detail": "The booking calendar is for patients."}, status=403)
    form = AvailabilitySerializer(data=request.query_params)
    form.is_valid(raise_exception=True)
    now = timezone.localtime()
    occupied = Appointment.objects.filter(slot=OuterRef("pk")).exclude(status=Status.CANCELLED)
    slots = Slot.objects.filter(
        doctor_id=form.validated_data["doctor"], date=form.validated_data["date"], doctor__account__is_active=True,
    ).filter(
        Q(date__gt=now.date()) | Q(date=now.date(), start_time__gt=now.time()),
    ).filter(~Exists(occupied))
    return Response(SlotSerializer(slots, many=True).data)


@api_view(["GET", "POST"])
@require_role("doctor")
def doctor_slots(request):
    slots = request.user.doctor.slots
    if request.method == "GET":
        return Response(SlotSerializer(slots.all(), many=True).data)
    return save_slot(request, slots)


@transaction.atomic
def save_slot(request, slots, slot=None):
    form = SlotSerializer(slot, data=request.data)
    form.is_valid(raise_exception=True)
    data = form.validated_data
    candidate = Slot(doctor=request.user.doctor, **data)
    if candidate.end_time <= candidate.start_time:
        return Response({"detail": "End time must follow start time."}, status=400)
    if candidate.starts_at <= timezone.now():
        return Response({"detail": "Choose a start time in the future."}, status=400)
    overlaps = slots.filter(
        date=candidate.date, start_time__lt=candidate.end_time, end_time__gt=candidate.start_time,
    )
    if slot:
        overlaps = overlaps.exclude(pk=slot.pk)
    if overlaps.exists():
        return Response({"detail": "This overlaps another slot on that date."}, status=409)
    record = form.save(doctor=request.user.doctor)
    return Response(SlotSerializer(record).data, status=200 if slot else 201)


@api_view(["PUT", "DELETE"])
@require_role("doctor")
@transaction.atomic
def doctor_slot(request, pk):
    slots = request.user.doctor.slots
    slot = get_object_or_404(slots, pk=pk)
    if slot.appointments.exists():
        return Response({"detail": "Slots with an appointment history are kept for the record."}, status=409)
    if request.method == "DELETE":
        slot.delete()
        return Response(status=204)
    return save_slot(request, slots, slot)


@api_view(["POST"])
@require_role("patient")
def book(request):
    form = BookSerializer(data=request.data)
    form.is_valid(raise_exception=True)
    try:
        with transaction.atomic():
            slot = get_object_or_404(Slot.objects.select_related("doctor__account"),
                                     pk=form.validated_data["slot"], doctor__account__is_active=True)
            if slot.starts_at <= timezone.now():
                return Response({"detail": "This slot has already started."}, status=409)
            if slot.appointments.exclude(status=Status.CANCELLED).exists():
                return Response({"detail": "This slot has already been booked."}, status=409)
            if request.user.appointments.filter(date=slot.date, start_time=slot.start_time).exclude(
                status=Status.CANCELLED,
            ).exists():
                return Response({"detail": "You already have an appointment at that time."}, status=409)
            visit = Appointment.objects.create(
                patient=request.user, slot=slot, date=slot.date, start_time=slot.start_time,
                reason=form.validated_data["reason"],
            )
    except IntegrityError:
        return Response({"detail": "The slot or appointment time was already taken."}, status=409)
    return Response({"id": visit.pk, "status": visit.status}, status=201)


@api_view(["POST"])
@require_role("patient")
@transaction.atomic
def cancel(request, pk):
    visit = get_object_or_404(request.user.appointments.select_related("slot"), pk=pk)
    if visit.status != Status.BOOKED:
        return Response({"detail": "Only booked appointments can be cancelled."}, status=409)
    if visit.slot.starts_at - timezone.now() < timedelta(hours=2):
        return Response({"detail": "Cancellation closes two hours before the appointment."}, status=409)
    visit.status = Status.CANCELLED
    visit.save(update_fields=["status"])
    return Response({"status": visit.status})


@api_view(["POST"])
@require_role("doctor")
@transaction.atomic
def complete(request, pk):
    form = CompleteSerializer(data=request.data)
    form.is_valid(raise_exception=True)
    visit = get_object_or_404(Appointment.objects.select_related("slot"), pk=pk, slot__doctor=request.user.doctor)
    if visit.status != Status.BOOKED or visit.slot.starts_at > timezone.now():
        return Response({"detail": "Only booked appointments that have started can be completed."}, status=409)
    visit.status = Status.COMPLETED
    visit.notes = form.validated_data["notes"]
    visit.save(update_fields=["status", "notes"])
    return Response({"status": visit.status})


@api_view(["GET"])
def dashboard(request):
    user_role = role(request.user)
    visits = Appointment.objects.select_related("slot__doctor__specialty", "patient")
    if user_role == "patient":
        visits = visits.filter(patient=request.user)
    elif user_role == "doctor":
        visits = visits.filter(slot__doctor=request.user.doctor)
    else:
        return Response({"detail": "Use Django Admin to review records."}, status=403)

    now = timezone.localtime()
    sections = {"upcoming": [], "past": []} if user_role == "patient" else {"today": [], "upcoming": [], "past": []}
    completed = 0
    for visit in visits:
        start = visit.slot.starts_at
        completed += visit.status == Status.COMPLETED
        if user_role == "doctor" and visit.date == now.date():
            section = "today"
        elif visit.status == Status.BOOKED and start >= now:
            section = "upcoming"
        else:
            section = "past"
        sections[section].append({
            "id": visit.pk, "doctor": visit.slot.doctor.name, "specialty": visit.slot.doctor.specialty.name,
            "patient": visit.patient.get_full_name() or visit.patient.username,
            "date": visit.date.isoformat(), "start_time": visit.start_time.isoformat(),
            "end_time": visit.slot.end_time.isoformat(), "status": visit.status,
            "reason": visit.reason, "notes": visit.notes,
            "can_cancel": user_role == "patient" and visit.status == Status.BOOKED
            and start - now >= timedelta(hours=2),
            "can_complete": user_role == "doctor" and visit.status == Status.BOOKED and start <= now,
        })
    return Response({"sections": sections, "completed": completed})
