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
  "home.agentsTitle": { ur: "Aap ke agents", en: "Your agents" },
  "home.agentStatus.live": {
    ur: "Kaam kar raha hai",
    en: "Currently active",
  },
  "home.agentStatus.paused": { ur: "Ruka hua hai", en: "Paused" },
  "home.recentConvos": {
    ur: "Haal hi ki baat cheet",
    en: "Recent conversations",
  },
  "home.viewAll": { ur: "Sab dekhein →", en: "View all →" },
  "home.msgsToday": { ur: "{n} messages aaj", en: "{n} messages today" },
  "header.logout": { ur: "Logout", en: "Log out" },
  "convos.searchPlaceholder": {
    ur: "Buyer ka naam ya number dhundein",
    en: "Search by buyer name or number",
  },
  "convos.tabAll": { ur: "Sab", en: "All" },
  "convos.tabUnread": { ur: "Naye", en: "Unread" },
  "convos.tabFlagged": { ur: "Nishaan lagaye hue", en: "Flagged" },
  "convos.empty": {
    ur: "Koi conversation nahi mila.",
    en: "No conversations found.",
  },
  "convos.flagAction": { ur: "Nishaan lagayein", en: "Flag" },
  "convos.unflagAction": { ur: "Nishaan hatayein", en: "Unflag" },
  "convos.flaggedBadge": { ur: "Nishaan lagaya gaya", en: "Flagged" },
  "convo.agentPill": {
    ur: "Agent: {agentNameUrdu}",
    en: "Agent: {agentNameUrdu}",
  },
  "convo.auditTooltip": {
    ur: "Yeh jawaab kaise bana?",
    en: "How was this reply made?",
  },
  "convo.readOnlyBanner": {
    ur: "Aap yahan se reply nahi kar sakte. Agent khud kar raha hai.",
    en: "You can't reply from here. The agent handles this itself.",
  },
  "convo.empty": {
    ur: "Buyer ne abhi tak message nahi bheja.",
    en: "Buyer hasn't messaged yet.",
  },
  "audit.title": {
    ur: "Yeh jawaab kaise bana?",
    en: "How was this reply made?",
  },
  "audit.understanding": {
    ur: "Agent ne yeh samjha: {parsedIntent}",
    en: "The agent understood: {parsedIntent}",
  },
  "audit.toolsTitle": { ur: "Tools istemaal hue", en: "Tools called" },
  "audit.replyTitle": { ur: "Agent ka jawaab", en: "Agent's reply" },
  "audit.timingTitle": { ur: "Waqt lagaya", en: "Time taken" },
  "audit.modelTitle": { ur: "Model istemaal hua", en: "Model used" },
  "audit.flagButton": {
    ur: "Yeh galat lag raha hai? Nishan lagayein",
    en: "Does this look wrong? Flag it",
  },
  "audit.notFound": {
    ur: "Audit record nahi mila.",
    en: "Audit record not found.",
  },
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
