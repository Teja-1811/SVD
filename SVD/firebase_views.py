import json

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.cache import never_cache


@never_cache
def firebase_messaging_sw(request):
    firebase_config = json.dumps(getattr(settings, "FIREBASE_WEB_CONFIG", {}))
    script = f"""
importScripts("https://www.gstatic.com/firebasejs/12.11.0/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/12.11.0/firebase-messaging-compat.js");

firebase.initializeApp({firebase_config});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {{
  const notification = payload.notification || {{}};
  const data = payload.data || {{}};
  const title = notification.title || data.title || "SVD Update";
  const options = {{
    body: notification.body || data.body || "",
    icon: notification.icon || "/static/android-chrome-192x192.png",
    badge: notification.badge || "/static/favicon-32x32.png",
    data: {{
      click_action: data.click_action || notification.click_action || "/",
    }},
    tag: notification.tag || data.tag || "svd-update",
  }};

  self.registration.showNotification(title, options);
}});

self.addEventListener("notificationclick", (event) => {{
  event.notification.close();
  const targetUrl = event.notification?.data?.click_action || "/";

  event.waitUntil(
    clients.matchAll({{ type: "window", includeUncontrolled: true }}).then((clientList) => {{
      for (const client of clientList) {{
        if ("focus" in client) {{
          if ("navigate" in client) {{
            client.navigate(targetUrl);
          }}
          return client.focus();
        }}
      }}

      if (clients.openWindow) {{
        return clients.openWindow(targetUrl);
      }}

      return undefined;
    }})
  );
}});
""".strip()
    return HttpResponse(script, content_type="application/javascript")
