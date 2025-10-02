# models.py
import json
from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()


class AIAssistant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    vapi_assistant_id = models.CharField(max_length=100, blank=True, null=True)
    name = models.CharField(max_length=200)
    voice_settings = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class PhoneNumber(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20)
    vapi_phone_id = models.CharField(
        max_length=100, unique=True, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)



class PriorityContact(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=400, blank=True, null=True)
    phone_number = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class BusinessKnowledge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.TextField()
    answer = models.TextField()
    category = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class CompanyInformation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    company_name = models.TextField(blank=True, null=True)
    website_url = models.CharField(max_length=1000, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    company_details = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PriceInfo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    package_name = models.TextField(blank=True, null=True)
    package_price = models.CharField(max_length=1000, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)




class BookingLink(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    booking_title = models.TextField( blank=True, null=True)
    booking_link = models.CharField(max_length=400,blank=True, null=True)




class Call(models.Model):
    CALL_STATUS_CHOICES = [
        ('started', 'Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    call_id = models.CharField(max_length=100, unique=True)
    caller_phone = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=CALL_STATUS_CHOICES)
    duration = models.IntegerField(default=0)  # in seconds
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CallTranscript(models.Model):
    call = models.OneToOneField(Call, on_delete=models.CASCADE)
    full_transcript = models.TextField()
    transcript_segments = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CallSummary(models.Model):
    call = models.OneToOneField(Call, on_delete=models.CASCADE)
    summary = models.TextField()
    key_points = models.JSONField(default=list)
    action_items = models.JSONField(default=list)
    caller_intent = models.CharField(max_length=200, blank=True)
    follow_up_needed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)



from multiselectfield import MultiSelectField

class WorkingDay(models.TextChoices):
    MONDAY = 'Mon', 'Monday'
    TUESDAY = 'Tue', 'Tuesday'
    WEDNESDAY = 'Wed', 'Wednesday'
    THURSDAY = 'Thu', 'Thursday'
    FRIDAY = 'Fri', 'Friday'
    SATURDAY = 'Sat', 'Saturday'
    SUNDAY = 'Sun', 'Sunday'

class HoursOfOperation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hours_of_operation')
    days = MultiSelectField(choices=WorkingDay.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.user.email} - {', '.join(self.days)}: {self.start_time} to {self.end_time}"





from django.db import models

from django.db import models
from multiselectfield import MultiSelectField

class CallData(models.Model):
    CALL_TYPES = (
        ('Client Inquiries', 'Client Inquiries'),
        ('Bookings', 'Bookings'),
        ('Support', 'Support'),
        ('Sales', 'Sales'),
        ('Follow-up', 'Follow-up'),
        ('Personalized', 'Personalized'),
        ('Mixed', 'Mixed'),
    )
    
    INDUSTRIES = (
        ('Real Estate', 'Real Estate'),
        ('Business Development', 'Business Development'),
        ('Technology', 'Technology'),
        ('Operation', 'Operation'),
        ('Accounting', 'Accounting'),
        ('Recruiting', 'Recruiting'),
        ('Sales', 'Sales'),
        ('Others', 'Others'),
    )
    
    WORK_STYLES = (
        ('Solo', 'Solo'),
        ('Small Team', 'Small Team'),
        ('Growing Business', 'Growing Business'),
        ('Remote', 'Remote'),
        ('Freelancer', 'Freelancer'),
        ('On-Site', 'On-Site'),
        ('Others', 'Others'),
    )
    
    ASSISTANCE_TYPES = (
        ('Answer Calls', 'Answer Calls'),
        ('Share Info', 'Share Info'),
        ('Handle Bookings', 'Handle Bookings'),
        ('Schedule Meetings', 'Schedule Meetings'),
        ('FAQs', 'FAQs'),
        ('Collect Leads', 'Collect Leads'),
        ('Others', 'Others'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    call_types = MultiSelectField(choices=CALL_TYPES, max_length=100)
    industries = MultiSelectField(choices=INDUSTRIES, max_length=100)
    work_styles = MultiSelectField(choices=WORK_STYLES, max_length=100)
    assistances = MultiSelectField(choices=ASSISTANCE_TYPES, max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{', '.join(self.call_types)} - {', '.join(self.industries)}"