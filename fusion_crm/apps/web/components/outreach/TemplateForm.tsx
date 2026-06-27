"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, Info, Loader2, Save } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import {
  useCreateTemplate,
  useTemplatePreview,
  useUpdateTemplate,
} from "@/lib/api/hooks/useOutreach";
import {
  MERGE_FIELDS,
  TRACKING_FORBIDDEN_CATEGORIES,
  type RenderedEmail,
  type TemplateBodyFormat,
  type TemplateCategory,
  type TemplateOut,
} from "@/lib/api/schemas/outreach";

interface Props {
  /**
   * When set, the form edits this existing template (PATCH); when null we
   * create a new draft via POST and route to the list on success.
   */
  initial: TemplateOut | null;
}

interface FormState {
  name: string;
  description: string;
  subject_template: string;
  body_template: string;
  body_format: TemplateBodyFormat;
  category: TemplateCategory;
  tracking_enabled: boolean;
  intent_tags: string[];
}

function emptyState(): FormState {
  return {
    name: "",
    description: "",
    subject_template: "",
    body_template: "",
    body_format: "markdown",
    category: "marketing",
    tracking_enabled: false,
    intent_tags: [],
  };
}

function fromTemplate(t: TemplateOut): FormState {
  return {
    name: t.name,
    description: t.description ?? "",
    subject_template: t.subject_template,
    body_template: t.body_template,
    // The wire schema reserves "html" but the editor only surfaces the two
    // Stage-1 formats. If we ever load an html template, treat it as
    // markdown — the operator can switch back if needed.
    body_format: t.body_format === "html" ? "markdown" : t.body_format,
    category: t.category,
    tracking_enabled: t.tracking_enabled,
    intent_tags: t.intent_tags,
  };
}

