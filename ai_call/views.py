from django.utils.dateparse import parse_datetime
from .models import Call, PhoneNumber
from rest_framework.decorators import api_view
from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
# Create your views here.
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.password_validation import validate_password
from rest_framework import status
from .serializers import *
from orani_main.utils import error_response
from .models import PhoneNumber , CompanyInformation
from .serializers import *
import random
from twilio.rest import Client
from authentications.models import UserProfile
import os
from datetime import datetime
import pytz  # optional, for timezone conversion
import requests

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
        return error_response(code=404 , message="No new available numbers found")

    # Shuffle the list randomly
    random.shuffle(available_numbers)

    return Response(available_numbers, status=200)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_assigned_phone_number(request):
    """
    Return only the virtual number assigned to the logged-in user,
    along with call summary.
    """
    try:
        phone_number_obj = PhoneNumber.objects.get(user=request.user)
        serializer = PhoneNumberSerializer(phone_number_obj)

        summary = get_call_summary(
            client,
            phone_number=phone_number_obj.phone_number,
            user_timezone=getattr(request.user, "timezone", "UTC")
        )

        # Merge two dicts properly
        response_data = {**serializer.data, **summary}

        return Response(response_data, status=status.HTTP_200_OK)

    except PhoneNumber.DoesNotExist:
        return Response(
            {"detail": "No phone number assigned."},
            status=status.HTTP_404_NOT_FOUND
        )






@api_view(["POST"])
@permission_classes([IsAuthenticated])
def save_phone_number(request):
    user = request.user
    phone_number = request.data.get("phone_number")
    
    
    if PhoneNumber.objects.filter(user=user).exists():
        save_knowdege_data(request)
        return error_response(message=" phone number is already assign the user", code=200)

    
    # Step 2: Check if this number is already taken by another user
    if PhoneNumber.objects.filter(phone_number=phone_number).exclude(user=user).exists():
        return error_response(message="This phone number is already saved by another user", code=400)

    # Step 3: Save or update number for this user
    saved_number, created = PhoneNumber.objects.update_or_create(
        user=user,
        defaults={
            "phone_number": phone_number,
            "is_active": True
        }
    )

    # Step 4: Update Twilio webhooks
    try:
        client.incoming_phone_numbers.create(
            phone_number=phone_number,
            voice_url="https://api.vapi.ai/twilio/inbound_call",
            voice_method="POST",
            # Set status callback for call events
            status_callback="https://api.vapi.ai/twilio/call_status",
            status_callback_method="POST"
        )
        
      
    except Exception as e:
        print(e)
        saved_number.delete()
        return error_response(message="Failed to update Twilio webhooks", code=400)

    # Step 5: Mark onboarding as completed
    user_profile, _ = UserProfile.objects.get_or_create(user=user)
    user_profile.has_completed_onboarding = True
    user_profile.save()
    
    userProfileSerializer = userProfileSerializer(user_profile)
    
    save_knowdege_data(request)

    return Response(
        {
            "message": "Phone number saved (and purchased if needed) successfully",
            "phone_number": phone_number,
            "user_profile": userProfileSerializer.data
            
        },
        status=201
    )

def save_knowdege_data(request):
    # Your Twilio logic here

    # Instead of passing DRF Request, just pass user
    response_data = get_user_data_dict(request.user)
    
    print(json.dumps(response_data, default=str))


    # Post to other backend
    try:
        backend_url = "https://e177403aa007.ngrok-free.app/setup/assistant"
        headers = {"Content-Type": "application/json"}
        post_response = requests.post(backend_url, json=response_data, headers=headers)
        print("Other backend response:", post_response.status_code, post_response.text)
    except requests.exceptions.RequestException as e:
        print("Error posting data:", e)

    return Response(response_data)


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
        return error_response({"error": "Number not found"}, status=404)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_call_logs(request):
    user = request.user
    call_list = []
    phone = PhoneNumber.objects.filter(user=user).first()

    user_timezone = getattr(user, "timezone", "UTC")
    tz = pytz.timezone(user_timezone)
    incoming_calls = client.calls.list(to=phone.phone_number )
    outgoing_calls = client.calls.list(from_=phone.phone_number)
    all_calls = incoming_calls + outgoing_calls

    all_calls_sorted = sorted(
        all_calls,
        key=lambda c: c.start_time or datetime.min,
        reverse=True
    )

    for c in all_calls_sorted:
        start_time_str = str(c.start_time.astimezone(tz)) if c.start_time else None
        end_time_str = str(c.end_time.astimezone(tz)) if c.end_time else None

        call_list.append({
            "call_sid": c.sid,
            "from": c._from,
            "to": c.to,
            "status": c.status,
            "start_time": start_time_str,
            "end_time": end_time_str,
            "duration": c.duration,
            "type": "incoming" if c.direction == "inbound" else "outgoing"
        })

    

    return Response({
        "phone_number": phone.phone_number if phone else None,
        "total_calls": len(all_calls_sorted),
        "answered_calls": len([c for c in all_calls_sorted if c.status == "completed"]),
        "calls": call_list
    })
    
    
