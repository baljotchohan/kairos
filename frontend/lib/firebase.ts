import { initializeApp, getApps, getApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

const isConfigured = !!process.env.NEXT_PUBLIC_FIREBASE_API_KEY;

if (!isConfigured && typeof window !== "undefined") {
  console.warn("KAIROS: Firebase env variables are missing. Auth will default to local client simulation.");
}

// Initialise Firebase defensively. A throw here (bad/partial config) would
// crash the entire client bundle at import time, so we fall back to null
// (simulation mode) instead of letting it bubble.
let app: ReturnType<typeof initializeApp> | null = null;
let auth: ReturnType<typeof getAuth> | null = null;

try {
  if (isConfigured) {
    app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();
    auth = getAuth(app);
  }
} catch (err) {
  if (typeof window !== "undefined") {
    console.error("KAIROS: Firebase init failed, falling back to simulation mode.", err);
  }
  app = null;
  auth = null;
}

export { app, auth };
