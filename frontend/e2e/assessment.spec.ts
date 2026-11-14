import { test, expect } from "@playwright/test";

test("government scheme selection leads to explainable PASS, UNKNOWN and FAIL demonstration results", async ({
  page,
}) => {
  await page.goto("/eligibility");
  await expect(
    page.getByRole("heading", { name: "Choose your starting point." }),
  ).toBeVisible();
  await page.getByLabel("Search schemes").fill("AICTE");
  await expect(page.locator(".scheme-card").first()).toContainText("AICTE");
  const selected = await page.locator(".scheme-card h2").first().innerText();
  await page
    .getByRole("link", { name: /^Assess / })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { level: 1, name: selected }),
  ).toBeVisible();
  await expect(page.getByLabel("Education level")).toBeVisible();
  await page.getByRole("button", { name: "Use Sample Details" }).click();
  await page
    .getByRole("button", { name: "Check Eligibility", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Criteria matched", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".report-page-heading")).toContainText(selected);
  await expect(page.locator("body")).not.toContainText(
    /fictional|synthetic|invented/i,
  );
  await expect(
    page.getByText("Project-authored illustration", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".evidence-quote")).toHaveCount(0);
  await page.screenshot({
    path: test.info().outputPath("illustrative-report.png"),
    fullPage: true,
  });
  await expect(
    page.getByText(/not supporting evidence for the illustrative criteria/),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Start a new check", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Check Eligibility", exact: true })
    .click();
  await expect(
    page
      .getByRole("heading", { name: "Additional information required" })
      .first(),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Start a new check", exact: true })
    .click();
  await page.getByRole("button", { name: "Use Sample Details" }).click();
  // 15 is a failing value for our authored template, not a government age rule.
  await page.getByLabel("Age", { exact: true }).fill("15");
  await page
    .getByRole("button", { name: "Check Eligibility", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Criteria not matched", exact: true }),
  ).toBeVisible();
});

test("mobile category selection asks relevant housing questions", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/eligibility");
  await page
    .getByRole("combobox", { name: "Category", exact: true })
    .selectOption("housing");
  await expect(page.locator(".scheme-card .eyebrow").first()).toHaveText(
    "Housing",
  );
  await page
    .getByRole("link", { name: /^Assess / })
    .first()
    .click();
  await expect(page.getByLabel("Already own a home?")).toBeVisible();
  await expect(page.getByLabel("Education level")).toHaveCount(0);
  await page.getByRole("button", { name: "Use Sample Details" }).click();
  await page
    .getByRole("button", { name: "Check Eligibility", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Criteria matched", exact: true }),
  ).toBeVisible();
  await expect(page.locator("body")).toHaveJSProperty(
    "scrollWidth",
    await page.locator("body").evaluate((element) => element.clientWidth),
  );
});

test("a category without a suitable template stays explicitly unsupported", async ({
  page,
}) => {
  await page.goto("/eligibility");
  await page
    .getByRole("combobox", { name: "Category", exact: true })
    .selectOption("transport");
  await expect(page.locator(".scheme-card .eyebrow").first()).toHaveText(
    "Transport",
  );
  await page
    .getByRole("link", { name: /^Assess / })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Assessment not available yet." }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Check Eligibility", exact: true }),
  ).toHaveCount(0);
});
