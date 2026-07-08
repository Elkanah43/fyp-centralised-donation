import json
import logging
from datetime import date, time
from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .models import Alert, Appointment, Donor, InventoryItem, RecipientCase

logger = logging.getLogger(__name__)

BLOOD_TYPES = {choice[0] for choice in Donor.BLOOD_TYPES}
DONOR_TYPES = {choice[0] for choice in Donor.DONOR_TYPES}
DONOR_STATUSES = {choice[0] for choice in Donor.STATUSES}
PRIORITIES = {choice[0] for choice in RecipientCase.PRIORITIES}
NEED_TYPES = {choice[0] for choice in RecipientCase.NEED_TYPES}
ALERT_LEVELS = {choice[0] for choice in Alert.LEVELS}
ORGANS = {"Kidney", "Liver", "Heart", "Cornea"}

INITIAL_INVENTORY = {
    "O-": 8,
    "O+": 28,
    "A-": 9,
    "A+": 31,
    "B-": 6,
    "B+": 16,
    "AB-": 4,
    "AB+": 11,
}


class ValidationError(Exception):
    def __init__(self, errors):
        self.errors = errors if isinstance(errors, dict) else {"detail": str(errors)}


def parse_body(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValidationError({"detail": "Request body must be valid JSON."})
    if not isinstance(payload, dict):
        raise ValidationError({"detail": "Request body must be a JSON object."})
    return payload


def clean_text(payload, field, *, max_length, required=True):
    value = str(payload.get(field, "") or "").strip()
    if required and not value:
        raise ValidationError({field: "This field is required."})
    if len(value) > max_length:
        raise ValidationError({field: f"Must be {max_length} characters or fewer."})
    return value


def clean_choice(payload, field, choices, *, default=None):
    value = payload.get(field, default)
    if value not in choices:
        raise ValidationError({field: f"Must be one of: {', '.join(sorted(choices))}."})
    return value


def error_response(exc):
    return JsonResponse({"errors": exc.errors}, status=400)


def api_login_required(view):
    """Like login_required, but returns a JSON 401 instead of a redirect."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"errors": {"detail": "Authentication required."}}, status=401)
        return view(request, *args, **kwargs)

    return wrapper


@login_required
@ensure_csrf_cookie
def home_view(request):
    return render(request, "index.html")


def robots_view(request):
    return render(request, "robots.txt", content_type="text/plain")


def sitemap_view(request):
    return render(request, "sitemap.xml", content_type="application/xml")


def ensure_seed_data():
    if not settings.DEMO_MODE:
        return
    if Donor.objects.exists() or RecipientCase.objects.exists() or Alert.objects.exists():
        return

    donor_seed = [
        {
            "name": "Amina Mensah",
            "donor_type": "Blood + Organ",
            "blood_type": "O-",
            "region": "Greater Accra",
            "phone": "+233 55 100 4102",
            "organs": ["Kidney", "Cornea"],
            "status": "Available",
        },
        {
            "name": "Kwame Owusu",
            "donor_type": "Blood",
            "blood_type": "A+",
            "region": "Ashanti",
            "phone": "+233 24 889 1200",
            "organs": [],
            "status": "Available",
        },
        {
            "name": "Nadia Boateng",
            "donor_type": "Organ",
            "blood_type": "B+",
            "region": "Greater Accra",
            "phone": "+233 20 541 7788",
            "organs": ["Liver"],
            "status": "Contacted",
        },
        {
            "name": "Joseph Tetteh",
            "donor_type": "Blood + Organ",
            "blood_type": "AB-",
            "region": "Central",
            "phone": "+233 59 211 0443",
            "organs": ["Heart", "Kidney"],
            "status": "Available",
        },
    ]

    for donor_data in donor_seed:
        Donor.objects.create(**donor_data)

    RecipientCase.objects.create(
        recipient="Kojo Baah",
        need_type="Organ",
        priority="Critical",
        blood_type="O+",
        organ="Kidney",
        hospital="Korle Bu Teaching Hospital",
        region="Greater Accra",
    )
    RecipientCase.objects.create(
        recipient="Grace Tano",
        need_type="Blood",
        priority="High",
        blood_type="B+",
        organ="",
        hospital="Komfo Anokye Teaching Hospital",
        region="Ashanti",
    )
    Alert.objects.create(
        level="Critical",
        title="Kidney case needs O+ compatible donor",
        message="Korle Bu requested accelerated matching for Kojo Baah.",
    )
    Alert.objects.create(
        level="Notice",
        title="AB- blood stock below reserve",
        message="Only 4 units available nationally in the demo inventory.",
    )

    for blood_type, units in INITIAL_INVENTORY.items():
        InventoryItem.objects.get_or_create(blood_type=blood_type, defaults={"units": units})


def serialize_donor(donor):
    return {
        "id": str(donor.id),
        "name": donor.name,
        "type": donor.donor_type,
        "bloodType": donor.blood_type,
        "region": donor.region,
        "phone": donor.phone,
        "organs": donor.organs or [],
        "status": donor.status,
    }


def serialize_case(case):
    return {
        "id": str(case.id),
        "recipient": case.recipient,
        "needType": case.need_type,
        "priority": case.priority,
        "bloodType": case.blood_type,
        "organ": case.organ,
        "hospital": case.hospital,
        "region": case.region,
        "createdAt": case.created_at.date().isoformat(),
    }


def serialize_appointment(appointment):
    return {
        "id": str(appointment.id),
        "donorId": str(appointment.donor_id),
        "date": appointment.date.isoformat(),
        "time": appointment.time.strftime("%H:%M"),
        "site": appointment.site,
        "purpose": appointment.purpose,
    }


def serialize_alert(alert):
    return {
        "id": str(alert.id),
        "level": alert.level,
        "title": alert.title,
        "message": alert.message,
    }


def serialize_inventory():
    return {item.blood_type: item.units for item in InventoryItem.objects.order_by("blood_type")}


def build_state_payload():
    ensure_seed_data()
    return {
        "donors": [serialize_donor(d) for d in Donor.objects.order_by("-created_at", "-id")],
        "cases": [serialize_case(c) for c in RecipientCase.objects.order_by("-created_at", "-id")],
        "inventory": serialize_inventory(),
        "appointments": [
            serialize_appointment(a)
            for a in Appointment.objects.select_related("donor").order_by("date", "time")
        ],
        "alerts": [serialize_alert(a) for a in Alert.objects.order_by("-created_at", "-id")],
        "demoMode": settings.DEMO_MODE,
    }


@never_cache
@require_http_methods(["GET"])
@api_login_required
def api_state(request):
    return JsonResponse(build_state_payload())


@require_http_methods(["POST"])
@api_login_required
def api_donors(request):
    try:
        payload = parse_body(request)
        organs = payload.get("organs", [])
        if not isinstance(organs, list) or not set(organs).issubset(ORGANS):
            raise ValidationError({"organs": f"Must be a list drawn from: {', '.join(sorted(ORGANS))}."})
        donor = Donor.objects.create(
            name=clean_text(payload, "name", max_length=200),
            donor_type=clean_choice(payload, "donor_type", DONOR_TYPES, default="Blood"),
            blood_type=clean_choice(payload, "blood_type", BLOOD_TYPES),
            region=clean_text(payload, "region", max_length=120),
            phone=clean_text(payload, "phone", max_length=30),
            organs=organs,
            status=clean_choice(payload, "status", DONOR_STATUSES, default="Available"),
        )
    except ValidationError as exc:
        return error_response(exc)
    return JsonResponse(serialize_donor(donor), status=201)


@require_http_methods(["POST"])
@api_login_required
def api_cases(request):
    try:
        payload = parse_body(request)
        need_type = clean_choice(payload, "need_type", NEED_TYPES, default="Blood")
        organ = ""
        if need_type == "Organ":
            organ = clean_choice(payload, "organ", ORGANS)
        priority = clean_choice(payload, "priority", PRIORITIES, default="Standard")
        with transaction.atomic():
            case = RecipientCase.objects.create(
                recipient=clean_text(payload, "recipient", max_length=200),
                need_type=need_type,
                priority=priority,
                blood_type=clean_choice(payload, "blood_type", BLOOD_TYPES),
                organ=organ,
                hospital=clean_text(payload, "hospital", max_length=200),
                region=clean_text(payload, "region", max_length=120),
            )
            alert = Alert.objects.create(
                level="Critical" if priority == "Critical" else "Notice",
                title=f"{priority} {need_type.lower()} case created",
                message=f"{case.recipient} was added from {case.hospital}.",
            )
    except ValidationError as exc:
        return error_response(exc)
    return JsonResponse({"case": serialize_case(case), "alert": serialize_alert(alert)}, status=201)


@require_http_methods(["POST"])
@api_login_required
def api_appointments(request):
    try:
        payload = parse_body(request)
        donor_id = payload.get("donorId") or payload.get("donor_id")
        if not donor_id:
            raise ValidationError({"donorId": "This field is required."})
        try:
            donor = Donor.objects.get(id=donor_id)
        except (Donor.DoesNotExist, ValueError):
            raise ValidationError({"donorId": "No donor found with this id."})
        try:
            appointment_date = date.fromisoformat(str(payload.get("date", "")))
        except ValueError:
            raise ValidationError({"date": "Must be a valid date in YYYY-MM-DD format."})
        if appointment_date < date.today():
            raise ValidationError({"date": "Appointment date cannot be in the past."})
        try:
            appointment_time = time.fromisoformat(str(payload.get("time", "")))
        except ValueError:
            raise ValidationError({"time": "Must be a valid time in HH:MM format."})
        appointment = Appointment.objects.create(
            donor=donor,
            date=appointment_date,
            time=appointment_time,
            site=clean_text(payload, "site", max_length=200),
            purpose=clean_text(payload, "purpose", max_length=80),
        )
    except ValidationError as exc:
        return error_response(exc)
    return JsonResponse(serialize_appointment(appointment), status=201)


@require_http_methods(["POST"])
@api_login_required
def api_inventory(request):
    try:
        payload = parse_body(request)
        blood_type = clean_choice(payload, "blood_type", BLOOD_TYPES)
        try:
            delta = int(payload.get("delta", 0))
        except (TypeError, ValueError):
            raise ValidationError({"delta": "Must be an integer."})
        if abs(delta) > 1000:
            raise ValidationError({"delta": "Adjustment too large."})
        with transaction.atomic():
            item, _ = InventoryItem.objects.select_for_update().get_or_create(
                blood_type=blood_type, defaults={"units": 0}
            )
            item.units = max(0, item.units + delta)
            item.save(update_fields=["units"])
    except ValidationError as exc:
        return error_response(exc)
    return JsonResponse({"inventory": serialize_inventory()})


@require_http_methods(["POST"])
@api_login_required
def api_alerts(request):
    try:
        payload = parse_body(request)
        alert = Alert.objects.create(
            level=clean_choice(payload, "level", ALERT_LEVELS, default="Notice"),
            title=clean_text(payload, "title", max_length=200),
            message=clean_text(payload, "message", max_length=2000),
        )
    except ValidationError as exc:
        return error_response(exc)
    return JsonResponse(serialize_alert(alert), status=201)


@require_http_methods(["POST"])
@api_login_required
def api_reset(request):
    if not settings.DEMO_MODE:
        return JsonResponse({"errors": {"detail": "Reset is disabled outside demo mode."}}, status=403)
    with transaction.atomic():
        Appointment.objects.all().delete()
        Donor.objects.all().delete()
        RecipientCase.objects.all().delete()
        InventoryItem.objects.all().delete()
        Alert.objects.all().delete()
        ensure_seed_data()
    return JsonResponse(build_state_payload())
