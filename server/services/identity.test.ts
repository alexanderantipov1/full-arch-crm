import { describe, it, expect, vi, beforeEach } from "vitest";

const storageMock = vi.hoisted(() => ({
  findPersonByEmail: vi.fn(),
  findPersonByPhone: vi.fn(),
  findPersonByNameDob: vi.fn(),
  findPersonByExternalId: vi.fn(),
  getPerson: vi.fn(),
  createPerson: vi.fn(),
  setPersonMergedInto: vi.fn(),
  linkPersonExternalId: vi.fn().mockResolvedValue({}),
}));

vi.mock("../storage", () => ({ storage: storageMock }));

import {
  resolveOrCreatePerson,
  mergePersons,
  normalizeEmail,
  normalizePhone,
  getPerson,
  linkExternalId,
  findPersonByExternalId,
} from "./identity";

beforeEach(() => {
  vi.clearAllMocks();
  storageMock.linkPersonExternalId.mockResolvedValue({});
});

describe("normalizeEmail", () => {
  it("trims and lowercases", () => {
    expect(normalizeEmail("  Jane@Example.COM ")).toBe("jane@example.com");
  });
  it("returns null for empty or whitespace-only", () => {
    expect(normalizeEmail("")).toBeNull();
    expect(normalizeEmail("   ")).toBeNull();
    expect(normalizeEmail(null)).toBeNull();
    expect(normalizeEmail(undefined)).toBeNull();
  });
});

describe("normalizePhone", () => {
  it("strips non-digit characters", () => {
    expect(normalizePhone("(415) 555-1234")).toBe("4155551234");
    expect(normalizePhone("+1.415.555.1234")).toBe("14155551234");
  });
  it("returns null when no digits", () => {
    expect(normalizePhone("")).toBeNull();
    expect(normalizePhone("---")).toBeNull();
    expect(normalizePhone(null)).toBeNull();
  });
});

describe("resolveOrCreatePerson — matching order", () => {
  it("matches by email first (normalized) and returns via='email'", async () => {
    storageMock.findPersonByEmail.mockResolvedValueOnce({ id: "p1", mergedIntoId: null });

    const result = await resolveOrCreatePerson({
      email: "  Jane@Example.COM ",
      phone: "(415) 555-1234",
      source: "intake",
    });

    expect(result.via).toBe("email");
    expect(result.person.id).toBe("p1");
    // Email was normalized before lookup.
    expect(storageMock.findPersonByEmail).toHaveBeenCalledWith("jane@example.com");
    // Phone was never checked because email already matched.
    expect(storageMock.findPersonByPhone).not.toHaveBeenCalled();
    expect(storageMock.createPerson).not.toHaveBeenCalled();
  });

  it("falls through to phone (normalized) when email doesn't match", async () => {
    storageMock.findPersonByEmail.mockResolvedValueOnce(undefined);
    storageMock.findPersonByPhone.mockResolvedValueOnce({ id: "p2", mergedIntoId: null });

    const result = await resolveOrCreatePerson({
      email: "new@example.com",
      phone: "+1 (415) 555-1234",
      source: "lead",
    });

    expect(result.via).toBe("phone");
    expect(result.person.id).toBe("p2");
    expect(storageMock.findPersonByPhone).toHaveBeenCalledWith("14155551234");
  });

  it("falls through to name+DOB when email and phone don't match", async () => {
    storageMock.findPersonByEmail.mockResolvedValueOnce(undefined);
    storageMock.findPersonByPhone.mockResolvedValueOnce(undefined);
    storageMock.findPersonByNameDob.mockResolvedValueOnce({ id: "p3", mergedIntoId: null });

    const result = await resolveOrCreatePerson({
      firstName: "Jane",
      lastName: "Doe",
      dateOfBirth: "1960-01-01",
      email: "new@example.com",
      phone: "5559999",
      source: "intake",
    });

    expect(result.via).toBe("name_dob");
    expect(storageMock.findPersonByNameDob).toHaveBeenCalledWith("Jane", "Doe", "1960-01-01");
  });

  it("creates a new person when nothing matches, with the right source provenance", async () => {
    storageMock.findPersonByEmail.mockResolvedValueOnce(undefined);
    storageMock.findPersonByPhone.mockResolvedValueOnce(undefined);
    storageMock.findPersonByNameDob.mockResolvedValueOnce(undefined);
    storageMock.createPerson.mockResolvedValueOnce({ id: "new-uuid", mergedIntoId: null });

    const result = await resolveOrCreatePerson({
      firstName: "Brand",
      lastName: "New",
      dateOfBirth: "1990-05-05",
      email: "brand.new@example.com",
      phone: "(555) 999-8888",
      source: "carestack",
    });

    expect(result.via).toBe("created");
    expect(result.person.id).toBe("new-uuid");
    const createArgs = storageMock.createPerson.mock.calls[0][0];
    expect(createArgs).toMatchObject({
      firstName: "Brand",
      lastName: "New",
      dateOfBirth: "1990-05-05",
      email: "brand.new@example.com",
      phone: "5559998888",
      firstSeenSource: "carestack",
    });
  });

  it("skips email lookup when no email is given", async () => {
    storageMock.findPersonByPhone.mockResolvedValueOnce({ id: "p4", mergedIntoId: null });
    await resolveOrCreatePerson({ phone: "5551234", source: "manual" });
    expect(storageMock.findPersonByEmail).not.toHaveBeenCalled();
    expect(storageMock.findPersonByPhone).toHaveBeenCalled();
  });
});