def get_call_summary(client, phone_number, user_timezone="UTC"):
    """
    Twilio call summary for a given phone number.
    """
    tz = pytz.timezone(user_timezone)

    # Twilio calls
    incoming_calls = client.calls.list(to=phone_number)
    outgoing_calls = client.calls.list(from_=phone_number)
    all_calls = incoming_calls + outgoing_calls

    # Sort by start_time (newest first)
    all_calls_sorted = sorted(
        all_calls,
        key=lambda c: c.start_time or datetime.min,
        reverse=True
    )

    incoming_count = 0
    outgoing_count = 0
    missed_count = 0
    received_count = 0

    # collect status counts
    status_list = []

    for c in all_calls_sorted:
        call_type = "incoming" if c.direction == "inbound" else "outgoing"

        status_list.append(c.status)

        if call_type == "incoming":
            incoming_count += 1
            if c.status == "completed":
                received_count += 1
                
        elif c.status in ["no-answer", "busy", "failed"]:
                print("yes i am im")
                missed_count += 1
        else:
            outgoing_count += 1

    # summary by status (completed, no-answer, busy, failed etc.)
    
        # print("status_list",status_list)
    return {
        "incoming_calls": incoming_count,
        "outgoing_calls": outgoing_count,
        "missed_calls": missed_count,
        "received_calls": received_count,
        "total_calls": len(all_calls_sorted),
        
    }

    
    

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def company_list_create(request):
    if request.method == 'GET':
        companies = CompanyInformation.objects.filter(user=request.user).first()
        serializer = CompanyInformationSerializer(companies)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        serializer = CompanyInformationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# -------------------------
