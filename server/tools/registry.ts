import type { Tool } from "./types";
import { suggestCodesTool } from "./coding/suggestCodes";
import { chatTool } from "./ai/chat";
import { diagnosisTool } from "./ai/diagnosis";
import { medicalNecessityLetterTool } from "./letters/medicalNecessity";
import { appealLetterTool } from "./letters/appeal";
import { suggestReplyTool } from "./messaging/suggestReply";
import { perioAssessmentTool } from "./perio/aiAssessment";
import { specialtyRecommendationsTool } from "./onboarding/specialtyRecommendations";
import { generateDocumentTool } from "./documents/generate";
import { runWorkflowTool } from "./workflow/runWorkflow";

// Single source of truth for the tool catalog. Both the MCP server and the
// agent workflow runner enumerate tools from here so adding a new tool
// requires exactly one edit to wire it up everywhere.

export const tools: Array<Tool<any, any>> = [
  suggestCodesTool,
  chatTool,
  diagnosisTool,
  medicalNecessityLetterTool,
  appealLetterTool,
  suggestReplyTool,
  perioAssessmentTool,
  specialtyRecommendationsTool,
  generateDocumentTool,
  runWorkflowTool,
];

const byName = new Map<string, Tool<any, any>>(tools.map((t) => [t.name, t]));

export function listTools(): Array<Tool<any, any>> {
  return tools;
}

export function getToolByName(name: string): Tool<any, any> | undefined {
  return byName.get(name);
}
