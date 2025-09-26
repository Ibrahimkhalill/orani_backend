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
        fields = ['id', 'user', 'name', 'profile_picture', 'has_completed_onboarding', 'joined_date']
        read_only_fields = ['id', 'user', 'joined_date']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        if instance.profile_picture and request:
            rep['profile_picture'] = request.build_absolute_uri(instance.profile_picture.url)
        return rep




class CustomUserUpdateSerializer(serializers.ModelSerializer):
    user_profile = UserProfileSerializer()

    class Meta:
        model = User
        fields = ['id', 'phone_number', 'email', 'role', 'is_verified', 'user_profile']
        read_only_fields = ['id', 'is_active', 'is_staff', 'is_superuser']

    def update(self, instance, validated_data):
    # Update email
        email = validated_data.get('email')
        if email:
            instance.email = email
            instance.save()

        return instance




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
            # Pass the request context so nested serializer can build full image URL
            context = self.context
            return UserProfileSerializer(obj.user_profile, context=context).data
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

    def create(self, validated_data):
        name = validated_data.pop('name', None)
        phone_number = validated_data.get('phone_number')

        # Check if a verified user already exists
        verified_user = User.objects.filter(phone_number=phone_number, is_verified=True).first()
        if verified_user:
            # Skip creation and just return the existing verified user
            return verified_user

        # Otherwise, create or update unverified user
        user, created = User.objects.update_or_create(
            phone_number=phone_number,
            defaults={
                'role': validated_data.get('role', 'user'),
                'is_active': False,     # inactive until verification
                'is_verified': False,   # not verified yet
                'email': validated_data.get('email')
            }
        )

        # Create or update profile
        UserProfile.objects.update_or_create(user=user)

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