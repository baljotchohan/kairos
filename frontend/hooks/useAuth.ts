"use client";

import { useEffect, useState } from "react";
import {
  User,
  signInWithPopup,
  signInWithRedirect,
  GoogleAuthProvider,
  signInAnonymously as firebaseSignInAnonymously,
  signOut,
  onIdTokenChanged,
} from "firebase/auth";
import { auth } from "@/lib/firebase";

export interface AuthUser {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
  isAnonymous: boolean;
}

// Check if Firebase config variables are loaded
const isConfigured = !!process.env.NEXT_PUBLIC_FIREBASE_API_KEY;

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isConfigured || !auth) {
      // Simulation mode — guard against corrupted localStorage payloads
      try {
        const savedUser = localStorage.getItem("kairos-sim-user");
        const savedToken = localStorage.getItem("kairos-sim-token");
        if (savedUser && savedToken) {
          setUser(JSON.parse(savedUser));
          setToken(savedToken);
        }
      } catch (err) {
        console.warn("KAIROS Auth: clearing corrupted simulation session", err);
        localStorage.removeItem("kairos-sim-user");
        localStorage.removeItem("kairos-sim-token");
      }
      setLoading(false);
      return;
    }

    let refreshInterval: ReturnType<typeof setInterval> | null = null;

    // Live Firebase mode with auto-token refresh
    const unsubscribe = onIdTokenChanged(auth, async (firebaseUser) => {
      setLoading(true);
      if (firebaseUser) {
        const idToken = await firebaseUser.getIdToken(true);
        setToken(idToken);
        setUser({
          uid: firebaseUser.uid,
          email: firebaseUser.email,
          displayName: firebaseUser.displayName,
          photoURL: firebaseUser.photoURL,
          isAnonymous: firebaseUser.isAnonymous,
        });

        if (refreshInterval) clearInterval(refreshInterval);
        refreshInterval = setInterval(async () => {
          try {
            const refreshedToken = await firebaseUser.getIdToken(true);
            setToken(refreshedToken);
          } catch (err) {
            console.error("KAIROS Auth: failed to refresh token in background", err);
          }
        }, 50 * 60 * 1000);
      } else {
        setUser(null);
        setToken(null);
        if (refreshInterval) {
          clearInterval(refreshInterval);
          refreshInterval = null;
        }
      }
      setLoading(false);
    });

    return () => {
      unsubscribe();
      if (refreshInterval) clearInterval(refreshInterval);
    };
  }, []);

  const loginWithGoogle = async () => {
    setLoading(true);
    try {
      if (!isConfigured || !auth) {
        // Mock Google Login with dynamic unique UID
        const mockUid = `sim-google-uid-${Math.floor(100000 + Math.random() * 900000)}`;
        const mockUser: AuthUser = {
          uid: mockUid,
          email: "baljot@company.com",
          displayName: "Baljot Chohan",
          photoURL: null,
          isAnonymous: false,
        };
        const mockToken = `simulated-google-jwt-token-${mockUid}`;
        setUser(mockUser);
        setToken(mockToken);
        localStorage.setItem("kairos-sim-user", JSON.stringify(mockUser));
        localStorage.setItem("kairos-sim-token", mockToken);
        setLoading(false);
        return;
      }

      const provider = new GoogleAuthProvider();
      provider.setCustomParameters({ prompt: "select_account" });
      try {
        await signInWithPopup(auth, provider);
        // onIdTokenChanged will call setLoading(false); add a fallback timeout
        // in case it fires before React can flush the state update
        setTimeout(() => setLoading(false), 3000);
      } catch (popupErr: any) {
        const code = popupErr?.code ?? "";
        // Popup blocked / closed / not supported → fall back to full-page redirect
        if (
          code === "auth/popup-blocked" ||
          code === "auth/popup-closed-by-user" ||
          code === "auth/cancelled-popup-request" ||
          code === "auth/operation-not-supported-in-this-environment"
        ) {
          await signInWithRedirect(auth, provider);
          return;
        }
        throw popupErr;
      }
    } catch (error) {
      console.error("KAIROS Auth: Google login failed", error);
      setLoading(false);
      throw error;
    }
  };

  const loginAnonymously = async () => {
    setLoading(true);
    try {
      if (!isConfigured || !auth) {
        // Mock Anonymous login with dynamic unique UID
        const mockUid = `sim-guest-uid-${Math.floor(100000 + Math.random() * 900000)}`;
        const mockUser: AuthUser = {
          uid: mockUid,
          email: null,
          displayName: "Guest User",
          photoURL: null,
          isAnonymous: true,
        };
        const mockToken = `simulated-anonymous-jwt-token-${mockUid}`;
        setUser(mockUser);
        setToken(mockToken);
        localStorage.setItem("kairos-sim-user", JSON.stringify(mockUser));
        localStorage.setItem("kairos-sim-token", mockToken);
        setLoading(false);
        return;
      }

      await firebaseSignInAnonymously(auth);
    } catch (error) {
      console.error("KAIROS Auth: Guest login failed", error);
      setLoading(false);
      throw error;
    }
  };

  const logout = async () => {
    setLoading(true);
    try {
      if (!isConfigured || !auth) {
        setUser(null);
        setToken(null);
        localStorage.removeItem("kairos-sim-user");
        localStorage.removeItem("kairos-sim-token");
        setLoading(false);
        return;
      }

      await signOut(auth);
    } catch (error) {
      console.error("KAIROS Auth: Logout failed", error);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  return {
    user,
    token,
    loading,
    loginWithGoogle,
    loginAnonymously,
    logout,
    isSimulation: !isConfigured || !auth,
  };
}
