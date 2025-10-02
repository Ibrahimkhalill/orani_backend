from django.db import models

class RevenueCatEvent(models.Model):
    EVENT_TYPES = [
        ("INITIAL_PURCHASE", "Initial Purchase"),
        ("RENEWAL", "Renewal"),
        ("CANCELLATION", "Cancellation"),
        ("UNCANCELLATION", "Uncancellation"),
        ("EXPIRATION", "Expiration"),
        ("BILLING_ISSUE", "Billing Issue"),
        ("PRODUCT_CHANGE", "Product Change"),
        ("SUBSCRIPTION_PAUSED", "Subscription Paused"),
        ("SUBSCRIPTION_RESUMED", "Subscription Resumed"),
    ]

    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    app_user_id = models.CharField(max_length=200, null=True, blank=True)
    product_id = models.CharField(max_length=200, null=True, blank=True)
    purchased_at = models.DateTimeField(null=True, blank=True)
    expiration_at = models.DateTimeField(null=True, blank=True)
    environment = models.CharField(max_length=50, null=True, blank=True)
    raw_payload = models.JSONField()  # পুরো JSON রাখব
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} - {self.app_user_id}"