export function TemplateForm({ initial }: Props) {
  const router = useRouter();
  const { toast } = useToast();

  const create = useCreateTemplate();
  const update = useUpdateTemplate(initial?.id ?? "");
  const preview = useTemplatePreview();

  const [state, setState] = useState<FormState>(
    initial ? fromTemplate(initial) : emptyState(),
  );
  const [tagInput, setTagInput] = useState("");
  const [rendered, setRendered] = useState<RenderedEmail | null>(null);
  const bodyRef = useRef<HTMLTextAreaElement | null>(null);

  const trackingLocked = TRACKING_FORBIDDEN_CATEGORIES.has(state.category);

  // If the operator switches to a forbidden category while tracking is on,
  // flip it off immediately so the save call doesn't trip the server gate.
  useEffect(() => {
    if (trackingLocked && state.tracking_enabled) {
      setState((s) => ({ ...s, tracking_enabled: false }));
    }
  }, [trackingLocked, state.tracking_enabled]);

  function patch<K extends keyof FormState>(key: K, value: FormState[K]) {
    setState((s) => ({ ...s, [key]: value }));
  }

  function insertMergeField(key: string) {
    const ta = bodyRef.current;
    if (!ta) return;
    const before = state.body_template.slice(0, ta.selectionStart);
    const after = state.body_template.slice(ta.selectionEnd);
    const token = `{{${key}}}`;
    const next = before + token + after;
    patch("body_template", next);
    // Restore selection at the end of the inserted token on the next tick
    // so the operator can keep typing immediately after.
    queueMicrotask(() => {
      const pos = before.length + token.length;
      ta.focus();
      ta.setSelectionRange(pos, pos);
    });
  }

  function addTag() {
    const t = tagInput.trim();
    if (!t || state.intent_tags.includes(t)) {
      setTagInput("");
      return;
    }
    patch("intent_tags", [...state.intent_tags, t]);
    setTagInput("");
  }

  function removeTag(t: string) {
    patch(
      "intent_tags",
      state.intent_tags.filter((x) => x !== t),
    );
  }

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    if (!state.name.trim() || !state.subject_template.trim() || !state.body_template.trim()) {
      toast({
        title: "Missing fields",
        description: "Name, subject, and body are all required.",
        variant: "destructive",
      });
      return;
    }
    try {
      if (initial) {
        await update.mutateAsync({
          name: state.name,
          description: state.description || null,
          subject_template: state.subject_template,
          body_template: state.body_template,
          body_format: state.body_format,
          category: state.category,
          tracking_enabled: state.tracking_enabled,
          intent_tags: state.intent_tags,
        });
        toast({ title: "Template updated", variant: "success" });
      } else {
        await create.mutateAsync({
          name: state.name,
          description: state.description || null,
          subject_template: state.subject_template,
          body_template: state.body_template,
          body_format: state.body_format,
          category: state.category,
          tracking_enabled: state.tracking_enabled,
          intent_tags: state.intent_tags,
        });
        toast({ title: "Template created", variant: "success" });
      }
      router.push("/outreach/templates");
    } catch (e: unknown) {
      const msg =
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Unknown error";
      toast({
        title: "Save failed",
        description: msg,
        variant: "destructive",
      });
    }
  }

  async function onPreview() {
    if (!initial?.id) {
      toast({
        title: "Save first",
        description:
          "Preview renders against a saved template. Save the draft, then click Preview.",
      });
      return;
    }
    try {
      const r = await preview.mutateAsync({ id: initial.id });
      setRendered(r);
    } catch (e: unknown) {
      const msg =
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Unknown error";
      toast({
        title: "Preview failed",
        description: msg,
        variant: "destructive",
      });
    }
  }

  const saving = create.isPending || update.isPending;

  return (
    <form onSubmit={onSave} className="space-y-6">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr,320px]">
        {/* Main form column */}
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="tpl-name">Name</Label>
              <Input
                id="tpl-name"
                value={state.name}
                onChange={(e) => patch("name", e.target.value)}
                placeholder="Welcome to Galleria"
                maxLength={240}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="tpl-category">Category</Label>
              <NativeSelect
                id="tpl-category"
                ariaLabel="Category"
                value={state.category}
                onChange={(e) =>
                  patch("category", e.target.value as TemplateCategory)
                }
              >
                <option value="marketing">Marketing</option>
                <option value="clinical">Clinical</option>
                <option value="transactional">Transactional</option>
                <option value="operational">Operational</option>
              </NativeSelect>
            </div>

            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="tpl-desc">Description</Label>
              <textarea
                id="tpl-desc"
                value={state.description}
                onChange={(e) => patch("description", e.target.value)}
                rows={2}
                maxLength={4000}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                placeholder="What this template is for (operator-facing only)."
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="tpl-format">Body format</Label>
              <NativeSelect
                id="tpl-format"
                ariaLabel="Body format"
                value={state.body_format}
                onChange={(e) =>
                  patch("body_format", e.target.value as TemplateBodyFormat)
                }
              >
                <option value="markdown">Markdown</option>
                <option value="mjml">MJML (advanced)</option>
              </NativeSelect>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tpl-tracking">Open / click tracking</Label>
              <div
                className="flex items-center gap-2"
                title={
                  trackingLocked
                    ? `Tracking is not allowed for ${state.category} templates per ADR-0004. Switch to "marketing" to enable.`
                    : undefined
                }
              >
                <Switch
                  id="tpl-tracking"
                  checked={state.tracking_enabled}
                  onCheckedChange={(v) => patch("tracking_enabled", v)}
                  disabled={trackingLocked}
                  ariaLabel="Tracking enabled"
                />
                <span className="text-xs text-muted-foreground">
                  {trackingLocked
                    ? "Disabled — not allowed for this category"
                    : state.tracking_enabled
                      ? "Enabled"
                      : "Off"}
                </span>
              </div>
              {trackingLocked ? (
                <div className="flex items-start gap-1 text-[11px] text-muted-foreground">
                  <Info className="mt-0.5 h-3 w-3 shrink-0" />
                  <span>
                    Clinical / transactional / operational templates may not
                    enable open or click tracking.
                  </span>
                </div>
              ) : null}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tpl-subject">Subject template</Label>
            <Input
              id="tpl-subject"
              value={state.subject_template}
              onChange={(e) => patch("subject_template", e.target.value)}
              placeholder="Hi {{patient.first_name}} 👋"
              className="font-mono text-sm"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tpl-body">Body template</Label>
            <textarea
              id="tpl-body"
              ref={bodyRef}
              value={state.body_template}
              onChange={(e) => patch("body_template", e.target.value)}
              rows={14}
              className="block w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              placeholder={`Hi {{patient.first_name}},\n\nThanks for reaching out to {{tenant.name}}.`}
            />
          </div>

          <div className="space-y-1.5">
            <Label>Intent tags</Label>
            <div className="flex flex-wrap items-center gap-2">
              {state.intent_tags.map((t) => (
                <button
                  type="button"
                  key={t}
                  onClick={() => removeTag(t)}
                  className="inline-flex items-center gap-1 rounded-full border bg-muted/40 px-2.5 py-0.5 text-xs hover:bg-muted"
                >
                  {t}
                  <span aria-hidden>×</span>
                </button>
              ))}
              <div className="flex items-center gap-1">
                <Input
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addTag();
                    }
                  }}
                  placeholder="add tag…"
                  className="h-8 w-32 text-xs"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addTag}
                >
                  Add
                </Button>
              </div>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Optional routing hints — e.g. <code>welcome</code>,{" "}
              <code>consult-followup</code>.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 border-t pt-4">
            <Button type="submit" disabled={saving} className="gap-1.5">
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              {initial ? "Save changes" : "Save draft"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={onPreview}
              disabled={preview.isPending}
              className="gap-1.5"
              title={initial ? undefined : "Save a draft first to render a preview"}
            >
              {preview.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
              Render preview
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => router.push("/outreach/templates")}
            >
              Cancel
            </Button>
          </div>
        </div>

        {/* Sidebar: merge fields + preview */}
        <aside className="space-y-4">
          <div className="rounded-md border bg-card p-4 shadow-sm">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold">Merge fields</h3>
              <Badge variant="outline">{MERGE_FIELDS.length}</Badge>
            </div>
            <p className="mb-3 text-[11px] text-muted-foreground">
              Click to insert at the cursor. Unknown placeholders render as
              empty strings.
            </p>
            <div className="space-y-3">
              {Array.from(new Set(MERGE_FIELDS.map((f) => f.group))).map(
                (group) => (
                  <div key={group}>
                    <div className="pb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                      {group}
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {MERGE_FIELDS.filter((f) => f.group === group).map(
                        (f) => (
                          <button
                            key={f.key}
                            type="button"
                            onClick={() => insertMergeField(f.key)}
                            title={f.description}
                            className="rounded border bg-background px-2 py-0.5 font-mono text-[11px] hover:bg-accent"
                          >
                            {f.key}
                          </button>
                        ),
                      )}
                    </div>
                  </div>
                ),
              )}
            </div>
          </div>

          {rendered ? (
            <div className="rounded-md border bg-card p-4 shadow-sm">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold">Live preview</h3>
                <button
                  type="button"
                  className="text-[11px] text-muted-foreground hover:text-foreground"
                  onClick={() => setRendered(null)}
                >
                  Hide
                </button>
              </div>
              <div className="space-y-2">
                <div className="rounded bg-muted/40 p-2 text-xs">
                  <span className="font-semibold">Subject:</span>{" "}
                  {rendered.subject || (
                    <span className="text-muted-foreground">(empty)</span>
                  )}
                </div>
                <iframe
                  title="Template preview"
                  sandbox=""
                  srcDoc={rendered.body_html}
                  className="h-72 w-full rounded border bg-background"
                />
              </div>
            </div>
          ) : null}
        </aside>
      </div>
    </form>
  );
}
