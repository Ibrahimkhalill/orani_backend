from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.db import transaction


# -----------------------------
# ✅ Custom User Manager
# -----------------------------
class CustomUserManager(BaseUserManager):
    def _create_user(self, phone_number=None, email=None, password=None, **extra_fields):
        if not phone_number and not email:
            raise ValueError("Phone number or email is required")
        if email:
            email = self.normalize_email(email)
            extra_fields['email'] = email
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)  # Can be blank for OTP-only login
        user.save(using=self._db)
        return user

    def create_user(self, phone_number=None, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(phone_number, email, password, **extra_fields)

    def create_superuser(self, phone_number=None, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        return self._create_user(phone_number, email, password, **extra_fields)


# -----------------------------
# ✅ Custom User Model
# -----------------------------
class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLES = (
        ('admin', 'Admin'),
        ('user', 'User'),
    )

    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    email = models.EmailField(_('email address'), unique=True, null=True, blank=True)

    apple_user_id = models.CharField(max_length=255, unique=True, null=True, blank=True)

    role = models.CharField(max_length=10, choices=ROLES, default='user')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []  # 'email' jodi chai, add here

    objects = CustomUserManager()
    
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        

   

# -----------------------------
# ✅ OTP Model
# -----------------------------
class OTP(models.Model):
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.IntegerField(default=0)

    def __str__(self):
        return f'OTP for {self.phone_number}: {self.otp}'

    def save(self, *args, **kwargs):
        with transaction.atomic():
            OTP.objects.filter(phone_number=self.phone_number).delete()
            super().save(*args, **kwargs)

    def is_expired(self):
        from django.utils import timezone
        return (timezone.now() - self.created_at).seconds > 120  # 2 min expiry


# -----------------------------
# ✅ User Profile Model (Optional)
# -----------------------------
class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='user_profile'
    )
    name = models.CharField(max_length=200, blank=True, null=True)
    profile_picture = models.ImageField(upload_to="profile", blank=True, null=True)
    joined_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)

    def __str__(self):
        return self.user.phone_number if self.user else "No User"