describe("resolveOrCreatePerson — merge following", () => {
  it("follows merged_into_id and returns the winner, not the loser", async () => {
    storageMock.findPersonByEmail.mockResolvedValueOnce({
      id: "loser",
      mergedIntoId: "winner",
    });
    storageMock.getPerson.mockResolvedValueOnce({ id: "winner", mergedIntoId: null });

    const result = await resolveOrCreatePerson({
      email: "shared@example.com",
      source: "intake",
    });

    expect(result.person.id).toBe("winner");
    expect(result.via).toBe("email");
  });

  it("stops following merge chains after 3 hops (cycle guard)", async () => {
    storageMock.findPersonByEmail.mockResolvedValueOnce({ id: "a", mergedIntoId: "b" });
    storageMock.getPerson
      .mockResolvedValueOnce({ id: "b", mergedIntoId: "c" })
      .mockResolvedValueOnce({ id: "c", mergedIntoId: "d" })
      .mockResolvedValueOnce({ id: "d", mergedIntoId: "e" });

    const result = await resolveOrCreatePerson({
      email: "chained@example.com",
      source: "intake",
    });

    // After 3 hops we stop and return whatever we last resolved.
    expect(result.person.id).toBe("d");
  });
});

describe("getPerson", () => {
  it("returns undefined when the id doesn't exist", async () => {
    storageMock.getPerson.mockResolvedValueOnce(undefined);
    const result = await getPerson("missing-uuid");
    expect(result).toBeUndefined();
  });

  it("follows merge chain on direct lookup", async () => {
    storageMock.getPerson
      .mockResolvedValueOnce({ id: "old", mergedIntoId: "new" })
      .mockResolvedValueOnce({ id: "new", mergedIntoId: null });
    const result = await getPerson("old");
    expect(result?.id).toBe("new");
  });
});

