import { describe, expect, it } from "vitest";
import {
  providerUrlBasesFromTenantSettings,
  providerUrlFor,
} from "@/lib/integrations/providerUrls";

describe("providerUrlFor", () => {
  it("synthesizes a Salesforce Lightning URL for a Lead", () => {
    const url = providerUrlFor("salesforce", "Lead", "00Q5j000001abcd");
    expect(url).toBe(
      "https://login.salesforce.com/lightning/r/Lead/00Q5j000001abcd/view",
    );
  });

  it("uses the configured Salesforce Lightning base URL", () => {
    const url = providerUrlFor("salesforce", "lead", "00Q5j000001abcd", {
      salesforceLightningBaseUrl:
        "https://fusiondentalimplants.lightning.force.com/",
    });
    expect(url).toBe(
      "https://fusiondentalimplants.lightning.force.com/lightning/r/Lead/00Q5j000001abcd/view",
    );
  });

  it("synthesizes a Salesforce URL for a Contact", () => {
    const url = providerUrlFor("salesforce", "Contact", "003ABC");
    expect(url).toBe(
      "https://login.salesforce.com/lightning/r/Contact/003ABC/view",
    );
  });

  it("falls back to the raw entity name for unknown SF entity kinds", () => {
    const url = providerUrlFor("salesforce", "CustomThing__c", "abc");
    expect(url).toBe(
      "https://login.salesforce.com/lightning/r/CustomThing__c/abc/view",
    );
  });

  it("synthesizes a CareStack URL for a Patient", () => {
    const url = providerUrlFor("carestack", "Patient", "PT-9985");
    expect(url).toBe("https://app.carestack.com/patient/PT-9985");
  });

  it("uses the configured CareStack app base URL", () => {
    const url = providerUrlFor("carestack", "patient", "PT-9985", {
      carestackAppBaseUrl: "https://antipov.carestack.com/",
    });
    expect(url).toBe("https://antipov.carestack.com/patient/PT-9985");
  });

  it("synthesizes a CareStack URL for an Appointment", () => {
    const url = providerUrlFor("carestack", "Appointment", "APT-42");
    expect(url).toBe("https://app.carestack.com/appointment/APT-42");
  });

  it("encodes special characters in the external id", () => {
    const url = providerUrlFor("salesforce", "Lead", "id with spaces");
    expect(url).toBe(
      "https://login.salesforce.com/lightning/r/Lead/id%20with%20spaces/view",
    );
  });

  it("returns null for providers without a deep-link pattern (hubspot)", () => {
    expect(providerUrlFor("hubspot", "Contact", "1")).toBeNull();
  });

  it("returns null for OAuth-only mailbox providers", () => {
    expect(providerUrlFor("google_workspace", "Mailbox", "x")).toBeNull();
    expect(providerUrlFor("microsoft_365", "Mailbox", "x")).toBeNull();
  });

  it("returns null for entirely unknown providers", () => {
    expect(providerUrlFor("vapi", "Contact", "x")).toBeNull();
  });

  it("extracts provider link bases from tenant settings", () => {
    const bases = providerUrlBasesFromTenantSettings([
      {
        key: "provider_link_bases",
        value: {
          salesforce_lightning_base_url:
            "https://fusiondentalimplants.lightning.force.com",
          carestack_app_base_url: "https://antipov.carestack.com",
        },
      },
    ]);

    expect(bases).toEqual({
      salesforceLightningBaseUrl:
        "https://fusiondentalimplants.lightning.force.com",
      carestackAppBaseUrl: "https://antipov.carestack.com",
    });
  });
});
