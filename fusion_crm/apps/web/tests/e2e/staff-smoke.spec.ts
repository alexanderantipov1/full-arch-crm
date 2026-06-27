import { expect, test as base, type BrowserContext, type Page } from "@playwright/test";

const ALICE_UID = "11111111-1111-1111-1111-111111111111";

type Fixtures = {
  consoleErrors: string[];
};

const test = base.extend<Fixtures>({
  consoleErrors: [
    async ({ page }, use) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      page.on("console", (message) => {
        const text = message.text();
        if (
          message.type() === "error" &&
          !text.includes("Failed to load resource")
        ) {
          errors.push(text);
        }
      });

      await use(errors);

      expect(errors).toEqual([]);
    },
    { auto: true },
  ],
});

async function authenticate(context: BrowserContext) {
  await context.addInitScript(() => {
    window.localStorage.setItem(
      "fusion.staff_session",
      JSON.stringify({
        staff_id: "55555555-5555-5555-5555-555555555555",
        email: "demo@fusion-dental.local",
        display_name: "demo",
        expires_at: new Date(Date.now() + 8 * 3600_000).toISOString(),
      }),
    );
  });
}

async function expectStaffShell(page: Page) {
  await expect(page.getByText("Fusion CRM").first()).toBeVisible();
  await expect(page.getByRole("link", { name: /Dashboard/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Project Manager/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Leads/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Settings/ })).toBeVisible();
}

test("login page surfaces invalid credential feedback", async ({ page }) => {
  await page.goto("/login");

  await expect(page.getByText("Sign in with your staff credentials.")).toBeVisible();
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();

  await expect(page.getByText("Wrong email or password.")).toBeVisible();
});

test("dashboard opens a person detail with clinic relationship evidence", async ({
  context,
  page,
}) => {
  await authenticate(context);
  await page.goto("/dashboard");

  await expectStaffShell(page);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByText("Lead status breakdown")).toBeVisible();

  await page.getByRole("link", { name: /Alice Morgan/ }).click();
  await expect(page).toHaveURL(new RegExp(`/persons/${ALICE_UID}`));
  await expect(page.getByText("Alice Morgan").first()).toBeVisible();
  await expect(page.getByText("Clinic relationship")).toBeVisible();
  await expect(page.getByText("Fusion Dental Implants").first()).toBeVisible();
  await expect(page.getByText("consult completed", { exact: true })).toBeVisible();
  await expect(page.getByText("CS-44218").first()).toBeVisible();

  await page.getByRole("button", { name: /Identity graph/ }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "Identity graph — Alice Morgan",
  );
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
});

test("integrations page can connect and sync a mocked provider", async ({
  context,
  page,
}) => {
  await authenticate(context);
  await page.goto("/integrations");

  await expect(page.getByRole("heading", { name: "Integrations" })).toBeVisible();
  await expect(page.getByText("salesforce").first()).toBeVisible();
  await expect(page.getByText("carestack").first()).toBeVisible();

  await page.getByRole("button", { name: "Connect" }).first().click();
  await expect(page.getByText("Connected").first()).toBeVisible();

  await page.getByRole("button", { name: "Sync now" }).first().click();
  await expect(page.getByText(/2 records · success/)).toBeVisible();
});

test("tenant settings show local mock locations", async ({ context, page }) => {
  await authenticate(context);
  await page.goto("/settings/tenant?tab=locations");

  await expect(page.getByRole("heading", { name: "Tenant settings" })).toBeVisible();
  await expect(page.getByText("Fusion Dental Implants").first()).toBeVisible();
  await expect(page.getByText("Galleria Oral Surgery & Dental Implants")).toBeVisible();
  await expect(page.getByText("Practice locations sourced from CareStack")).toBeVisible();
});

test("project manager leads linked view shows paired provider rows", async ({
  context,
  page,
}) => {
  await authenticate(context);
  await page.goto("/project-manager/leads");

  await expect(page.getByRole("heading", { name: "Leads" })).toBeVisible();
  await expect(page.getByText("1 total")).toBeVisible();
  await expect(page.getByText("1–1 of 1")).toBeVisible();
  await expect(page.getByText("Linked SF + CareStack")).toBeVisible();
  await expect(page.getByText("Salesforce", { exact: true })).toBeVisible();
  await expect(page.getByText("CareStack", { exact: true })).toBeVisible();
  await expect(page.getByText("00Q-demo-2")).toBeVisible();
  await expect(page.getByText("Patient #cs-linked-demo")).toBeVisible();
  await expect(page.getByText("CS Appt:")).toBeVisible();
  await expect(page.getByText("Fusion Dental Implants · Roseville")).toBeVisible();

  await page.getByRole("button", { name: "All leads" }).click();
  await expect(page.getByText("4 total")).toBeVisible();
  await expect(page.getByText("1–4 of 4")).toBeVisible();
});
