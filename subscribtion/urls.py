from django.urls import path
from .views import revenuecat_webhook

urlpatterns = [
    path("webhook/revenuecat/", revenuecat_webhook, name="revenuecat_webhook"),
]
