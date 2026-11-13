import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
test("synthetic citizen can register, save a reproducible fictional report and sign out", async ({
  page,
}) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
  await page.getByRole("link", { name: "Create a citizen account" }).click();
  await expect(
    page.getByRole("heading", { name: "Create your private workspace." }),
  ).toBeVisible();
  const username = "e2e_" + randomUUID().replaceAll("-", "").slice(0, 12);
  await page.getByLabel("Username", { exact: true }).fill(username);
  const password = "Synthetic-E2E-only-" + randomUUID();
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.getByRole("link", { name: "Profile", exact: true }).click();
  await page.getByLabel("State or union territory").selectOption("Assam");
  await page.getByLabel("Age in years").fill("21");
  await page.getByLabel("Annual family income (INR)").fill("240000");
  await page.getByRole("button", { name: "Save private profile" }).click();
  await expect(page.getByRole("status")).toContainText("was saved");
  await page.getByRole("link", { name: "Assessments", exact: true }).click();
  await page
    .getByRole("link", { name: "Create an assessment", exact: true })
    .click();
  await expect(
    page.getByText("Fictional development policy.", { exact: false }),
  ).toBeVisible();
  // Leave scheme-specific fields unknown; absence must stay UNKNOWN, never default to PASS.
  await page.getByRole("button", { name: "Evaluate & save privately" }).click();
  await expect(page).toHaveURL(/\/dashboard\/assessments\/[0-9a-f-]{36}$/);
  await expect(
    page.getByText("More information required", { exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Verify reproducibility" }).click();
  await expect(page.getByRole("status")).toContainText("matched the original");
  await page.getByRole("link", { name: "Notifications", exact: true }).click();
  await expect(
    page.getByText("No notifications here.", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/dashboard/assessments");
  await expect(page).toHaveURL(/\/login$/);
  // Remove only this test's newly created synthetic account through its own UI.
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page
    .getByLabel("Current password (required for account changes)")
    .fill(password);
  await page
    .getByLabel("I understand that my private data will be deleted.")
    .check();
  await page
    .getByRole("button", { name: "Delete account and private data" })
    .click();
  await expect(page).toHaveURL(/\/login$/);
});

test("explorer remains usable at mobile size and metadata cannot fabricate eligibility", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/schemes");
  await expect(
    page.getByRole("heading", {
      name: "Find a place to start.",
      exact: false,
    }),
  ).toBeVisible();
  await expect(page.getByText("Discovery metadata only").first()).toBeVisible();
  await expect(page.locator("body")).toHaveJSProperty(
    "scrollWidth",
    await page.locator("body").evaluate((element) => element.clientWidth),
  );
  const response = await page.request.post("/api/account/assessments", {
    data: {},
  });
  expect([401, 403]).toContain(response.status());
});
