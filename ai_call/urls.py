from django.urls import path
from . import views

urlpatterns = [
    path('get/available-phone-number', views.get_virtual_numbers),
    path('post/assign-phone-number', views.save_phone_number),
    path("twilio/incoming-call/", views.twilio_incoming_call),
]
