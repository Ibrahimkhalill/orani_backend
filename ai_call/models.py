# models.py
import json
from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()


class AIAssistant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    vapi_assistant_id = models.CharField(max_length=100, unique=True)
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


class BusinessKnowledge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.TextField()
    answer = models.TextField()
    category = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


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
