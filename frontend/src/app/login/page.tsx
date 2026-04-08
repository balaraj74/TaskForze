"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signInWithPopup,
} from "firebase/auth";
import { auth, googleProvider } from "@/lib/firebase";
import { useAuth } from "@/components/AuthProvider";
import { Mail, ShieldAlert } from "lucide-react";
import Image from "next/image";

function formatAuthError(err: unknown) {
  const message = err instanceof Error ? err.message : "Failed to sign in";
  const normalized = message.toLowerCase();
  const code =
    typeof err === "object" && err && "code" in err && typeof err.code === "string"
      ? err.code
      : "";

  if (normalized.includes("invalid_client") || normalized.includes("oauth client was invalid")) {
    const domain = typeof window !== "undefined" ? window.location.hostname : "this app domain";
    return `Google sign-in is misconfigured for this Firebase project. Re-enable the Google provider in Firebase Authentication, verify the linked OAuth web client in Google Cloud Credentials, and add ${domain} to Firebase Authentication > Settings > Authorized domains.`;
  }

  if (normalized.includes("unauthorized-domain")) {
    const domain = typeof window !== "undefined" ? window.location.hostname : "this app domain";
    return `This domain is not authorized for Firebase sign-in yet. Add ${domain} in Firebase Authentication > Settings > Authorized domains and try again.`;
  }

  if (code === "auth/operation-not-allowed") {
    return "This sign-in method is not enabled yet. Turn on Email/Password in Firebase Authentication > Sign-in method and try again.";
  }

  if (code === "auth/invalid-email") {
    return "Enter a valid email address.";
  }

  if (code === "auth/email-already-in-use") {
    return "An account with this email already exists. Try signing in instead.";
  }

  if (code === "auth/user-not-found" || code === "auth/wrong-password" || code === "auth/invalid-credential") {
    return "Incorrect email or password.";
  }

  if (code === "auth/weak-password") {
    return "Use a stronger password with at least 6 characters.";
  }

  if (code === "auth/too-many-requests") {
    return "Too many login attempts. Please wait a moment and try again.";
  }

  if (code === "auth/popup-closed-by-user") {
    return "Google sign-in was closed before it finished.";
  }

  return message;
}

