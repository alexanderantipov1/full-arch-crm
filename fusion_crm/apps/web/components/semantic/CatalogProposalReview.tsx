"use client";

import * as React from "react";
import {
  AlertCircle,
  CheckCircle2,
  History,
  Lightbulb,
  Plus,
  RefreshCw,
  Save,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import {
  useCatalogDraftPatch,
  useCatalogProposalHistory,
  useCatalogProposalImpactPreview,
  useCatalogProposals,
  useCatalogVersionHistory,
  useCreateCatalogProposal,
  useReviewCatalogProposal,
  useUpdateCatalogProposal,
} from "@/lib/api/hooks/useSemanticCatalog";
import type {
  CatalogProposal,
  CatalogProposalCreateInput,
  CatalogProposalStatus,
  CatalogProposalUpdateInput,
} from "@/lib/api/schemas/semanticCatalog";
import { cn } from "@/lib/utils";

type ConfidenceBucket = "low" | "medium" | "high";

type ProposalDraft = {
  raw_value: string;
  source_system: string;
  source_field: string;
  suggested_term: string;
  definition: string;
  synonyms: string;
  confidence: ConfidenceBucket;
  reason: string;
  reviewer_note: string;
  affected_questions: string;
  affected_read_models: string;
};

const STATUS_META: Record<
  CatalogProposalStatus,
  {
    label: string;
    className: string;
    icon: typeof Lightbulb;
  }
> = {
  proposed: {
    label: "In review",
    className: "border-blue-500/40 bg-blue-500/10 text-blue-700",
    icon: Lightbulb,
  },
  approved: {
    label: "Approved",
    className: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700",
    icon: CheckCircle2,
  },
  rejected: {
    label: "Rejected",
    className: "border-rose-500/40 bg-rose-500/10 text-rose-700",
    icon: XCircle,
  },
  unresolved: {
    label: "Unresolved",
    className: "border-amber-500/40 bg-amber-500/10 text-amber-700",
    icon: AlertCircle,
  },
};

const EMPTY_PROPOSALS: CatalogProposal[] = [];

function statusBadge(status: CatalogProposalStatus) {
  const meta = STATUS_META[status];
  const Icon = meta.icon;

  return (
    <Badge variant="outline" className={cn("gap-1", meta.className)}>
      <Icon className="h-3.5 w-3.5" />
      {meta.label}
    </Badge>
  );
}

function splitCsv(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinCsv(value: string[]) {
  return value.join(", ");
}

function confidenceToBucket(value: number): ConfidenceBucket {
  if (value >= 0.8) return "high";
  if (value >= 0.5) return "medium";
  return "low";
}

function bucketToConfidence(value: ConfidenceBucket) {
  if (value === "high") return 0.9;
  if (value === "medium") return 0.65;
  return 0.3;
}

function draftFromProposal(proposal: CatalogProposal): ProposalDraft {
  return {
    raw_value: proposal.raw_value,
    source_system: proposal.source_system,
    source_field: proposal.source_field,
    suggested_term: proposal.suggested_term,
    definition: proposal.definition,
    synonyms: joinCsv(proposal.synonyms),
    confidence: confidenceToBucket(proposal.confidence),
    reason: proposal.reason,
    reviewer_note: proposal.reviewer_note,
    affected_questions: joinCsv(proposal.affected_questions),
    affected_read_models: joinCsv(proposal.affected_read_models),
  };
}

function inputFromDraft(draft: ProposalDraft): CatalogProposalUpdateInput {
  return {
    raw_value: draft.raw_value,
    source_system: draft.source_system,
    source_field: draft.source_field,
    suggested_term: draft.suggested_term,
    definition: draft.definition,
    synonyms: splitCsv(draft.synonyms),
    confidence: bucketToConfidence(draft.confidence),
    reason: draft.reason,
    reviewer_note: draft.reviewer_note,
    affected_questions: splitCsv(draft.affected_questions),
    affected_read_models: splitCsv(draft.affected_read_models),
  };
}

function createDefaultProposal(): CatalogProposalCreateInput {
  return {
    raw_value: "New source value",
    source_system: "salesforce",
    source_field: "LeadSource",
    suggested_term: "unknown/review_needed",
    definition: "Needs human business definition.",
    synonyms: [],
    confidence: 0.3,
    reason: "Added manually for catalog review.",
    reviewer_note: "",
    affected_questions: [],
    affected_read_models: [],
    source_type: "manual",
    source_reference_id: null,
  };
}

function formatPatch(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function CatalogProposalReview() {
  const proposalsQuery = useCatalogProposals();
  const createProposal = useCreateCatalogProposal();
  const updateProposal = useUpdateCatalogProposal();
  const reviewProposal = useReviewCatalogProposal();
  const draftPatch = useCatalogDraftPatch();

  const proposals = proposalsQuery.data?.items ?? EMPTY_PROPOSALS;
  const [selectedId, setSelectedId] = React.useState("");

  React.useEffect(() => {
    if (!selectedId && proposals[0]) {
      setSelectedId(proposals[0].id);
    }
  }, [proposals, selectedId]);

  const selected = React.useMemo(() => {
    return (
      proposals.find((proposal) => proposal.id === selectedId) ?? proposals[0]
    );
  }, [proposals, selectedId]);

  const impactPreview = useCatalogProposalImpactPreview(selected?.id ?? null);
  const proposalHistory = useCatalogProposalHistory(selected?.id ?? null);
  const versionHistory = useCatalogVersionHistory(selected?.suggested_term ?? null);
  const [draft, setDraft] = React.useState<ProposalDraft | null>(null);

  React.useEffect(() => {
    if (selected) {
      setDraft(draftFromProposal(selected));
    } else {
      setDraft(null);
    }
  }, [selected]);

  const counts = React.useMemo(() => {
    return proposals.reduce(
      (acc, proposal) => {
        acc[proposal.status] += 1;
        return acc;
      },
      { proposed: 0, approved: 0, rejected: 0, unresolved: 0 },
    );
  }, [proposals]);

  const approvedProposalIds = React.useMemo(
    () =>
      proposals
        .filter((proposal) => proposal.status === "approved")
        .map((proposal) => proposal.id),
    [proposals],
  );

  const isBusy =
    createProposal.isPending ||
    updateProposal.isPending ||
    reviewProposal.isPending ||
    draftPatch.isPending;
  const reviewIsClosed =
    selected?.status === "approved" || selected?.status === "rejected";

  function updateDraft(patch: Partial<ProposalDraft>) {
    setDraft((current) => (current ? { ...current, ...patch } : current));
  }

  async function addProposal() {
    const created = await createProposal.mutateAsync(createDefaultProposal());
    setSelectedId(created.id);
  }

  async function saveSelected() {
    if (!selected || !draft) {
      return null;
    }
    return updateProposal.mutateAsync({
      id: selected.id,
      input: inputFromDraft(draft),
    });
  }

  async function reviewSelected(status: CatalogProposalStatus) {
    if (!selected || !draft || reviewIsClosed) {
      return;
    }
    await saveSelected();
    await reviewProposal.mutateAsync({
      id: selected.id,
      input: {
        status,
        reviewer_note: draft.reviewer_note,
        reason: draft.reason || "catalog_proposal_review",
      },
    });
  }

  async function generatePatch() {
    await draftPatch.mutateAsync({ proposal_ids: approvedProposalIds });
  }

  const patchText =
    draftPatch.data && draftPatch.data.patch.length > 0
      ? formatPatch(draftPatch.data.patch)
      : "No approved proposals have been converted into a backend draft patch yet.";

  return (
    <section className="space-y-4 rounded-md border bg-muted/20 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-sm font-semibold">
            Semantic Catalog Proposal Review V1
          </h2>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-muted-foreground">
            Human review layer for agent or tool proposed mappings. Reviewers
            edit the business meaning, save through the semantic catalog API,
            and approved proposals become candidates for catalog versions.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {statusBadge("proposed")}
          {statusBadge("approved")}
          {statusBadge("rejected")}
          {statusBadge("unresolved")}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-md border bg-background/70 p-3">
          <div className="text-xs text-muted-foreground">In review</div>
          <div className="mt-1 text-2xl font-semibold">{counts.proposed}</div>
        </div>
        <div className="rounded-md border bg-background/70 p-3">
          <div className="text-xs text-muted-foreground">Approved</div>
          <div className="mt-1 text-2xl font-semibold">{counts.approved}</div>
        </div>
        <div className="rounded-md border bg-background/70 p-3">
          <div className="text-xs text-muted-foreground">Rejected</div>
          <div className="mt-1 text-2xl font-semibold">{counts.rejected}</div>
        </div>
        <div className="rounded-md border bg-background/70 p-3">
          <div className="text-xs text-muted-foreground">Unresolved</div>
          <div className="mt-1 text-2xl font-semibold">{counts.unresolved}</div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              onClick={() => void addProposal()}
              className="gap-2"
              disabled={isBusy}
            >
              <Plus className="h-4 w-4" />
              Add proposal
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void proposalsQuery.refetch()}
              className="gap-2"
              disabled={isBusy}
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
          </div>

          {proposalsQuery.isLoading && (
            <div className="rounded-md border bg-background p-3 text-sm text-muted-foreground">
              Loading proposals...
            </div>
          )}

          {proposalsQuery.isError && (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              Failed to load catalog proposals.
            </div>
          )}

          {!proposalsQuery.isLoading && proposals.length === 0 && (
            <div className="rounded-md border bg-background p-3 text-sm text-muted-foreground">
              No proposals yet. Add one to start a persisted review draft.
            </div>
          )}

          <div className="space-y-2">
            {proposals.map((proposal) => (
              <button
                key={proposal.id}
                type="button"
                onClick={() => setSelectedId(proposal.id)}
                className={cn(
                  "w-full rounded-md border bg-background p-3 text-left transition-colors hover:bg-accent",
                  proposal.id === selected?.id && "border-primary bg-primary/5",
                )}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-sm font-medium">{proposal.raw_value}</div>
                  {statusBadge(proposal.status)}
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  {proposal.source_system}.{proposal.source_field} {"->"}{" "}
                  {proposal.suggested_term}
                </div>
              </button>
            ))}
          </div>
        </div>

        {selected && draft && (
          <div className="space-y-4 rounded-md border bg-background p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-sm font-semibold">{selected.raw_value}</div>
                <div className="mt-1 text-xs text-muted-foreground">
                  Human reviewer can edit the business meaning before approval.
                </div>
              </div>
              {statusBadge(selected.status)}
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="raw-value">Raw value</Label>
                <Input
                  id="raw-value"
                  value={draft.raw_value}
                  onChange={(event) =>
                    updateDraft({ raw_value: event.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="suggested-term">Suggested term</Label>
                <Input
                  id="suggested-term"
                  value={draft.suggested_term}
                  onChange={(event) =>
                    updateDraft({ suggested_term: event.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="source-system">Source system</Label>
                <NativeSelect
                  id="source-system"
                  value={draft.source_system}
                  onChange={(event) =>
                    updateDraft({ source_system: event.target.value })
                  }
                >
                  <option value="salesforce">salesforce</option>
                  <option value="carestack">carestack</option>
                  <option value="fusion">fusion</option>
                </NativeSelect>
              </div>
              <div className="space-y-2">
                <Label htmlFor="source-field">Source field</Label>
                <Input
                  id="source-field"
                  value={draft.source_field}
                  onChange={(event) =>
                    updateDraft({ source_field: event.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confidence">Confidence</Label>
                <NativeSelect
                  id="confidence"
                  value={draft.confidence}
                  onChange={(event) =>
                    updateDraft({
                      confidence: event.target.value as ConfidenceBucket,
                    })
                  }
                >
                  <option value="low">low</option>
                  <option value="medium">medium</option>
                  <option value="high">high</option>
                </NativeSelect>
              </div>
              <div className="space-y-2">
                <Label htmlFor="synonyms">Synonyms</Label>
                <Input
                  id="synonyms"
                  value={draft.synonyms}
                  onChange={(event) =>
                    updateDraft({ synonyms: event.target.value })
                  }
                />
              </div>
            </div>

            <div className="grid gap-3 lg:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="definition">Business definition</Label>
                <textarea
                  id="definition"
                  value={draft.definition}
                  onChange={(event) =>
                    updateDraft({ definition: event.target.value })
                  }
                  className="min-h-[92px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="reason">Agent/tool reason</Label>
                <textarea
                  id="reason"
                  value={draft.reason}
                  onChange={(event) => updateDraft({ reason: event.target.value })}
                  className="min-h-[92px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                />
              </div>
            </div>

            <div className="grid gap-3 lg:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="affected-questions">Affected questions</Label>
                <Input
                  id="affected-questions"
                  value={draft.affected_questions}
                  onChange={(event) =>
                    updateDraft({ affected_questions: event.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="affected-read-models">
                  Affected read models
                </Label>
                <Input
                  id="affected-read-models"
                  value={draft.affected_read_models}
                  onChange={(event) =>
                    updateDraft({ affected_read_models: event.target.value })
                  }
                />
              </div>
              <div className="space-y-2 lg:col-span-3">
                <Label htmlFor="reviewer-note">Reviewer note</Label>
                <Input
                  id="reviewer-note"
                  value={draft.reviewer_note}
                  onChange={(event) =>
                    updateDraft({ reviewer_note: event.target.value })
                  }
                />
              </div>
            </div>

            <div className="rounded-md border bg-muted/30 p-3">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
                <History className="h-3.5 w-3.5" />
                Impact preview
              </div>
              <div className="mt-2 grid gap-2 text-xs leading-5 text-muted-foreground md:grid-cols-3">
                <div>
                  <span className="font-medium text-foreground">Questions:</span>{" "}
                  {impactPreview.data?.impact.affected_questions.join(", ") ||
                    draft.affected_questions ||
                    "not assigned"}
                </div>
                <div>
                  <span className="font-medium text-foreground">Read models:</span>{" "}
                  {impactPreview.data?.impact.affected_read_models.join(", ") ||
                    draft.affected_read_models ||
                    "not assigned"}
                </div>
                <div>
                  <span className="font-medium text-foreground">Approval:</span>{" "}
                  {impactPreview.data?.can_approve === false
                    ? impactPreview.data.blockers.join(", ")
                    : "no blockers"}
                </div>
              </div>
            </div>

            <div className="grid gap-3 lg:grid-cols-2">
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
                  <History className="h-3.5 w-3.5" />
                  Review history
                </div>
                <div className="mt-2 space-y-2 text-xs leading-5">
                  {proposalHistory.isLoading && (
                    <div className="text-muted-foreground">Loading history...</div>
                  )}
                  {proposalHistory.isError && (
                    <div className="text-destructive">History is unavailable.</div>
                  )}
                  {proposalHistory.data?.items.length === 0 && (
                    <div className="text-muted-foreground">No review events yet.</div>
                  )}
                  {proposalHistory.data?.items.map((event) => (
                    <div key={`${event.action}-${event.occurred_at}`}>
                      <div className="font-medium text-foreground">
                        {event.action} · {event.status}
                      </div>
                      <div className="text-muted-foreground">
                        {formatDateTime(event.occurred_at)}
                        {event.reason ? ` · ${event.reason}` : ""}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-md border bg-muted/30 p-3">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
                  <History className="h-3.5 w-3.5" />
                  Version history
                </div>
                <div className="mt-2 space-y-2 text-xs leading-5">
                  {versionHistory.isLoading && (
                    <div className="text-muted-foreground">Loading versions...</div>
                  )}
                  {versionHistory.isError && (
                    <div className="text-destructive">Versions are unavailable.</div>
                  )}
                  {versionHistory.data?.items.length === 0 && (
                    <div className="text-muted-foreground">
                      No approved versions for this term yet.
                    </div>
                  )}
                  {versionHistory.data?.items.slice(0, 3).map((version) => (
                    <div key={version.id}>
                      <div className="font-medium text-foreground">
                        v{version.version} · {version.review_status}
                      </div>
                      <div className="text-muted-foreground">
                        {formatDateTime(version.approved_at)} · {version.reason}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                onClick={() => void saveSelected()}
                disabled={isBusy}
                className="gap-2"
              >
                <Save className="h-4 w-4" />
                Save changes
              </Button>
              <Button
                size="sm"
                onClick={() => void reviewSelected("approved")}
                disabled={isBusy || reviewIsClosed}
              >
                Approve
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => void reviewSelected("unresolved")}
                disabled={isBusy || reviewIsClosed}
              >
                Mark unresolved
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => void reviewSelected("rejected")}
                disabled={isBusy || reviewIsClosed}
              >
                Reject
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => void reviewSelected("proposed")}
                disabled={isBusy || reviewIsClosed || selected.status !== "unresolved"}
              >
                Return to review
              </Button>
            </div>
          </div>
        )}
      </div>

      <div className="rounded-md border bg-background p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="text-sm font-semibold">
              Backend approved catalog patch
            </div>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              Generated from approved proposals through the semantic catalog API.
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => void generatePatch()}
            disabled={isBusy || approvedProposalIds.length === 0}
          >
            Generate patch
          </Button>
        </div>
        <pre className="mt-3 max-h-80 overflow-auto rounded-md border bg-muted/20 p-3 whitespace-pre-wrap text-xs leading-6">
          {patchText}
        </pre>
      </div>
    </section>
  );
}
