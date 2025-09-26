from rest_framework import serializers
from .models import *

class CompanyInformationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyInformation
        fields = [
            'id',
            'user',
            'company_name',
            'website_url',
            'email',
            'company_details',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
 
 
class PriceInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceInfo
        fields = [
            'id',
            'user',
            'package_name',
            'package_price',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']       
 
 
class BookingLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingLink
        fields = [
            'id',
            'user',
            'booking_title',
            'booking_link',
           
        ]
        read_only_fields = ['id', 'user']  
 
class PhoneNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhoneNumber
        fields = [
            'id',
            'user',
            'phone_number',
            'vapi_phone_id',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'user', 'created_at']
        
        
        

from rest_framework import serializers
from .models import HoursOfOperation, WorkingDay

class HoursOfOperationSerializer(serializers.ModelSerializer):
    days = serializers.ListField(
        child=serializers.ChoiceField(choices=WorkingDay.choices)
    )

    class Meta:
        model = HoursOfOperation
        fields = ['id', 'user', 'days', 'start_time', 'end_time']
        read_only_fields = ['id', 'user']

    def create(self, validated_data):
        user = self.context['request'].user
        days = validated_data.pop('days')
        start_time = validated_data['start_time']
        end_time = validated_data['end_time']
        
        HoursOfOperation.objects.filter(user=user).delete()

        
        obj, created = HoursOfOperation.objects.update_or_create(
            user=user,
            defaults={'start_time': start_time, 'end_time': end_time, 'days': days}
        )
        return obj



class CallDataSerializer(serializers.ModelSerializer):
    call_types = serializers.MultipleChoiceField(choices=CallData.CALL_TYPES)
    industries = serializers.MultipleChoiceField(choices=CallData.INDUSTRIES)
    work_styles = serializers.MultipleChoiceField(choices=CallData.WORK_STYLES)
    assistances = serializers.MultipleChoiceField(choices=CallData.ASSISTANCE_TYPES)

    class Meta:
        model = CallData
        fields = ['id', 'user', 'call_types', 'industries', 'work_styles', 'assistances', 'created_at']
        read_only_fields = ['id', 'created_at', 'user']

    def create(self, validated_data):
        call_types = validated_data.pop('call_types')
        industries = validated_data.pop('industries')
        work_styles = validated_data.pop('work_styles')
        assistances = validated_data.pop('assistances')
        instance = CallData.objects.create(
            call_types=','.join(call_types),
            industries=','.join(industries),
            work_styles=','.join(work_styles),
            assistances=','.join(assistances)
        )
        return instance

    def update(self, instance, validated_data):
        instance.call_types = ','.join(validated_data.get('call_types', instance.call_types.split(',')))
        instance.industries = ','.join(validated_data.get('industries', instance.industries.split(',')))
        instance.work_styles = ','.join(validated_data.get('work_styles', instance.work_styles.split(',')))
        instance.assistances = ','.join(validated_data.get('assistances', instance.assistances.split(',')))
        instance.save()
        return instance

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        
        def ensure_list(value):
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                return value.split(',') if value else []
            return []

        ret['call_types'] = ensure_list(getattr(instance, 'call_types', []))
        ret['industries'] = ensure_list(getattr(instance, 'industries', []))
        ret['work_styles'] = ensure_list(getattr(instance, 'work_styles', []))
        ret['assistances'] = ensure_list(getattr(instance, 'assistances', []))
        
        return ret



from rest_framework import serializers
from .models import AIAssistant

class AIAssistantSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIAssistant
        fields = ['user', 'vapi_assistant_id', 'name', 'voice_settings', 'created_at']
        read_only_fields = ['created_at']