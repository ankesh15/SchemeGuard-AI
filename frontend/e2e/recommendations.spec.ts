import { test, expect, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

async function questionnaire(page: Page, prefilled = false) {
  await expect(page.getByLabel("Age in years")).toBeVisible();
  if (prefilled) {
    await expect(page.getByLabel("Age in years")).toHaveValue("21");
    await expect(page.getByLabel("State or union territory")).toHaveValue(
      "Assam",
    );
  } else {
    await page.getByLabel("Age in years").fill("21");
    await page.getByLabel("State or union territory").selectOption("Assam");
  }
  await page.getByRole("button", { name: "Next", exact: true }).click();
  if (prefilled)
    await expect(page.getByLabel("Education level")).toHaveValue(
      "undergraduate",
    );
  await page.getByLabel("Education level").selectOption("undergraduate");
  await page.getByLabel("Currently a student?").selectOption("true");
  await page.getByLabel("Course or field of study").fill("Engineering");
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page.getByLabel("Occupation", { exact: true }).selectOption("student");
  await page.getByLabel("Employment status").selectOption("part_time");
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page.getByLabel("Annual family income (INR)").fill("240000");
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page.getByLabel("Scholarships and Education", { exact: true }).check();
}
async function noOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
}
for (const mobile of [false, true]) {
  test(`guest profile → PostgreSQL recommendations → detail → assessment → edit (${mobile ? "mobile" : "desktop"})`, async ({
    page,
  }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Discover Government Schemes Made for You",
    );
    await expect(page.locator(".scheme-card")).toHaveCount(0);
    await noOverflow(page);
    if (!mobile)
      await page.screenshot({
        path: test.info().outputPath("profile-first-home.png"),
        fullPage: true,
        animations: "disabled",
      });
    await page
      .getByRole("link", { name: "Find My Schemes", exact: true })
      .last()
      .click();
    await expect(page).toHaveURL(/\/find-schemes$/);
    await questionnaire(page);
    await page.getByRole("button", { name: "Find Relevant Schemes" }).click();
    await expect(page).toHaveURL(/\/schemes\/recommended$/);
    await expect(page.locator(".recommendation-card").first()).toBeVisible();
    await expect(page.locator(".recommendation-card").first()).toContainText(
      "Highly Relevant",
    );
    await expect(page.locator(".recommendation-card").first()).toContainText(
      "Why this scheme?",
    );
    await noOverflow(page);
    await page.screenshot({
      path: test
        .info()
        .outputPath(
          mobile ? "recommendations-mobile.png" : "recommendations-desktop.png",
        ),
      fullPage: true,
    });
    const name = await page
      .locator(".recommendation-card h3")
      .first()
      .innerText();
    await page
      .getByRole("link", { name: "View Details", exact: true })
      .first()
      .click();
    await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Why this was recommended" }),
    ).toBeVisible();
    await page
      .getByRole("link", { name: "Check Eligibility", exact: true })
      .click();
    await expect(page.getByLabel("Age", { exact: true })).toHaveValue("21");
    await expect(page.getByLabel("Annual family income (INR)")).toHaveValue(
      "240000",
    );
    await page
      .getByRole("button", { name: "Check Eligibility", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Criteria matched", exact: true }),
    ).toBeVisible();
    await expect(page.locator("body")).toContainText(
      "do not determine government eligibility",
    );
    await page
      .getByRole("link", { name: "Back to recommendations", exact: true })
      .click();
    await expect(page.locator(".recommendation-card").first()).toBeVisible();
    await page.getByRole("link", { name: "Edit Details", exact: true }).click();
    await expect(page.getByLabel("Age in years")).toHaveValue("21");
    expect(
      await page.evaluate(() => localStorage.length + sessionStorage.length),
    ).toBe(0);
    expect(page.url()).not.toMatch(/240000|Assam|age=/);
    expect(pageErrors).toEqual([]);
  });
  test(`citizen saved profile is prefilled, saved by consent, reused on dashboard and cleared on logout (${mobile ? "mobile" : "desktop"})`, async ({
    page,
  }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    const username = "rec_e2e_" + randomUUID().replaceAll("-", "").slice(0, 12);
    const password = "Synthetic-only-" + randomUUID();
    await page.goto("/register");
    await page.getByLabel("Username", { exact: true }).fill(username);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByLabel("Confirm password").fill(password);
    await page
      .getByRole("button", { name: "Create account", exact: true })
      .click();
    await expect(page).toHaveURL(/\/dashboard$/);
    const origin = new URL(page.url()).origin;
    try {
      // Use the existing private API to establish a profile, then verify all UI handoffs.
      const session = await (await page.request.get("/api/account/me")).json();
      const saved = await page.request.put("/api/account/profiles/me", {
        headers: { Origin: origin, "X-CSRF-Token": session.csrf_token },
        data: {
          age_years: 21,
          state: "Assam",
          course_level: "undergraduate",
          current_student: true,
          interests: ["education"],
        },
      });
      expect(saved.status()).toBe(200);
      await page.goto("/find-schemes");
      await questionnaire(page, true);
      await page
        .getByLabel("Save these changes to my private encrypted profile")
        .check();
      await page.getByRole("button", { name: "Find Relevant Schemes" }).click();
      await expect(page.locator(".recommendation-card").first()).toBeVisible();
      const own = await (
        await page.request.get("/api/account/profiles/me")
      ).json();
      expect(own.profile.interests).toContain("education");
      expect(own.profile.employment_status).toBe("part_time");
      await page
        .getByRole("link", { name: "View Details", exact: true })
        .first()
        .click();
      await page
        .getByRole("link", { name: "Check Eligibility", exact: true })
        .click();
      await expect(page.getByLabel("Age", { exact: true })).toHaveValue("21");
      await page
        .getByRole("button", { name: "Check Eligibility", exact: true })
        .click();
      await expect(
        page.getByRole("heading", { name: "Criteria matched", exact: true }),
      ).toBeVisible();
      await page.goto("/schemes");
      await expect(page).toHaveURL(/\/schemes\/recommended$/);
      await expect(page.locator(".recommendation-card").first()).toBeVisible();
      await page.goto("/dashboard");
      await expect(
        page.getByRole("heading", { name: "Recommended schemes for you" }),
      ).toBeVisible();
      await expect(page.locator(".recommendation-card").first()).toBeVisible();
      await noOverflow(page);
      await page
        .getByRole("link", { name: "Find Schemes for Me", exact: true })
        .click();
      await expect(page.getByLabel("Age in years")).toHaveValue("21");
      await page.goto("/dashboard");
      await page.getByRole("button", { name: "Sign out", exact: true }).click();
      await expect(page).toHaveURL(/\/login$/);
      await page.goto("/schemes");
      await expect(page).toHaveURL(/\/find-schemes$/);
      await expect(page.getByLabel("Age in years")).toHaveValue("");
    } finally {
      const login = await page.request.post("/api/account/auth/login", {
        headers: { Origin: origin },
        data: { username, password },
      });
      if (login.ok()) {
        const own = await login.json();
        const removed = await page.request.delete("/api/account/me", {
          headers: { Origin: origin, "X-CSRF-Token": own.csrf_token },
          data: { current_password: password, acknowledge_deletion: true },
        });
        expect(removed.status()).toBe(204);
      }
    }
  });
}
