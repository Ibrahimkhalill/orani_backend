from django.utils.dateparse import parse_datetime
from .models import Call, PhoneNumber
from rest_framework.decorators import api_view
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .serializers import *
from orani_main.utils import error_response
from .models import PhoneNumber , CompanyInformation
from .serializers import *
from authentications.serializers import UserProfileSerializer
import random
from twilio.rest import Client
from authentications.models import UserProfile
import os
from datetime import datetime
import pytz  # optional, for timezone conversion
import requests
from twilio.twiml.voice_response import VoiceResponse
from rest_framework import generics
from twilio.twiml.voice_response import VoiceResponse , Dial


TWILIO_ACCOUNT_SID = os.getenv("TWILLIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILLIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILLIO_PHONE_NUMBER")


client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
print("client",TWILIO_ACCOUNT_SID,TWILIO_AUTH_TOKEN)



import requests


def genrate_push_token(request):
    with open(r"C:\Users\Ibrahim Khalil\Desktop\Ibrahim Work\django\orani_app\ai_call\service_account.json") as f:
        fcm_json = json.load(f)


    # Create Push Credential
    push_credential = client.chat.credentials.create(
        type="fcm",
        friendly_name="voice-push-credential-fcm",
        secret=json.dumps(fcm_json)
    )

    print("Push Credential SID:", push_credential.sid)
    
    


def get_user_location(request):
    # Get IP from request
    ip = get_client_ip(request)  # custom function to handle proxies, etc.

    # Use free API (example)
    resp = requests.get(f"https://ipapi.co/{ip}/json/")
    if resp.status_code == 200:
        data = resp.json()
        return {
            "city": data.get("city"),
            "region": data.get("region"),
            "country": data.get("country_code"),
            "area_code": data.get("area_code")  # if provided
        }
    return None

def get_client_ip(request):
    """Get client IP handling proxies"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@api_view(["GET"])
# @permission_classes([IsAuthenticated])
def get_virtual_numbers(request):
    data = get_user_location(request)
    

    # Fallback if location lookup fails
    if not data:
        data = {
            "city": None,
            "region": None,
            "country": "US",
            "area_code": None
        }

    supported_local_countries = ["US", "CA"]  # countries Twilio supports
    country_code = data.get("country") or "US"

    if country_code not in supported_local_countries:
        country_code = "US"  # fallback to default

    # Optional: filter by area code if available
    area_code = request.GET.get("area_code")

    try:
        if area_code :
            numbers = client.available_phone_numbers(country_code).local.list(
                sms_enabled=True,
                voice_enabled=True,
                limit=4,
                area_code=area_code
            )
        else:
             numbers = client.available_phone_numbers(country_code).local.list(
                sms_enabled=True,
                voice_enabled=True,
                limit=4,
            )
            
    except Exception as e:
        return error_response(code=500, message=f"Failed to fetch numbers: {str(e)}")

    existing_numbers = PhoneNumber.objects.values_list("phone_number", flat=True)

    available_numbers = [n.phone_number for n in numbers if n.phone_number not in existing_numbers]

    if not available_numbers:
        return error_response(code=404, message="No new available numbers found")

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

    if not phone_number:
        return Response(
            {"message": "Phone number is required."}, status=400
        )

    # Check if this number is already assigned to this user
    existing = PhoneNumber.objects.filter(user=user).first()
    if existing and existing.phone_number == phone_number:
        save_knowdege_data(request)
        return Response(
            {"message": "Phone number is already assigned to this user."},
            status=200,
        )

    # Check if number is used by another user
    if PhoneNumber.objects.filter(phone_number=phone_number).exclude(user=user).exists():
        return Response(
            {"message": "This phone number is already saved by another user."},
            status=409,
        )

    # Save or update the phone number for this user
    saved_number, created = PhoneNumber.objects.update_or_create(
        user=user,
        defaults={"phone_number": phone_number, "is_active": True}
    )

    # Twilio integration
    try:
        # Check if number exists in Twilio? Optional: fetch existing numbers
        client.incoming_phone_numbers.create(
            phone_number=phone_number,
            voice_url="https://api.vapi.ai/twilio/inbound_call",
            voice_method="POST",
            status_callback="https://api.vapi.ai/twilio/call_status",
            status_callback_method="POST"
        )
    except Exception as e:
        print("Twilio Error:", e)
        # Optionally mark the number inactive instead of deleting
        saved_number.is_active = False
        saved_number.save()
        return Response(
            {"message": "Failed to update Twilio webhooks."}, status=400
        )

    # Mark onboarding as completed
    user_profile, _ = UserProfile.objects.get_or_create(user=user)
    user_profile.has_completed_onboarding = True
    user_profile.save()

    user_profile_serializer = UserProfileSerializer(user_profile)
    # Save knowledge data
    save_knowdege_data(request)

    return Response(
        {
            "message": "Phone number saved successfully.",
            "phone_number": phone_number,
            "user_profile": user_profile_serializer.data,
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
        backend_url = f'{os.getenv("AI_BACKEND_URL")}/setup/assistant'
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
    from_number = request.POST.get('From')  # customer real number
    to_number = request.POST.get('To')      # your Twilio number

    print(f"📞 Incoming call from {from_number} to {to_number}")
    response = VoiceResponse()
    # এখন কলটা তোমার app user (ধরা যাক 'alice') কে পাঠাও
    dial = response.dial()
    dial.client('38')  # Twilio client identity — তোমার app এ register করা user

    return HttpResponse(str(response), content_type='text/xml')



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_call_logs(request):
    user = request.user
    call_list = []
    phone = PhoneNumber.objects.filter(user=user).first()

    if not phone:
        return Response({
            "error": "User does not have a phone number assigned."
        }, status=200)

    user_timezone = getattr(user, "timezone", "UTC")
    tz = pytz.timezone(user_timezone)

    incoming_calls = client.calls.list(to=phone.phone_number)
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
        "phone_number": phone.phone_number,
        "total_calls": len(all_calls_sorted),
        "answered_calls": len([c for c in all_calls_sorted if c.status == "completed"]),
        "calls": call_list
    })

    
def get_call_summary(client, phone_number, user_timezone="UTC"):
    """
    Twilio call summary for a given phone number.
    """
    
    try :
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
    except Exception as e:
        print("Error in get_call_summary:", e)
        return {
            "incoming_calls": 0,
            "outgoing_calls": 0,
            "missed_calls": 0,
            "received_calls": 0,
            "total_calls": 0,
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

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_assistant_data(request):
   
    assistant = AIAssistant.objects.filter(user=request.user).first()
    serializer = AIAssistantSerializer(assistant)
    return Response(serializer.data)

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
    
    


# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def list_hours_of_operation(request):
#     """
#     List all hours of operation for the current user.
#     """
#     hours = HoursOfOperation.objects.filter(user=request.user)
#     serializer = HoursOfOperationSerializer(hours, many=True)
#     return Response(serializer.data)



