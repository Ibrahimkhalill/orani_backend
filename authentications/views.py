from django.shortcuts import render
from django.contrib.auth.hashers import make_password
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import OTP, UserProfile, CustomUser
from .serializers import (
    CustomUserSerializer,
    CustomUserCreateSerializer,
    UserProfileSerializer,
    OTPSerializer,
    AppleLoginSerializer,
    PhoneLoginSerializer,
    CustomUserUpdateSerializer

)

from django.http import JsonResponse
import re

from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from orani_main.utils import error_response
import random
from twilio.rest import Client
import os
TWILIO_ACCOUNT_SID = os.getenv("TWILLIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILLIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILLIO_PHONE_NUMBER")


client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

print("SID:", TWILIO_ACCOUNT_SID)
print("TOKEN:", TWILIO_AUTH_TOKEN)
print("PHONE:", TWILIO_PHONE_NUMBER)

User = get_user_model()


def generate_otp():
    return str(random.randint(10000, 99999))


def send_otp_sms(phone_number, otp):
    # return get_virtual_numbers()

    message_body = f"Your verification OTP is: {otp}"
    try:
        message = client.messages.create(
            body=message_body,
            from_=TWILIO_PHONE_NUMBER,
            to=phone_number  # use the passed phone_number
        )
        print("OTP sent successfully")
        return message.sid  # optionally return the message SID
    except Exception as e:
        print(f"Failed to send OTP SMS: {e}")
        raise e


@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    
    serializer = CustomUserCreateSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        phone_number = serializer.validated_data['phone_number']

        otp = generate_otp()
        OTP.objects.filter(phone_number=phone_number).delete()
        otp_data = {'phone_number': user.phone_number, 'otp': otp}
        otp_serializer = OTPSerializer(data=otp_data)
        if otp_serializer.is_valid():
            otp_serializer.save()
            try:
                result = send_otp_sms(phone_number=phone_number, otp=otp)
            except Exception as e:
                raw_error = str(e)

                # Remove ANSI color codes
                ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
                clean_error = ansi_escape.sub('', raw_error).strip()

                # Optionally, extract just the important line
                clean_line = None
                for line in clean_error.split("\n"):
                    if "Invalid 'To' Phone Number" in line:
                        clean_line = line.strip()
                        break
                if not clean_line:
                    clean_line = clean_error.split("\n")[0]  # fallback

                return error_response(
                    code=500,
                    message=clean_line,
                    details={"twilio_error": clean_line}
                )

        return Response({
            "message": "Please verify your phone number with the OTP sent",
            "user_id": user.id,
            "result": result
        }, status=status.HTTP_201_CREATED)
    return error_response(code=400, details=serializer.errors)


