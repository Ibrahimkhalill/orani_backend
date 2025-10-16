from django.urls import path
from . import views

urlpatterns = [
    path('get/available-phone-number', views.get_virtual_numbers),
    path('post/assign-phone-number', views.save_phone_number),
    path('get/assign-phone-number', views.get_assigned_phone_number),
    path("twilio/incoming-call/", views.twilio_incoming_call),
    path("get/call-history/", views.user_call_logs),
    
    #company data
    path('companies/', views.company_list_create, name='company-list-create'),
    path('companies/<int:pk>/', views.company_detail, name='company-detail'),
    
    
      # PriceInfo
    path("price-info/", views.price_info_list_create, name="price-info-list-create"),
    path("price-info/<int:pk>/", views.price_info_detail, name="price-info-detail"),

    # BookingLink
    path("booking-links/", views.booking_link_list_create, name="booking-link-list-create"),
    path("booking-links/<int:pk>/", views.booking_link_detail, name="booking-link-detail"),
    
    
    #service - hour
    
    path('service-hours/', views.list_hours_of_operation, name='list_hours_of_operation'),  # GET
    path('service-hours/manage/', views.manage_hours_of_operation, name='manage_hours_of_operation'),  # POST/PUT
    
    
    path('voice/handle/', views.voice_handler),  # POST/PUT
    
    
    path('get_twilio_token/', views.get_twilio_token),  # POST/PUT
    
    
    path('save-calldata/', views.save_calldata, name='save-calldata'),
    
    path('get-calldata/', views.get_bussines_call_data, name='get-calldata'),
    
    
    path('ai-assistant/', views.create_or_update_ai_assistant, name='create_or_update_ai_assistant'),
    
    #save priority contact
    path('priority-contacts/', views.save_update_priocity_contact, name='create_or_update_priority_contact'),
    
    path("get-sms-history/user/", views.fetch_sms_history)
]
    
    

