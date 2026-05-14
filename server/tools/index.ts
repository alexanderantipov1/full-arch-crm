// Tool layer entry point. Routes import tools from here so the underlying
// file layout can evolve without touching every consumer.
//
// The export surface here is also the surface a future MCP server would
// expose to external AI clients (Claude Code, Codex, etc.) — same tools,
// different transport. Keep names stable; deprecate, don't rename.

export { suggestCodesTool } from "./coding/suggestCodes";
export { chatTool } from "./ai/chat";
export { diagnosisTool } from "./ai/diagnosis";
export { medicalNecessityLetterTool } from "./letters/medicalNecessity";
export { appealLetterTool } from "./letters/appeal";
export { suggestReplyTool } from "./messaging/suggestReply";
export { perioAssessmentTool } from "./perio/aiAssessment";
export { specialtyRecommendationsTool } from "./onboarding/specialtyRecommendations";
export { generateDocumentTool } from "./documents/generate";
export { runWorkflowTool } from "./workflow/runWorkflow";

export {
  runTool,
  principalFromReq,
  httpStatusForToolError,
  respondWithToolResult,
} from "./runner";

export type {
  Tool,
  ToolContext,
  ToolResult,
  ToolError,
  Principal,
} from "./types";
export { ToolErrorCode, defineTool } from "./types";