describe("resolveOrCreatePerson — external ID matching", () => {
  it("matches by external ID before checking email or phone (highest trust)", async () => {
    storageMock.findPersonByExternalId.mockResolvedValueOnce({ id: "p-ext", mergedIntoId: null });

    const result = await resolveOrCreatePerson({
      email: "jane@example.com",
      phone: "5551234",
      externalIds: [{ system: "salesforce", id: "00Q5e000001abc" }],
      source: "salesforce",
    });

    expect(result.via).toBe("external_id");
    expect(result.person.id).toBe("p-ext");
    expect(storageMock.findPersonByExternalId).toHaveBeenCalledWith("salesforce", "00Q5e000001abc");
    // Email/phone lookups skipped — external match was authoritative.
    expect(storageMock.findPersonByEmail).not.toHaveBeenCalled();
    expect(storageMock.findPersonByPhone).not.toHaveBeenCalled();
  });

  it("walks multiple external-ID hints until one resolves", async () => {
    storageMock.findPersonByExternalId
      .mockResolvedValueOnce(undefined) // first hint misses
      .mockResolvedValueOnce({ id: "p-2", mergedIntoId: null }); // second matches

    const result = await resolveOrCreatePerson({
      externalIds: [
        { system: "carestack", id: "cs-999" },
        { system: "salesforce", id: "sf-123" },
      ],
      source: "carestack",
    });

    expect(result.via).toBe("external_id");
    expect(result.person.id).toBe("p-2");
    expect(storageMock.findPersonByExternalId).toHaveBeenCalledTimes(2);
  });

  it("falls through to email when no external ID matches", async () => {
    storageMock.findPersonByExternalId.mockResolvedValue(undefined);
    storageMock.findPersonByEmail.mockResolvedValueOnce({ id: "p-by-email", mergedIntoId: null });

    const result = await resolveOrCreatePerson({
      email: "fallthrough@example.com",
      externalIds: [{ system: "salesforce", id: "unknown" }],
      source: "salesforce",
    });

    expect(result.via).toBe("email");
    expect(result.person.id).toBe("p-by-email");
  });

  it("links unmatched external-ID hints to the resolved person", async () => {
    storageMock.findPersonByEmail.mockResolvedValueOnce({ id: "existing", mergedIntoId: null });

    await resolveOrCreatePerson({
      email: "shared@example.com",
      externalIds: [
        { system: "stripe", id: "cus_abc" },
        { system: "carestack", id: "cs-42", kind: "patient" },
      ],
      source: "intake",
    });

    // Both external IDs got linked to the person we matched by email.
    expect(storageMock.linkPersonExternalId).toHaveBeenCalledTimes(2);
    const calls = storageMock.linkPersonExternalId.mock.calls.map((c) => c[0]);
    expect(calls).toContainEqual(
      expect.objectContaining({ personUid: "existing", externalSystem: "stripe", externalId: "cus_abc" }),
    );
    expect(calls).toContainEqual(
      expect.objectContaining({ personUid: "existing", externalSystem: "carestack", externalKind: "patient" }),
    );
  });

  it("does not re-link the external ID that matched (only the others)", async () => {
    storageMock.findPersonByExternalId.mockResolvedValueOnce({ id: "via-sf", mergedIntoId: null });

    await resolveOrCreatePerson({
      externalIds: [
        { system: "salesforce", id: "sf-1" }, // matched
        { system: "carestack", id: "cs-1" }, // needs to be linked
      ],
      source: "salesforce",
    });

    expect(storageMock.linkPersonExternalId).toHaveBeenCalledTimes(1);
    expect(storageMock.linkPersonExternalId.mock.calls[0][0]).toMatchObject({
      personUid: "via-sf",
      externalSystem: "carestack",
      externalId: "cs-1",
    });
  });

  it("links external IDs to a freshly created person when nothing matches", async () => {
    storageMock.findPersonByExternalId.mockResolvedValue(undefined);
    storageMock.findPersonByEmail.mockResolvedValue(undefined);
    storageMock.findPersonByPhone.mockResolvedValue(undefined);
    storageMock.findPersonByNameDob.mockResolvedValue(undefined);
    storageMock.createPerson.mockResolvedValueOnce({ id: "freshly-created", mergedIntoId: null });

    await resolveOrCreatePerson({
      firstName: "New",
      lastName: "Human",
      dateOfBirth: "2000-01-01",
      externalIds: [{ system: "carestack", id: "cs-new-1" }],
      source: "carestack",
    });

    expect(storageMock.linkPersonExternalId).toHaveBeenCalledOnce();
    expect(storageMock.linkPersonExternalId.mock.calls[0][0]).toMatchObject({
      personUid: "freshly-created",
      externalSystem: "carestack",
      externalId: "cs-new-1",
    });
  });

  it("swallows uniqueness violations when linking (concurrent writer already linked it)", async () => {
    storageMock.findPersonByEmail.mockResolvedValueOnce({ id: "p", mergedIntoId: null });
    storageMock.linkPersonExternalId.mockRejectedValueOnce(
      new Error('duplicate key value violates unique constraint "uniq_person_external_ids_system_id"'),
    );

    // Should NOT throw — the race is benign.
    await expect(
      resolveOrCreatePerson({
        email: "race@example.com",
        externalIds: [{ system: "stripe", id: "cus_race" }],
        source: "intake",
      }),
    ).resolves.toMatchObject({ via: "email", person: { id: "p" } });
  });
});

describe("linkExternalId / findPersonByExternalId", () => {
  it("writes a row through storage", async () => {
    await linkExternalId("p-x", { system: "salesforce", id: "sf-42", kind: "Contact" }, { source: "test" });
    expect(storageMock.linkPersonExternalId).toHaveBeenCalledWith(
      expect.objectContaining({
        personUid: "p-x",
        externalSystem: "salesforce",
        externalId: "sf-42",
        externalKind: "Contact",
        metadata: { source: "test" },
      }),
    );
  });

  it("findPersonByExternalId follows merge chains", async () => {
    storageMock.findPersonByExternalId.mockResolvedValueOnce({ id: "old", mergedIntoId: "new" });
    storageMock.getPerson.mockResolvedValueOnce({ id: "new", mergedIntoId: null });
    const found = await findPersonByExternalId("carestack", "cs-merged");
    expect(found?.id).toBe("new");
  });

  it("findPersonByExternalId returns undefined when not linked", async () => {
    storageMock.findPersonByExternalId.mockResolvedValueOnce(undefined);
    expect(await findPersonByExternalId("nope", "missing")).toBeUndefined();
  });
});

describe("mergePersons", () => {
  it("rejects self-merge", async () => {
    await expect(mergePersons("same", "same")).rejects.toThrow(/themselves/);
  });

  it("rejects merging when either side doesn't exist", async () => {
    storageMock.getPerson
      .mockResolvedValueOnce(undefined) // loser
      .mockResolvedValueOnce({ id: "w" }); // winner
    await expect(mergePersons("missing", "w")).rejects.toThrow(/not found/);
  });

  it("sets loser.mergedIntoId on success", async () => {
    storageMock.getPerson
      .mockResolvedValueOnce({ id: "loser" })
      .mockResolvedValueOnce({ id: "winner" });

    await mergePersons("loser", "winner");

    expect(storageMock.setPersonMergedInto).toHaveBeenCalledWith("loser", "winner");
  });
});
