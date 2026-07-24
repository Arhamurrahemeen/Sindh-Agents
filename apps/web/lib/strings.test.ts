import { describe, expect, it } from "vitest";

import { t } from "./strings";

describe("t", () => {
  it("returns the Roman Urdu string for a key with no placeholders", () => {
    expect(t("login.title")).toBe("Login karein");
  });

  it("interpolates variables into the string", () => {
    expect(t("home.greeting", { name: "Aslam" })).toBe(
      "Assalam-o-alaikum, Aslam",
    );
  });
});