# Retrieve, Update, Delete
# -------------------------
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def company_detail(request, pk):
    try:
        company = CompanyInformation.objects.get(pk=pk, user=request.user)
    except CompanyInformation.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = CompanyInformationSerializer(company)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = CompanyInformationSerializer(company, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            save_knowdege_data(request)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        company.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    
    

# -------- PriceInfo CRUD --------
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def price_info_list_create(request):
    if request.method == "GET":
        price_infos = PriceInfo.objects.filter(user=request.user)
        serializer = PriceInfoSerializer(price_infos, many=True)
        return Response(serializer.data)

    elif request.method == "POST":
        serializer = PriceInfoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            save_knowdege_data(request)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def price_info_detail(request, pk):
    try:
        price_info = PriceInfo.objects.get(pk=pk, user=request.user)
    except PriceInfo.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        serializer = PriceInfoSerializer(price_info)
        return Response(serializer.data)

    elif request.method in ["PUT", "PATCH"]:
        serializer = PriceInfoSerializer(price_info, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            save_knowdege_data(request)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        price_info.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_or_update_ai_assistant(request):
    """
    Create a new AIAssistant or update if it already exists for a user.
    """
    user_id = request.user.id
    if not user_id:
        return Response({"error": "User ID is required."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND)

    # Check if AIAssistant already exists
    try:
        assistant = AIAssistant.objects.get(user=user)
        serializer = AIAssistantSerializer(assistant, data=request.data, partial=True)
    except AIAssistant.DoesNotExist:
        serializer = AIAssistantSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save(user=user)
        save_knowdege_data(request)
        return Response(serializer.data, status=status.HTTP_200_OK)
    print(serializer.errors)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



# -------- BookingLink CRUD --------
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def booking_link_list_create(request):
    if request.method == "GET":
        booking_links = BookingLink.objects.filter(user=request.user)
        serializer = BookingLinkSerializer(booking_links, many=True)
        return Response(serializer.data)

    elif request.method == "POST":
        serializer = BookingLinkSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            save_knowdege_data(request)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        print("s", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def booking_link_detail(request, pk):
    try:
        booking_link = BookingLink.objects.get(pk=pk, user=request.user)
    except BookingLink.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        serializer = BookingLinkSerializer(booking_link)
        return Response(serializer.data)

    elif request.method in ["PUT", "PATCH"]:
        serializer = BookingLinkSerializer(booking_link, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            save_knowdege_data(request)
            return Response(serializer.data)
        
        print("serializer.errors",serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        booking_link.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)    
    
    


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_hours_of_operation(request):
    """
    List all hours of operation for the current user.
    """
    hours = HoursOfOperation.objects.filter(user=request.user)
    serializer = HoursOfOperationSerializer(hours, many=True)
    return Response(serializer.data)


@api_view(['POST', 'PUT'])
@permission_classes([IsAuthenticated])
def manage_hours_of_operation(request):
    """
    Create or update hours for multiple days at once.
    POST: create
    PUT: update
    """
    
    serializer = HoursOfOperationSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        obj = serializer.save()  # single object
        save_knowdege_data(request)
        return Response({
            "message": "Hours saved successfully",
            "days": obj.days  # obj.days is already a list
        }, status=200)
   
    return Response(serializer.errors, status=400)




from twilio.twiml.voice_response import VoiceResponse , Dial




@csrf_exempt
def voice_handler(request):
    to_number = request.POST.get("To")       # The number being called
    from_number = request.POST.get("From")   # The caller's number
    
    # Find the user associated with the 'from' number
    try:
        user_phone = PhoneNumber.objects.get(phone_number=from_number, is_active=True)
        user = user_phone.user
        print("Incoming call from user:", user.id, user.email ,user_phone.phone_number)
    except PhoneNumber.DoesNotExist:
        user = None
        print("No user found for number:", from_number)

    response = VoiceResponse()

    if to_number:
        # Dial external number using valid Twilio number as callerId
        dial = Dial(caller_id=user_phone.phone_number)
        dial.number(to_number)
        response.append(dial)
    else:
        # Default response
        response.say("Hello, your call is connected.")

    return HttpResponse(str(response), content_type="application/xml")


# views.py
from django.http import JsonResponse
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_twilio_token(request):
    api_key = "SK7b925482fcfcd3b522874477beef8566"           
    api_secret = "GIwbzhvPFoNCpaqD8s4KHsfvPYvnrUpS"       
    outgoing_app_sid = "APcc492ac8a5dbbecc470b9ebdb3e1e5ea"  
    identity = str(request.user.id) 


    # Create token
    token = AccessToken(TWILIO_ACCOUNT_SID, api_key, api_secret, identity=identity)
    voice_grant = VoiceGrant(
        outgoing_application_sid=outgoing_app_sid,
        incoming_allow=True
    )
    token.add_grant(voice_grant)


    # In Python 3, to_jwt() returns a string
    return JsonResponse({"token": token.to_jwt(), "identity": identity})





def get_user_data_dict(user):
    company_info = CompanyInformation.objects.filter(user=user).first()
    price_info = PriceInfo.objects.filter(user=user)
    booking_links = BookingLink.objects.filter(user=user)
    phone_numbers_qs = PhoneNumber.objects.filter(user=user)
    hours_of_operation = HoursOfOperation.objects.filter(user=user)
    call_data = CallData.objects.filter(user=user)
    ai = AIAssistant.objects.filter(user=user).first()
    
    company_info_data = CompanyInformationSerializer(company_info).data if company_info else None
    if company_info_data:
        company_info_data["business_name"] = company_info_data.pop("company_name", "")

    phone_numbers_data = PhoneNumberSerializer(phone_numbers_qs, many=True).data

    response_data = {
        "user_id": str(user.id),
        "company_info": company_info_data,
        "price_info": PriceInfoSerializer(price_info, many=True).data,
        "booking_links": BookingLinkSerializer(booking_links, many=True).data,
        "phone_numbers": phone_numbers_data,
        "hours_of_operation": HoursOfOperationSerializer(hours_of_operation, many=True).data,
        "call_data": CallDataSerializer(call_data, many=True).data,
        "selected_voice_id": ai.vapi_assistant_id if ai else None
    }

    return response_data


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_calldata(request):
    serializer = CallDataSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)  # Uses the custom create() method from the serializer
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    else:
        # Print errors to console/logs
        print("CallDataSerializer errors:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)