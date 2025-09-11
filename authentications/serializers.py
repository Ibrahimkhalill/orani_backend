from rest_framework import serializers
from .models import CustomUser, OTP, UserProfile
from django.contrib.auth import get_user_model
from payment.models import Subscription

User = get_user_model()

# ---------------------------
# ✅ User Profile Serializer
# ---------------------------
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'name', 'profile_picture', 'joined_date']
        read_only_fields = ['id', 'user', 'joined_date']

    def validate(self, data):
        if 'name' in data and not data['name']:
            raise serializers.ValidationError({'name': 'Name cannot be empty'})
        return data


# ---------------------------
# ✅ User Serializer (For Read)
# ---------------------------
class CustomUserSerializer(serializers.ModelSerializer):
    user_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'phone_number', 'email', 'role', 'is_verified', 'user_profile']
        read_only_fields = ['id', 'is_active', 'is_staff', 'is_superuser']

    def get_user_profile(self, obj):
        try:
            return UserProfileSerializer(obj.user_profile).data
        except UserProfile.DoesNotExist:
            return None


# ---------------------------
# ✅ User Create Serializer (Signup with Phone)
# ---------------------------
class CustomUserCreateSerializer(serializers.ModelSerializer):
    name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    phone_number = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = ['id', 'phone_number', 'email', 'role', 'name']
        extra_kwargs = {
            'phone_number': {'required': True},
            'email': {'required': False},
        }

    def validate(self, data):
        phone_number = data.get('phone_number')
        if not phone_number:
            raise serializers.ValidationError({'phone_number': 'This field is required'})
        if User.objects.filter(phone_number=phone_number, is_verified=True).exists():
            raise serializers.ValidationError({'phone_number': 'User already exists'})
        return data

    def create(self, validated_data):
        name = validated_data.pop('name', None)
        phone_number = validated_data.get('phone_number')

        # delete unverified duplicates
        User.objects.filter(phone_number=phone_number, is_verified=False).delete()

        user = User.objects.create_user(
            phone_number=phone_number,
            role=validated_data.get('role', 'user')
        )
        UserProfile.objects.create(user=user, name=name)
        return user


# ---------------------------
# ✅ OTP Serializer (for phone-based OTP login)
# ---------------------------
class OTPSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(required=True)
    otp = serializers.CharField(required=True)

    class Meta:
        model = OTP
        fields = ['id', 'phone_number', 'otp', 'created_at', 'attempts']
        read_only_fields = ['id', 'created_at', 'attempts']

    def validate(self, data):
        if not data.get('phone_number') or not data.get('otp'):
            raise serializers.ValidationError({'detail': 'Phone number and OTP are required'})
        return data


# ---------------------------
# ✅ Apple Login Serializer
# ---------------------------
class AppleLoginSerializer(serializers.Serializer):
    
    user_id = serializers.CharField(required=True)
    email = serializers.EmailField(required=False)

    def validate(self, data):
        if not data.get('user_id'):
            raise serializers.ValidationError({'detail': 'apple user_id are required'})
        return data


class PhoneLoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(required=True)
  

    def validate(self, data):
        phone_number = data.get('phone_number')
        print(phone_number)
       
        if not phone_number:
            raise serializers.ValidationError("Phone number are required")

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this phone number does not exist")

        if not user.is_verified:
            raise serializers.ValidationError("User phone number not verified")

        data['user'] = user
        return data