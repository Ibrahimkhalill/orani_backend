import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from .models import RevenueCatEvent

@csrf_exempt
def revenuecat_webhook(request):
    if request.method == "POST":
        try:
            payload = json.loads(request.body)
            print("Received RevenueCat webhook:", payload)
            event = payload.get("event", {})

            event_type = event.get("type")
            app_user_id = event.get("app_user_id")
            product_id = event.get("product_id")
            purchased_at_ms = event.get("purchased_at_ms")
            expiration_at_ms = event.get("expiration_at_ms")
            environment = event.get("environment")

            # timestamp convert
            purchased_at = (
                datetime.fromtimestamp(purchased_at_ms / 1000.0)
                if purchased_at_ms else None
            )
            expiration_at = (
                datetime.fromtimestamp(expiration_at_ms / 1000.0)
                if expiration_at_ms else None
            )

            # Check if subscription exists for this user + product
            sub, created = RevenueCatEvent.objects.update_or_create(
                app_user_id=app_user_id,
                product_id=product_id,
                defaults={
                    "event_type": event_type,
                    "purchased_at": purchased_at,
                    "expiration_at": expiration_at,
                    "environment": environment,
                    "raw_payload": payload,
                },
            )

            if created:
                msg = f"New subscription created for {app_user_id}"
            else:
                msg = f"Subscription updated (renewal/change) for {app_user_id}"

            print(f"[RevenueCat Webhook] {msg} | Event: {event_type}")

            return JsonResponse({"status": "success", "message": msg, "event_type": event_type}, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Invalid method"}, status=405)
