import { z } from "zod";
import { anthropic } from "../../services/ai";
import { defineTool } from "../types";

const inputSchema = z.object({
  specialty: z.string().optional(),
  practiceType: z.string().optional(),
});

export type SpecialtyRecommendationsInput = z.infer<typeof inputSchema>;

export interface RecommendedModule {
  title: string;
  url: string;
  reason: string;
}

export interface SpecialtyRecommendationsOutput {
  welcome: string;
  modules: RecommendedModule[];
}

// Onboarding is UX-critical — never surface an error to the user. On any
// failure (AI down, malformed JSON, etc.), fall back to a generic welcome so
// the wizard keeps moving. That's why this tool always returns `ok: true`.
export const specialtyRecommendationsTool = defineTool<SpecialtyRecommendationsInput, SpecialtyRecommendationsOutput>({
  name: "onboarding.specialtyRecommendations",
  description: "Suggest a personalized welcome + 6 most-relevant modules for a dental specialty onboarding.",
  inputSchema,
  async handler(_ctx, input) {
    const specialty = input.specialty || input.practiceType || "dental";
    const fallback: SpecialtyRecommendationsOutput = {
      welcome: `Welcome! Your platform is ready for ${specialty} practice.`,
      modules: [],
    };

    try {
      const message = await anthropic.messages.create({
        model: "claude-opus-4-5",
        max_tokens: 600,
        messages: [
          {
            role: "user",
            content: `You are helping set up a dental practice management platform for a ${specialty} specialist. Generate a brief, enthusiastic personalized welcome (2 sentences max) and a JSON list of the 6 most relevant module categories for this specialty from the following list. Return ONLY valid JSON in this format: {"welcome": "...", "modules": [{"title":"...", "url":"...", "reason":"..."}]}. Available modules: Patients (/patients), Scheduling (/appointments), Perio Charting (/perio), Endo/RCT (/endo), Recall System (/recall), Oral Surgery (/oral-surgery), Orthodontics (/ortho), Pediatric (/pediatric), Treatment Plans (/treatment-plans), Implant Tracker (/implant-tracker), Lab & Design (/lab), Billing & Claims (/billing), Coding Engine (/coding), Medical Clearance (/medical-clearance), Surgery Day (/surgery), AI Documentation (/ai-documentation), Appeals Engine (/appeals), Insurance Verification (/eligibility), Patient Messaging (/patient-messaging), Consent Forms (/consent-forms). Specialty: ${specialty}`,
          },
        ],
      });

      const block = message.content[0];
      const text = block.type === "text" ? block.text : "";
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      if (!jsonMatch) {
        return { ok: true, data: fallback };
      }
      const parsed = JSON.parse(jsonMatch[0]) as Partial<SpecialtyRecommendationsOutput>;
      return {
        ok: true,
        data: {
          welcome: parsed.welcome ?? fallback.welcome,
          modules: Array.isArray(parsed.modules) ? parsed.modules : [],
        },
      };
    } catch (err) {
      console.error("Specialty recommendation error:", err);
      return { ok: true, data: fallback };
    }
  },
});