@api_view(['POST'])
@permission_classes([AllowAny])
def request_login_otp(request):
    """
    Step 1 of phone login: user submits phone_number to get OTP sent
    """
    serializer = PhoneLoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        phone_number = user.phone_number

        otp = generate_otp()
        OTP.objects.filter(phone_number=user.phone_number).delete()
        otp_data = {'phone_number': user.phone_number, 'otp': otp}
        otp_serializer = OTPSerializer(data=otp_data)
        if otp_serializer.is_valid():
            otp_serializer.save()
            try:
                send_otp_sms(phone_number=phone_number, otp=otp)
            except Exception as e:
                return error_response(
                    code=500,
                    message="Failed to send OTP SMS",
                    details={"error": [str(e)]}
                )
            return Response({"message": "OTP sent to your phone number", "user_id": user.id}, status=status.HTTP_201_CREATED)
        return error_response(code=400, details=otp_serializer.errors)
    return error_response(code=400, details=serializer.errors)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_login_otp(request):
    """
    Step 2 of phone login: user submits phone_number + otp, get JWT tokens if valid
    """
    user_id = request.data.get('user_id')
    otp_value = request.data.get('otp')

    if not user_id or not otp_value:
        details = {}
        if not user_id:
            details['user_id'] = ['This field is required']
        if not otp_value:
            details['otp'] = ['This field is required']
        return error_response(code=400, details=details)

    try:
        user = User.objects.get(id=user_id)
        otp_obj = OTP.objects.get(phone_number=user.phone_number)

        if otp_obj.otp != otp_value:
            return error_response(
                code=400,
                details={"otp": ["The provided OTP is invalid"]}
            )
        if otp_obj.is_expired():
            return error_response(
                code=400,
                details={"otp": ["The OTP has expired"]}
            )
        if not user.is_verified:
            user.is_verified = True
            user.is_active = True
            user.save()

        otp_obj.delete()

        refresh = RefreshToken.for_user(user)
        profile = getattr(user, 'user_profile', None)
        profile_serializer = UserProfileSerializer(profile)

        return Response({
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "role": user.role,
            "is_verified": user.is_verified,
            "profile": profile_serializer.data
        }, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        return error_response(
            code=404,
            details={"phone_number": ["No user exists with this phone number"]}
        )
    except OTP.DoesNotExist:
        return error_response(
            code=404,
            details={"phone_number": ["No OTP found for this phone number"]}
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def apple_login(request):
    serializer = AppleLoginSerializer(data=request.data)
    if serializer.is_valid():
        # identity_token = serializer.validated_data['identity_token']
        user_id = serializer.validated_data['user_id']
        email = serializer.validated_data.get('email', None)

        # TODO: Verify identity_token with Apple here

        # Try get user by apple_user_id field (you must add this field in your User model)
        try:
            user = User.objects.get(apple_user_id=user_id)
        except User.DoesNotExist:
            # Create new user with apple_user_id
            user = User.objects.create_user(
                phone_number=None,
                email=email,
                role='user',
                is_verified=True,
                apple_user_id=user_id,
                # No password needed for Apple login
                password=make_password(None)
            )
            UserProfile.objects.create(user=user, name=email.split(
                '@')[0] if email else "AppleUser")

        refresh = RefreshToken.for_user(user)
        profile_serializer = UserProfileSerializer(user.user_profile)

        return Response({
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "role": user.role,
            "is_verified": user.is_verified,
            "profile": profile_serializer.data
        }, status=status.HTTP_200_OK)

    return error_response(code=400, details=serializer.errors)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_users(request):
    users = User.objects.all()
    serializer = CustomUserSerializer(users, many=True)
    return Response(serializer.data)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    try:
        profile = request.user.user_profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(
            user=request.user, name=request.user.email.split('@')[0])

    if request.method == 'GET':
        user = CustomUser.objects.get(id=request.user.id)
        serializer = CustomUserSerializer(user, context={'request': request})
        return Response(serializer.data)

    if request.method == 'PUT':
        print("data", request)
        print("FILES:", request.FILES) 
        user = request.user
        serializer = CustomUserUpdateSerializer(user, data=request.data, partial=True, context={'request': request})
        profileSerializer = UserProfileSerializer(profile, data=request.data,  partial=True, context={'request': request})
        if serializer.is_valid() and profileSerializer.is_valid():
            serializer.save()
            profileSerializer.save()
            return Response(serializer.data)
        return error_response(code=400, details=serializer.errors)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_otp(request):
    user_id = request.data.get('user_id')
    if not user_id:
        return error_response(
            code=400,
            details={"user_id": ["This field is required"]}
        )

    try:
        user = User.objects.get(id=user_id)

    except User.DoesNotExist:
        return error_response(
            code=404,
            details={"user_id": ["No user exists with this phone number"]}
        )

    otp = generate_otp()
    OTP.objects.filter(phone_number=user.phone_number).delete()
    otp_data = {'phone_number': user.phone_number, 'otp': otp}
    serializer = OTPSerializer(data=otp_data)
    if serializer.is_valid():
        serializer.save()
        try:
            send_otp_sms(phone_number=user.phone_number, otp=otp)
        except Exception as e:
            return error_response(
                code=500,
                message="Failed to send OTP SMS",
                details={"error": [str(e)]}
            )
        return Response({"message": "OTP sent to your phone number"}, status=status.HTTP_201_CREATED)
    return error_response(code=400, details=serializer.errors)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    user_id = request.data.get('user_id')
    otp_value = request.data.get('otp')

    if not user_id or not otp_value:
        details = {}
        if not user_id:
            details["user_id"] = ["This field is required"]
        if not otp_value:
            details["otp"] = ["This field is required"]
        return error_response(code=400, details=details)

    try:
        user = User.objects.get(pk=user_id)
        otp_obj = OTP.objects.get(email=user.email)

        if otp_obj.otp != otp_value:
            return error_response(
                code=400,
                details={"otp": ["The provided OTP is invalid"]}
            )
        if otp_obj.is_expired():
            return error_response(
                code=400,
                details={"otp": ["The OTP has expired"]}
            )



        user.is_verified = True
        user.save()
        otp_obj.delete()

        return Response({"message": "Phone number verified successfully. You can now log in"})
    except User.DoesNotExist:
        return error_response(
            code=404,
            details={"phone_number": ["No user exists with this phone number"]}
        )
    except OTP.DoesNotExist:
        return error_response(
            code=404,
            details={"phone_number": ["No OTP found for this phone number"]}
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp_reset(request):
    phone_number = request.data.get('phone_number')
    otp_value = request.data.get('otp')

    if not phone_number or not otp_value:
        details = {}
        if not phone_number:
            details["phone_number"] = ["This field is required"]
        if not otp_value:
            details["otp"] = ["This field is required"]
        return error_response(code=400, details=details)

    try:
        user = User.objects.get(user_profile__phone_number=phone_number)
        otp_obj = OTP.objects.get(email=user.email)

        if otp_obj.otp != otp_value:
            return error_response(
                code=400,
                details={"otp": ["The provided OTP is invalid"]}
            )
        if otp_obj.is_expired():
            return error_response(
                code=400,
                details={"otp": ["The OTP has expired"]}
            )
        return Response({"message": "OTP verified successfully"})
    except User.DoesNotExist:
        return error_response(
            code=404,
            details={"phone_number": ["No user exists with this phone number"]}
        )
    except OTP.DoesNotExist:
        return error_response(
            code=404,
            details={"phone_number": ["No OTP found for this phone number"]}
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    phone_number = request.data.get('phone_number')
    if not phone_number:
        return error_response(
            code=400,
            details={"phone_number": ["This field is required"]}
        )

    try:
        user = User.objects.get(user_profile__phone_number=phone_number)
        if not user.is_verified:
            return error_response(
                code=400,
                details={"phone_number": [
                    "Please verify your phone number before resetting your password"]}
            )
    except User.DoesNotExist:
        return error_response(
            code=404,
            details={"phone_number": ["No user exists with this phone number"]}
        )

    otp = generate_otp()
    OTP.objects.filter(email=user.email).delete()
    otp_data = {'email': user.email, 'otp': otp}
    serializer = OTPSerializer(data=otp_data)
    if serializer.is_valid():
        serializer.save()
        try:
            send_otp_sms(phone_number=phone_number, otp=otp)
        except Exception as e:
            return error_response(
                code=500,
                message="Failed to send OTP SMS",
                details={"error": [str(e)]}
            )
        return Response({"message": "OTP sent to your phone number"}, status=status.HTTP_201_CREATED)
    return error_response(code=400, details=serializer.errors)


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    phone_number = request.data.get('phone_number')
    otp_value = request.data.get('otp')
    new_password = request.data.get('new_password')

    if not all([phone_number, otp_value, new_password]):
        details = {}
        if not phone_number:
            details["phone_number"] = ["This field is required"]
        if not new_password:
            details["new_password"] = ["This field is required"]
        return error_response(code=400, details=details)

    try:
        user = User.objects.get(user_profile__phone_number=phone_number)
        otp_obj = OTP.objects.get(email=user.email)

        if otp_obj.otp != otp_value:
            return error_response(
                code=400,
                details={"otp": ["The provided OTP is invalid"]}
            )

        if not user.is_verified:
            return error_response(
                code=400,
                details={"phone_number": [
                    "Please verify your phone number before resetting your password"]}
            )

        try:
            validate_password(new_password, user)
        except ValidationError as e:
            return error_response(
                code=400,
                details={"new_password": e.messages}
            )

        user.set_password(new_password)
        user.save()
        otp_obj.delete()
        return Response({'message': 'Password reset successful'})
    except User.DoesNotExist:
        return error_response(
            code=404,
            details={"phone_number": ["No user exists with this phone number"]}
        )
    except OTP.DoesNotExist:
        return error_response(
            code=404,
            details={"phone_number": ["No OTP found for this phone number"]}
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')

    if not current_password or not new_password:
        details = {}
        if not current_password:
            details["current_password"] = ["This field is required"]
        if not new_password:
            details["new_password"] = ["This field is required"]
        return error_response(code=400, details=details)

    user = request.user
    if not user.check_password(current_password):
        return error_response(
            code=400,
            details={"current_password": ["The current password is incorrect"]}
        )

    try:
        validate_password(new_password, user)
    except ValidationError as e:
        return error_response(
            code=400,
            details={"new_password": e.messages}
        )

    user.set_password(new_password)
    user.save()
    return Response({'message': 'Password changed successfully'}, status=status.HTTP_200_OK)
