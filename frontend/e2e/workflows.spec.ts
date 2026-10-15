import { test, expect, type Page } from "@playwright/test";
async function login(page: Page, role: string) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(`${role}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("LearnSphere2026!");
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(
    page.getByRole("heading", { name: /Welcome back/ }),
  ).toBeVisible();
}
async function logout(page: Page) {
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Continue your journey" }),
  ).toBeVisible();
}
test("complete administrator, faculty and learner workflow", async ({
  page,
}) => {
  page.on("dialog", (dialog) => dialog.accept());
  await login(page, "admin");
  await page.getByRole("link", { name: "People", exact: true }).click();
  for (const role of ["instructor", "student"]) {
    await page.getByRole("button", { name: "Add person" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Full name").fill(`E2E ${role}`);
    await dialog.getByLabel("Email address").fill(`e2e-${role}@example.com`);
    await dialog.getByLabel("Role", { exact: true }).selectOption(role);
    await dialog.getByLabel("Initial password").fill("LearnSphere2026!");
    await dialog.getByRole("button", { name: "Create account" }).click();
    await expect(dialog).not.toBeVisible();
  }
  await logout(page);
  await login(page, "e2e-instructor");
  await page.getByRole("link", { name: "Create a course" }).click();
  await page.getByLabel("Course title").fill("E2E Secure Software");
  await page.getByLabel("URL slug").fill("e2e-secure-software");
  await page
    .getByLabel("Description", { exact: true })
    .fill("Build secure software with verified permissions.");
  await page
    .getByLabel("Learning objectives")
    .fill("Explain and apply tenant isolation.");
  await page.getByRole("button", { name: "Create draft" }).click();
  await expect(
    page.getByRole("heading", { name: "E2E Secure Software" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Section", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByLabel("Section title")
    .fill("Getting started");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Save changes" })
    .click();
  await page.getByRole("button", { name: "Lesson", exact: true }).click();
  let dialog = page.getByRole("dialog");
  await dialog.getByLabel("Lesson title").fill("Authorization boundaries");
  await dialog
    .getByLabel("Section", { exact: true })
    .selectOption({ label: "Getting started" });
  await dialog
    .getByLabel("Lesson content")
    .fill(
      "Always enforce permissions and institution isolation on the server.",
    );
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole("tab", { name: "assessments", exact: true }).click();
  await page.getByRole("button", { name: "Add question", exact: true }).click();
  dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Question", { exact: true })
    .fill("Where must access checks run?");
  await dialog.getByLabel("Option 1", { exact: true }).fill("On the server");
  await dialog
    .getByLabel("Option 2", { exact: true })
    .fill("Only in the browser");
  await dialog.getByRole("button", { name: "Save question" }).click();
  await page.getByRole("button", { name: "Quiz", exact: true }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Quiz title").fill("Security knowledge");
  await dialog
    .getByRole("checkbox", { name: /Where must access checks run/ })
    .check();
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await page.getByRole("button", { name: "Assignment", exact: true }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Assignment title").fill("Secure endpoint design");
  await dialog
    .getByLabel("Instructions")
    .fill("Describe how your endpoint enforces tenant ownership.");
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await page
    .getByRole("button", { name: "Submit for review", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Publish course", exact: true })
    .click();
  await expect(
    page.getByText("published", { exact: true }).first(),
  ).toBeVisible();
  const courseUrl = page.url();
  await logout(page);
  await login(page, "e2e-student");
  await page.goto(courseUrl);
  await page.getByRole("button", { name: "Enroll in course" }).click();
  await page.getByRole("link", { name: "Continue learning" }).click();
  await expect(
    page.getByText(
      "Always enforce permissions and institution isolation on the server.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Mark lesson complete" }).click();
  await expect(page.getByText("100% complete")).toBeVisible();
  await page.getByRole("link", { name: "Assessments & discussions" }).click();
  await page.getByRole("tab", { name: "assessments", exact: true }).click();
  await page.getByRole("button", { name: "Start / resume" }).click();
  await page.getByRole("radio", { name: "On the server" }).check();
  await page.getByRole("button", { name: "Submit attempt" }).click();
  await expect(page.getByText("Released result")).toBeVisible();
  await expect(page.getByText("1 / 1", { exact: true })).toBeVisible();
  await page.goto(courseUrl);
  await page.getByRole("tab", { name: "assessments", exact: true }).click();
  await page.getByRole("button", { name: "Submit work" }).click();
  dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Your response")
    .fill(
      "Authenticate, resolve membership, verify course assignment, then enforce the business rule.",
    );
  await dialog.getByRole("button", { name: "Submit assignment" }).click();
  await expect(dialog).not.toBeVisible();
  await logout(page);
  await login(page, "e2e-instructor");
  await page.goto(courseUrl);
  await page.getByRole("tab", { name: "assessments", exact: true }).click();
  await page.getByRole("button", { name: "Grade submission" }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel(/Total marks/).fill("95");
  await dialog
    .getByLabel("Feedback", { exact: true })
    .fill("Clear explanation of scope checks.");
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).not.toBeVisible();
  await logout(page);
  await login(page, "e2e-student");
  await page.goto(courseUrl);
  await page.getByRole("tab", { name: "assessments", exact: true }).click();
  await expect(page.getByText("95 marks")).toBeVisible();
  await expect(
    page.getByText("Clear explanation of scope checks."),
  ).toBeVisible();
  await page.getByRole("link", { name: "Continue learning" }).click();
  await page.getByRole("button", { name: "Issue my certificate" }).click();
  await page.getByRole("link", { name: "View certificates" }).click();
  await expect(
    page.getByRole("heading", { name: "E2E Secure Software" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "People", exact: true }),
  ).toHaveCount(0);
  await page.goto("/users");
  await expect(
    page.getByText("Your role does not have access to this area."),
  ).toBeVisible();
});
test("responsive navigation and real API-backed dashboard render without overflow", async ({
  page,
}) => {
  await login(page, "student");
  await expect(page.getByText("Learning momentum")).toBeVisible();
  await page.screenshot({
    path: "test-results/dashboard-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("button", { name: "Open navigation" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "Course catalog", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "A world of learning" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await expect
    .poll(() =>
      page
        .locator(".sidebar")
        .evaluate((el) => Math.round(el.getBoundingClientRect().right)),
    )
    .toBeLessThanOrEqual(0);
  await page.screenshot({
    path: "test-results/catalog-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
});
