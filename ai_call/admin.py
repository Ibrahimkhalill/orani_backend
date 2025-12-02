from django.contrib import admin

# Register your models here.
from .models import *

admin.site.register(CompanyInformation)
admin.site.register(CallData)
admin.site.register(AIAssistant)
admin.site.register(HoursOfOperation)
admin.site.register(PhoneNumber)