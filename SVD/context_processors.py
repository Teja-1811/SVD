from django.conf import settings


def firebase_settings(request):
    return {
        "firebase_web_config": getattr(settings, "FIREBASE_WEB_CONFIG", {}),
        "firebase_push_vapid_key": getattr(settings, "FIREBASE_WEB_VAPID_KEY", ""),
        "firebase_push_enabled": getattr(settings, "FIREBASE_PUSH_ENABLED", False),
    }
