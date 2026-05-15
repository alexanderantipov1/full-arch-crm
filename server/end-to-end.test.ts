/**
 * End-to-end demo test.
 *
 * Exercises every seam the architectural backbone added, composing them
 * together exactly the way a real MCP-driven agent run would. No fake
 * tools, no fake services — only the boundaries are mocked:
 *
 *   - `anthropic.messages.create` (so we can script the agent's responses)
 *   - `storage.*`                  (so we don't hit a real Postgres)
 *
 * Everything between those — MCP dispatcher → tool registry →
 * `workflow.run` tool → agent loop → `documents.generate` tool →
 * `PhiService` (capability check + tenant filter + audit row) →
 * workflow_instance + workflow_steps persistence — is the real code path.
 *
 * If this test passes, the whole stack composes.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

// ── Anthropic + AI service mock ─────────────────────────────────────────
const anthropicMock = vi.hoisted(() => ({
  messages: { create: vi.fn() },
}));
vi.mock("./services/ai", () => ({
  anthropic: anthropicMock,
  askClaude: vi.fn().mockResolvedValue("Dear insurance carrier, the patient requires..."),
  hasSignedAnthropicBaa: vi.fn(() => true),
}));

// ── Storage mock — every method the test path touches ──────────────────
const storageMock = vi.hoisted(() => {
  // Mutable bag of created rows so assertions can inspect what was written.
  const audit: any[] = [];
  const workflowInstances: any[] = [];
  const workflowSteps: any[] = [];

  return {
    // PHI reads.
    getPatient: vi.fn(),
    getMedicalHistory: vi.fn().mockResolvedValue({ conditions: ["edentulism"] }),
    getTreatmentPlansByPatient: vi.fn().mockResolvedValue([]),

    // PHI writes.
    createGeneratedDocument: vi.fn(async (data: any) => ({ id: 901, ...data })),

    // Audit.
    createAuditLog: vi.fn(async (row: any) => {
      audit.push(row);
      return { id: audit.length, ...row };
    }),

    // Workflow durability.
    createWorkflowInstance: vi.fn(async (data: any) => {
      const row = { id: "wf-e2e-1", ...data };
      workflowInstances.push(row);
      return row;
    }),
    createWorkflowStep: vi.fn(async (data: any) => {
      const row = { id: `step-${workflowSteps.length + 1}`, ...data };
      workflowSteps.push(row);
      return row;
    }),
    updateWorkflowInstance: vi.fn(async (id: string, patch: any) => {
      const row = workflowInstances.find((r) => r.id === id);
      if (row) Object.assign(row, patch);
    }),

    // Identity (not exercised in this happy-path flow but the chain loads
    // these methods on import).
    findPersonByEmail: vi.fn(),
    findPersonByPhone: vi.fn(),
    findPersonByNameDob: vi.fn(),
    findPersonByExternalId: vi.fn(),
    getPerson: vi.fn(),
    createPerson: vi.fn(),
    linkPersonExternalId: vi.fn(),

    // Inspection handles for assertions.
    _audit: audit,
    _workflowInstances: workflowInstances,
    _workflowSteps: workflowSteps,
  };
});
vi.mock("./storage", () => ({ storage: storageMock }));

// ── Now import the real modules ─────────────────────────────────────────
// Order matters: the mocks above must register before these imports trigger
// any service loads.
import { handleMcpRequest } from "./mcp/server";
import { makePrincipal } from "./tools/types";

// Helpers to script the agent's Anthropic responses turn-by-turn.
function toolUseTurn(opts: { id: string; name: string; input: Record<string, unknown> }) {
  return { content: [{ type: "tool_use", id: opts.id, name: opts.name, input: opts.input }] };
}
function finalAnswerTurn(text: string) {
  return { content: [{ type: "text", text }] };
}

beforeEach(() => {
  vi.clearAllMocks();
  // Reset the bag-of-rows handles.
  storageMock._audit.length = 0;
  storageMock._workflowInstances.length = 0;
  storageMock._workflowSteps.length = 0;
  // Default patient lookup is tenant-A so the principal can read it.
  storageMock.getPatient.mockResolvedValue({
    id: 42,
    tenantId: "tenant-a",
    firstName: "Jane",
    lastName: "Doe",
    dateOfBirth: "1960-01-01",
  });
  // Same for medical history — gets returned by gatedRead (no tenant on it).
  storageMock.getMedicalHistory.mockResolvedValue({ conditions: ["edentulism"] });
  storageMock.getTreatmentPlansByPatient.mockResolvedValue([]);
  storageMock.createGeneratedDocument.mockImplementation(async (data: any) => ({ id: 901, ...data }));
});

describe("end-to-end: MCP → workflow.run → documents.generate → PhiService", () => {
  it("composes every layer for a clinical-document-generation workflow", async () => {
    // Script: the agent's first turn calls documents.generate; second turn
    // it returns a final answer. Two Anthropic calls total — one
    // tool-use, one summary.
    anthropicMock.messages.create
      .mockResolvedValueOnce(
        toolUseTurn({
          id: "tu_1",
          name: "documents.generate",
          input: { patientId: 42, documentType: "medical-necessity" },
        }),
      )
      .mockResolvedValueOnce(finalAnswerTurn("Generated a medical necessity letter for patient 42."));

    // The MCP request the agent client would have sent. Principal is what
    // `mcpAuth` would have produced from a valid bearer token — tenant +
    // full PHI capabilities.
    const principal = makePrincipal({
      userId: "mcp:test-key",
      email: "agent@test",
      tenantId: "tenant-a",
      capabilities: ["phi.read", "phi.write"],
    });

    const response = await handleMcpRequest(
      {
        jsonrpc: "2.0",
        id: 100,
        method: "tools/call",
        params: {
          name: "workflow.run",
          arguments: {
            goal: "Generate a medical necessity letter for patient 42 to support their full-arch implant claim.",
            maxIterations: 3,
          },
        },
      },
      principal,
    );

    // ── 1. MCP layer succeeded ───────────────────────────────────────
    expect("result" in response).toBe(true);
    if (!("result" in response)) return; // narrow
    const result = response.result as any;
    expect(result.isError).toBeUndefined();
    expect(result.structuredContent).toBeDefined();

    // ── 2. The workflow ran to completion ────────────────────────────
    const workflow = result.structuredContent;
    expect(workflow.endReason).toBe("completed");
    expect(workflow.iterations).toBe(2); // tool_use turn + final answer turn
    expect(workflow.finalAnswer).toMatch(/medical necessity letter/i);

    // ── 3. PhiService capability check + audit on PHI reads ──────────
    // documents.generate reads: patient + medical history + treatment plans
    // → three phi.read audit rows. Plus one phi.create for the generated
    // document. All four rows are marked phiAccessed.
    const audit = storageMock._audit;
    expect(audit.length).toBe(4);
    const actions = audit.map((r) => r.action).sort();
    expect(actions).toEqual(["phi.create", "phi.read", "phi.read", "phi.read"]);
    expect(audit.every((r) => r.phiAccessed === true)).toBe(true);
    expect(audit.every((r) => r.userId === "mcp:test-key")).toBe(true);
    // The single write was for the generated_document resource.
    const writeRow = audit.find((r) => r.action === "phi.create");
    expect(writeRow.resourceType).toBe("generated_document");
    expect(writeRow.patientId).toBe(42);

    // ── 4. Workflow durability — instance + step rows persisted ──────
    expect(storageMock._workflowInstances.length).toBe(1);
    const instance = storageMock._workflowInstances[0];
    expect(instance).toMatchObject({
      principalUserId: "mcp:test-key",
      status: "completed",
      endReason: "completed",
      iterationsUsed: 2,
    });
    // The step trail captured the documents.generate invocation with its
    // input + ok result.
    expect(storageMock._workflowSteps.length).toBe(1);
    const step = storageMock._workflowSteps[0];
    expect(step).toMatchObject({
      instanceId: "wf-e2e-1",
      iteration: 1,
      toolName: "documents.generate",
    });
    expect(step.input).toMatchObject({ patientId: 42, documentType: "medical-necessity" });
    expect(step.result.ok).toBe(true);
    expect(step.result.data.documentId).toBe(901);

    // ── 5. Generated document was actually persisted ─────────────────
    expect(storageMock.createGeneratedDocument).toHaveBeenCalledOnce();
    const docArgs = storageMock.createGeneratedDocument.mock.calls[0][0];
    expect(docArgs).toMatchObject({
      patientId: 42,
      documentType: "medical-necessity",
    });
    expect(docArgs.title).toContain("Medical Necessity");
    expect(docArgs.title).toContain("Jane Doe");

    // ── 6. workflow.run filtered itself out of the recursive tool set ─
    // The first Anthropic call lists tools the agent can call. workflow.run
    // must NOT be in there (otherwise the agent could recurse forever).
    const firstCallTools = anthropicMock.messages.create.mock.calls[0][0].tools;
    const toolNames = firstCallTools.map((t: any) => t.name);
    expect(toolNames).toContain("documents.generate");
    expect(toolNames).not.toContain("workflow.run");
  });

  it("hides cross-tenant patients from the agent — PhiService denies the read", async () => {
    // Same script, but the patient lives in tenant-b and the principal is
    // in tenant-a. PhiService.filterByTenant should treat the read as
    // not-found, the agent's documents.generate tool should fail with
    // not_found, and that failure should propagate as a workflow step
    // with ok:false.
    storageMock.getPatient.mockResolvedValue({
      id: 42,
      tenantId: "tenant-b", // different tenant
      firstName: "Jane",
      lastName: "Doe",
      dateOfBirth: "1960-01-01",
    });

    anthropicMock.messages.create
      .mockResolvedValueOnce(
        toolUseTurn({
          id: "tu_1",
          name: "documents.generate",
          input: { patientId: 42, documentType: "medical-necessity" },
        }),
      )
      .mockResolvedValueOnce(finalAnswerTurn("Could not access patient 42."));

    const principal = makePrincipal({
      userId: "mcp:test-key",
      tenantId: "tenant-a",
      capabilities: ["phi.read", "phi.write"],
    });

    const response = await handleMcpRequest(
      {
        jsonrpc: "2.0",
        id: 101,
        method: "tools/call",
        params: {
          name: "workflow.run",
          arguments: { goal: "Try to read patient 42 from another tenant", maxIterations: 3 },
        },
      },
      principal,
    );

    expect("result" in response).toBe(true);
    if (!("result" in response)) return;
    const workflow = (response.result as any).structuredContent;

    // The workflow itself completed normally, but the step inside it
    // failed because PhiService hid the cross-tenant patient.
    expect(workflow.endReason).toBe("completed");
    const step = storageMock._workflowSteps[0];
    expect(step.toolName).toBe("documents.generate");
    expect(step.result.ok).toBe(false);
    expect(step.result.error.code).toBe("not_found");

    // No document was persisted — the read failure short-circuited the
    // generate path before any write happened.
    expect(storageMock.createGeneratedDocument).not.toHaveBeenCalled();

    // An audit row was still written for the read (which returned undefined
    // post-filter). That's the HIPAA invariant: every attempt is logged.
    const readAttempts = storageMock._audit.filter((r) => r.action === "phi.read");
    expect(readAttempts.length).toBeGreaterThanOrEqual(1);
  });
});
