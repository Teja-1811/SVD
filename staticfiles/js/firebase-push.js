import { initializeApp } from "https://www.gstatic.com/firebasejs/12.11.0/firebase-app.js";
import { getAnalytics } from "https://www.gstatic.com/firebasejs/12.11.0/firebase-analytics.js";
import {
  deleteToken,
  getMessaging,
  getToken,
  isSupported,
  onMessage,
} from "https://www.gstatic.com/firebasejs/12.11.0/firebase-messaging.js";

const storageKey = "svd_fcm_token";
const logPrefix = "[SVD Push]";

const main = async () => {
  const firebaseConfig = window.svdFirebaseConfig || null;
  const pushContext = window.svdPushContext || null;

  if (!firebaseConfig) {
    console.warn(`${logPrefix} Missing Firebase config.`);
    return;
  }

  const { vapidKey, pushEnabled, ...appConfig } = firebaseConfig;
  const app = initializeApp(appConfig);

  try {
    getAnalytics(app);
  } catch (_error) {
    // Analytics is optional in environments where it is unsupported.
  }

  if (!pushContext?.isAuthenticated || !pushEnabled) {
    console.info(`${logPrefix} Push disabled or user not authenticated.`);
    return;
  }

  if (!window.isSecureContext && !["localhost", "127.0.0.1"].includes(window.location.hostname)) {
    console.warn(`${logPrefix} Push notifications require a secure context.`);
    return;
  }

  if (!("Notification" in window) || !("serviceWorker" in navigator)) {
    console.warn(`${logPrefix} Browser does not support notifications or service workers.`);
    return;
  }

  const getCookie = (name) => {
    const prefix = `${name}=`;
    return document.cookie
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith(prefix))
      ?.slice(prefix.length) || "";
  };

  const postJson = async (url, payload) => {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify(payload),
    });
    console.info(`${logPrefix} POST ${url} ->`, response.status);
    return response.ok;
  };

  const showForegroundNotification = (payload) => {
    const title = payload?.notification?.title || payload?.data?.title || "SVD Update";
    const body = payload?.notification?.body || payload?.data?.body || "";
    const clickAction = payload?.data?.click_action || "/";

    if (Notification.permission !== "granted") {
      return;
    }

    const notification = new Notification(title, {
      body,
      icon: payload?.notification?.icon || "/static/android-chrome-192x192.png",
      badge: payload?.notification?.badge || "/static/favicon-32x32.png",
      tag: payload?.data?.tag || "svd-update",
    });

    notification.onclick = () => {
      window.focus();
      window.location.href = clickAction;
    };
  };

  const supported = await isSupported().catch(() => false);
  if (!supported) {
    console.warn(`${logPrefix} Firebase messaging is not supported in this browser context.`);
    return;
  }

  const messaging = getMessaging(app);
  let serviceWorkerRegistration = null;

  const unregisterPush = async ({ revokeToken = false } = {}) => {
    const storedToken = window.localStorage.getItem(storageKey);
    if (!storedToken) {
      return;
    }

    await postJson(pushContext.unregisterUrl, { token: storedToken }).catch(() => false);

    if (revokeToken) {
      try {
        await deleteToken(messaging);
      } catch (_error) {
        // Best-effort cleanup.
      }
    }

    window.localStorage.removeItem(storageKey);
  };

  const syncPushSubscription = async () => {
    if (Notification.permission === "denied") {
      console.warn(`${logPrefix} Notification permission is denied.`);
      await unregisterPush({ revokeToken: false });
      return;
    }

    let permission = Notification.permission;
    console.info(`${logPrefix} Initial notification permission:`, permission);
    if (permission === "default") {
      permission = await Notification.requestPermission();
      console.info(`${logPrefix} Permission after prompt:`, permission);
    }

    if (permission !== "granted") {
      console.warn(`${logPrefix} Notification permission was not granted.`);
      return;
    }

    serviceWorkerRegistration = serviceWorkerRegistration || await navigator.serviceWorker.register(
      pushContext.serviceWorkerUrl,
      { scope: "/" },
    );
    console.info(`${logPrefix} Service worker registered:`, serviceWorkerRegistration.scope);

    serviceWorkerRegistration = await navigator.serviceWorker.ready;
    console.info(`${logPrefix} Service worker ready:`, serviceWorkerRegistration.scope);

    const token = await getToken(messaging, {
      vapidKey,
      serviceWorkerRegistration,
    });

    if (!token) {
      console.warn(`${logPrefix} No FCM token returned.`);
      return;
    }
    console.info(`${logPrefix} FCM token generated.`, token);

    const storedToken = window.localStorage.getItem(storageKey);
    if (storedToken === token) {
      console.info(`${logPrefix} Token already stored locally.`);
      return;
    }

    const saved = await postJson(pushContext.registerUrl, {
      token,
      user_agent: navigator.userAgent,
    }).catch((error) => {
      console.warn(`${logPrefix} Backend token registration request failed.`, error);
      return false;
    });

    if (saved) {
      console.info(`${logPrefix} Token registered with backend.`);
      window.localStorage.setItem(storageKey, token);
    } else {
      console.warn(`${logPrefix} Backend token registration failed.`);
    }
  };

  onMessage(messaging, (payload) => {
    showForegroundNotification(payload);
  });

  document.querySelectorAll('a[href*="logout"]').forEach((anchor) => {
    anchor.addEventListener("click", async (event) => {
      event.preventDefault();
      await Promise.race([
        unregisterPush({ revokeToken: true }),
        new Promise((resolve) => window.setTimeout(resolve, 700)),
      ]);
      window.location.href = anchor.href;
    });
  });

  await syncPushSubscription();
};

main().catch((error) => {
  console.warn(`${logPrefix} Firebase push bootstrap failed.`, error);
});
