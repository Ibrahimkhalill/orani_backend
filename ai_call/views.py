from django.utils.dateparse import parse_datetime
from .models import Call, PhoneNumber
from rest_framework.decorators import api_view
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
# Create your views here.
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from orani_main.utils import error_response
from .models import PhoneNumber
import random
from twilio.rest import Client
import os
TWILIO_ACCOUNT_SID = os.getenv("ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("PHONE_NUMBER")


client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_virtual_numbers(request):
    # Fetch 4 available Twilio numbers
    numbers = client.available_phone_numbers("US").local.list(
        sms_enabled=True,
        voice_enabled=True,
        limit=4
    )

    # Get phone numbers already saved in the DB
    existing_numbers = PhoneNumber.objects.values_list(
        "phone_number", flat=True)

    # Filter out numbers that are already in DB
    available_numbers = [
        n.phone_number for n in numbers if n.phone_number not in existing_numbers]

    if not available_numbers:
        return error_response("No new available numbers found", status=404)

    # Shuffle the list randomly
    random.shuffle(available_numbers)

    return Response(available_numbers, status=200)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def save_phone_number(request):
    user = request.user
    phone_number = request.data.get("phone_number")

    if not phone_number:
        return error_response("phone_number are required", status=400)

    # Check if this number already exists
    if PhoneNumber.objects.filter(phone_number=phone_number).exists():
        return error_response("This phone number is already saved", status=400)

    PhoneNumber.objects.create(
        user=user,
        phone_number=phone_number,
        is_active=True
    )

    return Response({"message": "Phone number saved successfully"}, status=201)


# views.py


def log_incoming_call(data):
    call_id = data.get("CallSid")
    to_number = data.get("To")
    from_number = data.get("From")
    status = data.get("CallStatus")
    started_at = parse_datetime(
        data.get("StartTime")) if data.get("StartTime") else None
    ended_at = parse_datetime(
        data.get("EndTime")) if data.get("EndTime") else None

    phone_obj = PhoneNumber.objects.filter(phone_number=to_number).first()
    if not phone_obj:
        return None

    call, created = Call.objects.get_or_create(
        call_id=call_id,
        defaults={
            "user": phone_obj.user,
            "caller_phone": from_number,
            "status": status,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration": 0
        }
    )

    if not created:
        call.status = status
        call.ended_at = ended_at
        call.save()

    return call


@api_view(["POST"])
def twilio_incoming_call(request):
    # Twilio sends POST data
    data = request.data
    call = log_incoming_call(data)
    if call:
        return Response({"message": "Call logged"}, status=200)
    else:
        return Response({"error": "Number not found"}, status=404)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_call_logs(request):
    user = request.user

    calls = Call.objects.filter(user=user).order_by(
        '-started_at')  # latest first
    call_list = []

    for c in calls:
        call_list.append({
            "call_id": c.call_id,
            "caller_phone": c.caller_phone,
            "status": c.status,  # 'started', 'in_progress', 'completed', 'failed'
            "started_at": c.started_at,
            "ended_at": c.ended_at,
            "duration": c.duration,
            # simple example
            "type": "incoming" if c.status in ['started', 'in_progress', 'completed'] else "outgoing"
        })

    phone = PhoneNumber.objects.filter(user=user).first()

    return Response({
        "phone_number": phone.phone_number if phone else None,
        "total_calls": calls.count(),
        "answered_calls": calls.filter(status='completed').count(),
        "calls": call_list
    })