class BookListView(generics.ListAPIView):
    queryset = HoursOfOperation.objects.all()
    serializer_class = HoursOfOperationSerializer
    permission_classes = [IsAuthenticated]


@api_view(['POST', 'PUT'])
@permission_classes([IsAuthenticated])
def manage_hours_of_operation(request):
    day_groups = request.data.get('day_groups', [])
    if not isinstance(day_groups, list):
        return Response({"error": "day_groups must be a list"}, status=400)

    user = request.user
    # Delete previous entries if needed
    HoursOfOperation.objects.filter(user=user).delete()

    saved_groups = []
    for group_data in day_groups:
        serializer = HoursOfOperationSerializer(data=group_data, context={'request': request})
        if serializer.is_valid():
            obj = serializer.save()  # Creates a new record for each group
            saved_groups.append({
                "id": obj.id,
                "days": obj.days,
                "start_time": obj.start_time.strftime("%H:%M"),
                "end_time": obj.end_time.strftime("%H:%M")
            })
        else:
            return Response(serializer.errors, status=400)

    return Response({
        "message": "Hours saved successfully",
        "day_groups": saved_groups
    }, status=200)










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
    
    
    
    api_key = os.getenv("TWILLIO_API_KEY")         
    api_secret = os.getenv("TWILLIO_API_SECRET") 
    outgoing_app_sid = os.getenv("TWILLIO_OUTGOING_APP_SID")
    push_credential_sid = os.getenv("PUSH_CREDENTIAL_SID")
    identity = str(request.user.id) 
    print("api_key, api_secret, outgoing_app_sid", api_key, api_secret, outgoing_app_sid)

    # Create token
    token = AccessToken(TWILIO_ACCOUNT_SID, api_key, api_secret, identity=identity)
    voice_grant = VoiceGrant(
        outgoing_application_sid=outgoing_app_sid,
        incoming_allow=True,
        push_credential_sid=push_credential_sid
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
        "selected_voice_id": ai.vapi_assistant_id if ai else None,
        "ai_name": ai.name if ai else None,
        "ring_count": int(ai.ring) if ai.ring else None
        
    }

    return response_data


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_calldata(request):
    user = request.user
    print("User:", user)
    print("Request data:", request.data)

    # Check if user already has CallData
    instance = CallData.objects.filter(user=user).first()

    if instance:
        # Update existing CallData
        serializer = CallDataSerializer(instance, data=request.data)
    else:
        # Create new CallData
        serializer = CallDataSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save(user=user)  # Will create or update as needed
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    else:
        print("Serializer errors:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_bussines_call_data(request):
    user = request.user
    call_data = CallData.objects.filter(user=user).first()
    if not call_data:
        return Response({'detail': 'No call data found.'}, status=status.HTTP_404_NOT_FOUND)
    serializer = CallDataSerializer(call_data)
    return Response(serializer.data, status=status.HTTP_200_OK)
   




@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def save_update_priocity_contact(request):
   
    if request.method == 'GET':
        try:
            priority_contact = PriorityContact.objects.get(user=request.user)
        except PriorityContact.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PriorityContactSerializer(priority_contact, many=True)
        if serializer.is_valid():
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
  
    elif request.method == 'POST':
        number = request.data.get("number", None)

       
        if number:
            try:
                priority_contact = PriorityContact.objects.get(phone_number=number, user=request.user)
                priority_contact.delete()
                return Response(
                    {"detail": f"Priority contact {number} removed successfully"},
                    status=status.HTTP_200_OK
                )
            except PriorityContact.DoesNotExist:
                return Response({"detail": "Contact not found."}, status=status.HTTP_404_NOT_FOUND)

        
        serializer = PriorityContactSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        print("serializer.errors",serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])    
def fetch_sms_history(request):
    # genrate_push_token(request)
    user = request.user
    number = PhoneNumber.objects.get(user=user)
    from_number = request.GET.get("from_number")
    print("number",number.phone_number)
    try :
        messages = client.messages.list(
            to= TWILIO_PHONE_NUMBER,
            # to=number.phone_number,
            from_=from_number
        )
        
        print("messages",messages)

        sms_history = []
        for msg in messages:
            sms_history.append({
                "from": msg.from_,
                "to": msg.to,
                "body": msg.body,
                "status": msg.status,
                "direction": msg.direction,
                "date_sent": str(msg.date_sent)
            })
        return Response(sms_history, status=200)    
            
    except Exception as e:
        return Response(e)