"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ApiError,
  apiFetch,
  sendOtpResponseSchema,
  verifyOtpResponseSchema,
} from "@/lib/api";
import { t } from "@/lib/strings";

type Step = "phone" | "otp";

function resolveErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === "RATE_LIMITED") return t("login.rateLimited");
    if (err.code === "OTP_INVALID" || err.code === "OTP_EXPIRED")
      return t("login.otpError");
    if (err.code === "SME_NOT_ENROLLED") return t("login.smeNotEnrolled");
    return err.messageUrdu ?? t("login.genericError");
  }
  return t("login.genericError");
}

export default function LoginPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [resendLocked, setResendLocked] = useState(false);
  const otpInputRef = useRef<HTMLInputElement>(null);

  async function handleSendOtp(): Promise<void> {
    setError(null);
    setSubmitting(true);
    try {
      const result = await apiFetch(
        "/api/auth/send-otp",
        sendOtpResponseSchema,
        {
          method: "POST",
          body: JSON.stringify({ phone }),
        },
      );
      setStep("otp");
      setResendLocked(true);
      setTimeout(
        () => setResendLocked(false),
        result.data.resendAvailableInSeconds * 1000,
      );
      requestAnimationFrame(() => otpInputRef.current?.focus());
    } catch (err) {
      setError(resolveErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleVerifyOtp(code: string): Promise<void> {
    setError(null);
    setSubmitting(true);
    try {
      await apiFetch("/api/auth/verify-otp", verifyOtpResponseSchema, {
        method: "POST",
        body: JSON.stringify({ phone, otp: code }),
      });
      router.push("/");
      router.refresh();
    } catch (err) {
      setError(resolveErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>{t("login.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          {step === "phone" ? (
            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                void handleSendOtp();
              }}
            >
              <div className="space-y-2">
                <Label htmlFor="phone">{t("login.phonePlaceholder")}</Label>
                <Input
                  id="phone"
                  type="tel"
                  autoFocus
                  placeholder="+92 3XX XXXXXXX"
                  value={phone}
                  onChange={(e) =>
                    setPhone(e.target.value.replace(/[^\d+]/g, ""))
                  }
                />
              </div>
              {error ? (
                <p className="text-sm text-destructive">{error}</p>
              ) : null}
              <Button
                type="submit"
                disabled={submitting || phone.length === 0}
                className="w-full bg-emerald-600 hover:bg-emerald-700"
              >
                {t("login.sendOtp")}
              </Button>
            </form>
          ) : (
            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                void handleVerifyOtp(otp);
              }}
            >
              <div className="space-y-2">
                <Label htmlFor="otp">{t("login.otpPrompt")}</Label>
                <Input
                  id="otp"
                  ref={otpInputRef}
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  value={otp}
                  onChange={(e) => {
                    const next = e.target.value.replace(/\D/g, "").slice(0, 6);
                    setOtp(next);
                    if (next.length === 6) void handleVerifyOtp(next);
                  }}
                />
              </div>
              {error ? (
                <p className="text-sm text-destructive">{error}</p>
              ) : null}
              <Button
                type="submit"
                disabled={submitting || otp.length !== 6}
                className="w-full bg-emerald-600 hover:bg-emerald-700"
              >
                {t("login.submit")}
              </Button>
              <Button
                type="button"
                variant="ghost"
                disabled={resendLocked || submitting}
                onClick={() => void handleSendOtp()}
                className="w-full"
              >
                {t("login.sendOtp")}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
