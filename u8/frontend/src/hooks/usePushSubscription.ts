import { useCallback } from 'react';
import { ApiClient } from '../lib/api';

const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY || '';

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export function usePushSubscription(api: ApiClient | null) {
  const subscribe = useCallback(async () => {
    if (!api || !VAPID_PUBLIC_KEY) return false;
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return false;

    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
      });

      await api.pushSubscribe(subscription.toJSON());
      return true;
    } catch {
      return false;
    }
  }, [api]);

  const unsubscribe = useCallback(async () => {
    if (!api) return false;

    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await subscription.unsubscribe();
      }
      await api.pushUnsubscribe();
      return true;
    } catch {
      return false;
    }
  }, [api]);

  return { subscribe, unsubscribe };
}
