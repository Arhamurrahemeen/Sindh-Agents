export const strings = {
  "login.title": { ur: "Login karein", en: "Log in" },
  "login.phonePlaceholder": {
    ur: "Phone number daalein",
    en: "Enter phone number",
  },
  "login.otpPrompt": {
    ur: "OTP daalein (SMS pe aaya hai)",
    en: "Enter OTP (sent via SMS)",
  },
  "login.sendOtp": { ur: "OTP bhejain", en: "Send OTP" },
  "login.submit": { ur: "Login karein", en: "Log in" },
  "login.otpError": {
    ur: "OTP galat hai. Dobara try karein.",
    en: "Wrong OTP. Try again.",
  },
  "login.rateLimited": {
    ur: "Ek minute rukein, phir try karein.",
    en: "Wait a minute, then retry.",
  },
  "login.smeNotEnrolled": {
    ur: "Yeh number register nahi hai.",
    en: "This number isn't registered.",
  },
  "login.genericError": {
    ur: "Kuch ghalat ho gaya. Dobara try karein.",
    en: "Something went wrong. Try again.",
  },
  "home.greeting": { ur: "Assalam-o-alaikum, {name}", en: "Hello, {name}" },
  "home.noAgents": { ur: "Abhi tak koi agent nahi.", en: "No agents yet." },
  "header.logout": { ur: "Logout", en: "Log out" },
  "widget.greeting": {
    ur: "Assalam-o-alaikum! Kya madad chahiye?",
    en: "Hello! How can we help?",
  },
  "widget.namePrompt": { ur: "Aap ka naam?", en: "Your name?" },
  "widget.nameSubmit": { ur: "Shuru karein", en: "Start" },
  "widget.placeholder": { ur: "Message likhein...", en: "Type a message..." },
  "widget.send": { ur: "Bhejein", en: "Send" },
  "widget.offlineError": {
    ur: "Server abhi busy hai, thodi der mein try karein.",
    en: "Server is busy right now, try again shortly.",
  },
} as const;

export type StringKey = keyof typeof strings;

export function t(key: StringKey, vars?: Record<string, string>): string {
  const value: string = strings[key].ur;
  if (!vars) return value;
  return Object.entries(vars).reduce(
    (acc: string, [name, replacement]) =>
      acc.replaceAll(`{${name}}`, replacement),
    value,
  );
}