export default function LoginPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) {
      router.replace("/");
    }
  }, [user, loading, router]);

  const resetError = () => {
    if (error) setError(null);
  };

  const handleEmailAuth = async () => {
    const trimmedEmail = email.trim();

    if (!trimmedEmail || !password) {
      setError("Enter your email and password.");
      return;
    }

    if (mode === "signup" && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);

      if (mode === "signup") {
        await createUserWithEmailAndPassword(auth, trimmedEmail, password);
      } else {
        await signInWithEmailAndPassword(auth, trimmedEmail, password);
      }
    } catch (err) {
      setError(formatAuthError(err));
      setIsSubmitting(false);
    }
  };

  const handleGoogleSignIn = async () => {
    try {
      setIsSubmitting(true);
      setError(null);
      await signInWithPopup(auth, googleProvider);
      // Successful sign in will trigger the useEffect above to redirect
    } catch (err) {
      setError(formatAuthError(err));
      setIsSubmitting(false);
    }
  };

  if (loading || user) {
    return null; // Will redirect or show loading in AuthGuard if used there
  }

  return (
    <div className="flex h-screen w-full flex-col items-center justify-center bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-[#1d1b32] via-[#0b0c10] to-[#0b0c10] text-[#e2e8f0]">
      <div className="w-full max-w-md px-8 text-center mt-[-10vh]">
        <div className="mb-8 flex justify-center">
          <div className="relative h-28 w-28 drop-shadow-[0_0_40px_rgba(123,97,255,0.4)]">
            <Image src="/logo.png" alt="TaskForze Logo" fill priority className="object-contain" />
          </div>
        </div>

        <h1 className="mb-3 text-4xl font-bold tracking-tight text-white">
          TaskForze
        </h1>
        <p className="mb-10 text-lg leading-relaxed text-[#94a3b8]">
          Your personal AI workforce. Delegate tasks, orchestrate workflows, and 
          multiply your productivity.
        </p>

        <div className="mb-6 grid grid-cols-2 rounded-2xl border border-white/10 bg-white/5 p-1">
          <button
            type="button"
            onClick={() => {
              setMode("signin");
              setError(null);
            }}
            className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
              mode === "signin" ? "bg-white text-black" : "text-[#94a3b8] hover:text-white"
            }`}
          >
            Sign in
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("signup");
              setError(null);
            }}
            className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
              mode === "signup" ? "bg-white text-black" : "text-[#94a3b8] hover:text-white"
            }`}
          >
            Create account
          </button>
        </div>

        {error && (
          <div className="mb-6 flex items-start gap-3 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-left text-sm text-rose-200">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
            <span className="leading-relaxed">{error}</span>
          </div>
        )}

        <div className="mb-4 space-y-4 text-left">
          <div>
            <label htmlFor="email" className="mb-2 block text-sm font-medium text-[#cbd5e1]">
              Email
            </label>
            <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 backdrop-blur-md">
              <Mail className="h-4 w-4 shrink-0 text-[#94a3b8]" />
              <input
                id="email"
                type="email"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  resetError();
                }}
                placeholder="you@example.com"
                className="w-full bg-transparent text-white outline-none placeholder:text-[#64748b]"
              />
            </div>
          </div>

          <div>
            <label htmlFor="password" className="mb-2 block text-sm font-medium text-[#cbd5e1]">
              Password
            </label>
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 backdrop-blur-md">
              <input
                id="password"
                type="password"
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                  resetError();
                }}
                placeholder={mode === "signup" ? "Create a password" : "Enter your password"}
                className="w-full bg-transparent text-white outline-none placeholder:text-[#64748b]"
              />
            </div>
          </div>

          {mode === "signup" && (
            <div>
              <label htmlFor="confirmPassword" className="mb-2 block text-sm font-medium text-[#cbd5e1]">
                Confirm password
              </label>
              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 backdrop-blur-md">
                <input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => {
                    setConfirmPassword(event.target.value);
                    resetError();
                  }}
                  placeholder="Re-enter your password"
                  className="w-full bg-transparent text-white outline-none placeholder:text-[#64748b]"
                />
              </div>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={handleEmailAuth}
          disabled={isSubmitting}
          className="mb-4 flex w-full items-center justify-center rounded-2xl bg-gradient-to-r from-[#7b61ff] to-[#24d4ff] px-6 py-4 text-base font-semibold text-white transition-transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-70 disabled:hover:scale-100"
        >
          {isSubmitting ? "Please wait..." : mode === "signup" ? "Create account" : "Sign in with email"}
        </button>

        <div className="mb-4 flex items-center gap-4 text-xs uppercase tracking-[0.28em] text-[#64748b]">
          <div className="h-px flex-1 bg-white/10" />
          <span>Or</span>
          <div className="h-px flex-1 bg-white/10" />
        </div>

        <button
          onClick={handleGoogleSignIn}
          disabled={isSubmitting}
          className="group relative flex w-full items-center justify-center gap-3 overflow-hidden rounded-2xl bg-white px-6 py-4 text-base font-medium text-black transition-transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-70 disabled:hover:scale-100"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/50 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
          {isSubmitting ? (
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-black border-r-transparent" />
          ) : (
            <svg className="h-5 w-5" viewBox="0 0 24 24">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                fill="#EA4335"
              />
            </svg>
          )}
          <span>{isSubmitting ? "Signing in..." : "Continue with Google"}</span>
        </button>

        <p className="mt-8 text-sm text-[#47516b]">
          Secured by Firebase Authentication
        </p>
      </div>
    </div>
  );
}
