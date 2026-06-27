"use client";

import { useState } from "react";
import {
  Building2,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  Link2,
  Plus,
  Save,
  Sparkles,
  Store,
  Trash2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import {
  useCreateVendor,
  useCreateVendorClaim,
  useVendorClaimSuggestions,
  useDeactivateVendor,
  useDeleteVendorClaim,
  useDeleteVendorCost,
  useSetVendorCost,
  useUnassignedSignatures,
  useUpdateVendor,
  useVendorClaims,
  useVendorCosts,
  useVendors,
} from "@/lib/api/hooks/useVendors";
import {
  VENDOR_KIND_LABELS,
  VENDOR_KINDS,
  type Vendor,
  type VendorKind,
} from "@/lib/api/schemas/vendor";

function kindBadge(kind: string) {
  if (kind === "in_house") {
    return (
      <Badge variant="secondary" className="gap-1">
        <Building2 className="h-3 w-3" />
        In-house
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="gap-1">
      <Store className="h-3 w-3" />
      Agency
    </Badge>
  );
}

function fmtMoney(amount: number, currency: string): string {
  try {
    return amount.toLocaleString("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    });
  } catch {
    return `${amount.toLocaleString()} ${currency}`;
  }
}

function feeSummary(vendor: Vendor): string {
  if (vendor.flat_monthly_fee) {
    return vendor.monthly_fee != null
      ? `${fmtMoney(vendor.monthly_fee, vendor.fee_currency)} / mo`
      : "—";
  }
  return "Per month";
}

interface VendorFormState {
  name: string;
  kind: VendorKind;
  color: string;
  notes: string;
  flatMonthlyFee: boolean;
  monthlyFee: string;
  currency: string;
}

const EMPTY_FORM: VendorFormState = {
  name: "",
  kind: "agency",
  color: "",
  notes: "",
  flatMonthlyFee: true,
  monthlyFee: "",
  currency: "USD",
};

// Build the fee part of a create/update payload from form state. The amount is
// only sent in flat mode with a valid value; in per-month mode it is omitted
// (left unchanged) so a previously-set flat fee is preserved if the operator
// toggles back — and the backend's "None = unchanged" PATCH semantics match the
// intent instead of receiving an ignored null.
function feePayload(form: VendorFormState): {
  flat_monthly_fee: boolean;
  fee_currency: string;
  monthly_fee?: number;
} {
  const flat = form.flatMonthlyFee;
  const parsed = Number(form.monthlyFee);
  const hasAmount =
    flat && form.monthlyFee.trim() !== "" && !Number.isNaN(parsed);
  return {
    flat_monthly_fee: flat,
    fee_currency: form.currency.trim() || "USD",
    ...(hasAmount ? { monthly_fee: parsed } : {}),
  };
}

function VendorFormFields({
  state,
  onChange,
  perMonthSlot,
}: {
  state: VendorFormState;
  onChange: (next: VendorFormState) => void;
  perMonthSlot?: React.ReactNode;
}) {
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="vendor-name">
          Name <span className="text-destructive">*</span>
        </Label>
        <Input
          id="vendor-name"
          value={state.name}
          onChange={(e) => onChange({ ...state, name: e.target.value })}
          placeholder="Dima Media"
          aria-invalid={state.name.trim() === ""}
        />
        {state.name.trim() === "" ? (
          <p className="text-xs text-muted-foreground">
            Name is required before you can save.
          </p>
        ) : null}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="vendor-kind">Kind</Label>
          <NativeSelect
            id="vendor-kind"
            ariaLabel="Vendor kind"
            value={state.kind}
            onChange={(e) =>
              onChange({ ...state, kind: e.target.value as VendorKind })
            }
          >
            {VENDOR_KINDS.map((k) => (
              <option key={k} value={k}>
                {VENDOR_KIND_LABELS[k]}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="vendor-color">Color</Label>
          <Input
            id="vendor-color"
            value={state.color}
            onChange={(e) => onChange({ ...state, color: e.target.value })}
            placeholder="#2563eb"
          />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="vendor-notes">Notes</Label>
        <Input
          id="vendor-notes"
          value={state.notes}
          onChange={(e) => onChange({ ...state, notes: e.target.value })}
          placeholder="Monthly retainer, contact, etc."
        />
      </div>

      {/* Monthly spend (ENG-573) */}
      <div className="space-y-3 rounded-md border p-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <Label>Same amount every month</Label>
            <p className="text-xs text-muted-foreground">
              On = one flat monthly fee. Off = set a different amount per month.
            </p>
          </div>
          <Switch
            checked={state.flatMonthlyFee}
            onCheckedChange={(v) =>
              onChange({ ...state, flatMonthlyFee: v })
            }
            aria-label="Same amount every month"
          />
        </div>
        {state.flatMonthlyFee ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="vendor-fee">Monthly amount</Label>
              <Input
                id="vendor-fee"
                inputMode="decimal"
                value={state.monthlyFee}
                onChange={(e) =>
                  onChange({ ...state, monthlyFee: e.target.value })
                }
                placeholder="5000"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="vendor-ccy">Currency</Label>
              <Input
                id="vendor-ccy"
                value={state.currency}
                maxLength={3}
                onChange={(e) =>
                  onChange({
                    ...state,
                    currency: e.target.value.toUpperCase(),
                  })
                }
                placeholder="USD"
              />
            </div>
          </div>
        ) : (
          (perMonthSlot ?? (
            <p className="text-xs text-muted-foreground">
              Save the vendor first, then add each month&apos;s amount here.
            </p>
          ))
        )}
      </div>
    </div>
  );
}

function MonthlyCostsEditor({
  vendorId,
  currency,
}: {
  vendorId: string;
  currency: string;
}) {
  const { toast } = useToast();
  const { data, isLoading } = useVendorCosts(vendorId);
  const setCost = useSetVendorCost(vendorId);
  const deleteCost = useDeleteVendorCost(vendorId);
  const [month, setMonth] = useState("");
  const [amount, setAmount] = useState("");

  const rows = data ?? [];

  function add() {
    const parsed = Number(amount);
    if (!month || amount.trim() === "" || Number.isNaN(parsed)) return;
    setCost.mutate(
      { period_month: month, amount: parsed },
      {
        onSuccess: () => {
          setAmount("");
        },
        onError: (err) =>
          toast({
            title: "Could not save month",
            description: err.message,
            variant: "destructive",
          }),
      },
    );
  }

  return (
    <div className="space-y-2">
      <Label className="text-xs text-muted-foreground">Amount per month</Label>
      {isLoading ? (
        <Skeleton className="h-8 w-full" />
      ) : rows.length > 0 ? (
        <div className="divide-y rounded-md border">
          {rows.map((c) => (
            <div
              key={c.id}
              className="flex items-center justify-between gap-2 px-2 py-1.5 text-sm"
            >
              <span className="flex items-center gap-1.5 font-mono text-xs">
                <CalendarDays className="h-3.5 w-3.5 text-muted-foreground" />
                {c.period_month}
              </span>
              <span className="ml-auto tabular-nums">
                {fmtMoney(c.amount, currency)}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                aria-label={`Remove ${c.period_month}`}
                onClick={() => deleteCost.mutate(c.period_month)}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">No months set yet.</p>
      )}
      <div className="flex items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="cost-month" className="text-xs">
            Month
          </Label>
          <Input
            id="cost-month"
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="w-40"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="cost-amount" className="text-xs">
            Amount ({currency})
          </Label>
          <Input
            id="cost-amount"
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="7000"
            className="w-32"
          />
        </div>
        <Button
          type="button"
          size="sm"
          className="gap-1"
          disabled={!month || amount.trim() === "" || setCost.isPending}
          onClick={add}
        >
          <Plus className="h-4 w-4" />
          Add
        </Button>
      </div>
    </div>
  );
}

function VendorClaimsEditor({
  vendorId,
  vendorName,
}: {
  vendorId: string;
  vendorName: string;
}) {
  const { toast } = useToast();
  const { data: claims, isLoading } = useVendorClaims(vendorId);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const sigs = useUnassignedSignatures(pickerOpen);
  const suggestions = useVendorClaimSuggestions(vendorId, pickerOpen);
  const createClaim = useCreateVendorClaim(vendorId);
  const deleteClaim = useDeleteVendorClaim(vendorId);

  const claimRows = claims ?? [];
  const bound = new Set(
    claimRows.map((c) => `${c.match_field}=${c.match_value}`),
  );
  const f = filter.trim().toLowerCase();
  const items = (sigs.data?.items ?? []).filter(
    (s) =>
      !bound.has(`${s.match_field}=${s.value}`) &&
      (f === "" || `${s.match_field} ${s.value}`.toLowerCase().includes(f)),
  );
  const suggested = (suggestions.data?.items ?? []).filter(
    (s) => !bound.has(`${s.match_field}=${s.value}`),
  );

  function attach(field: string, value: string, origin: string = "manual") {
    createClaim.mutate(
      { match_field: field, match_op: "eq", match_value: value, origin },
      {
        onSuccess: (c) => {
          if (c === null) {
            toast({ title: "Vendor not found", variant: "destructive" });
          }
        },
        onError: (err) =>
          toast({
            title: "Could not bind",
            description: err.message,
            variant: "destructive",
          }),
      },
    );
  }

  return (
    <div className="space-y-3 rounded-md border p-3">
      <div>
        <Label>Claimed traffic</Label>
        <p className="text-xs text-muted-foreground">
          Bind traffic signatures to this vendor — matching leads resolve to it;
          unbound traffic stays Unassigned.
        </p>
      </div>
      {isLoading ? (
        <Skeleton className="h-8 w-full" />
      ) : claimRows.length > 0 ? (
        <div className="divide-y rounded-md border">
          {claimRows.map((c) => (
            <div
              key={c.id}
              className="flex items-center gap-2 px-2 py-1.5 text-sm"
            >
              <Badge variant="outline" className="font-mono text-[10px]">
                {c.match_field}
              </Badge>
              <span className="text-xs text-muted-foreground">{c.match_op}</span>
              <span className="truncate font-medium">{c.match_value}</span>
              {c.origin === "agent" ? (
                <Badge variant="secondary" className="text-[10px]">
                  agent
                </Badge>
              ) : null}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="ml-auto h-7 w-7 shrink-0 p-0 text-muted-foreground hover:text-destructive"
                aria-label={`Remove claim ${c.match_value}`}
                onClick={() => deleteClaim.mutate(c.id)}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">No traffic bound yet.</p>
      )}

      <button
        type="button"
        onClick={() => setPickerOpen((o) => !o)}
        className="flex items-center gap-1 text-sm font-medium text-primary hover:underline"
      >
        {pickerOpen ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
        <Link2 className="h-4 w-4" />
        Bind unassigned traffic
      </button>
      {pickerOpen && (suggestions.isLoading || suggested.length > 0) ? (
        <div className="space-y-1.5 rounded-md border border-primary/30 bg-primary/5 p-2">
          <div className="flex items-center gap-1.5 text-xs font-medium text-primary">
            <Sparkles className="h-3.5 w-3.5" />
            Suggested for {vendorName}
          </div>
          {suggestions.isLoading ? (
            <Skeleton className="h-8 w-full" />
          ) : (
            suggested.slice(0, 20).map((s) => (
              <div
                key={`sg-${s.match_field}=${s.value}`}
                className="flex items-center gap-2 text-sm"
              >
                <Badge variant="outline" className="font-mono text-[10px]">
                  {s.match_field}
                </Badge>
                <span className="truncate" title={s.rationale}>
                  {s.value}
                </span>
                <span className="ml-auto shrink-0 text-xs tabular-nums text-muted-foreground">
                  {s.lead_count.toLocaleString()} leads
                </span>
                <Button
                  type="button"
                  size="sm"
                  className="h-7 shrink-0 gap-1"
                  disabled={createClaim.isPending}
                  onClick={() => attach(s.match_field, s.value, "agent")}
                >
                  <Plus className="h-3.5 w-3.5" />
                  Accept
                </Button>
              </div>
            ))
          )}
          {suggested.length > 20 ? (
            <p className="text-[11px] text-muted-foreground">
              +{(suggested.length - 20).toLocaleString()} more — find them in the
              full list below.
            </p>
          ) : null}
        </div>
      ) : null}
      {pickerOpen ? (
        <div className="space-y-2">
          <Input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter signatures…"
            className="h-8"
          />
          {sigs.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : items.length > 0 ? (
            <div className="max-h-56 divide-y overflow-y-auto rounded-md border">
              {items.slice(0, 100).map((s) => (
                <div
                  key={`${s.match_field}=${s.value}`}
                  className="flex items-center gap-2 px-2 py-1.5 text-sm"
                >
                  <Badge variant="outline" className="font-mono text-[10px]">
                    {s.match_field}
                  </Badge>
                  <span className="truncate">{s.value}</span>
                  <span className="ml-auto shrink-0 text-xs tabular-nums text-muted-foreground">
                    {s.lead_count.toLocaleString()} leads
                  </span>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-7 shrink-0 gap-1"
                    disabled={createClaim.isPending}
                    onClick={() => attach(s.match_field, s.value)}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Attach
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              No unassigned signatures{filter ? " match the filter" : ""}.
            </p>
          )}
          {items.length > 100 ? (
            <p className="text-[11px] text-muted-foreground">
              Showing the first 100 of {items.length.toLocaleString()} signatures
              — refine the filter to narrow.
            </p>
          ) : null}
          {sigs.data ? (
            <p className="text-[11px] text-muted-foreground">
              Scanned {sigs.data.scanned.toLocaleString()} unassigned leads
              {sigs.data.capped ? " (capped — more exist)" : ""}.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function CreateVendorDialog() {
  const { toast } = useToast();
  const create = useCreateVendor();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<VendorFormState>(EMPTY_FORM);

  function submit() {
    create.mutate(
      {
        name: form.name.trim(),
        kind: form.kind,
        color: form.color.trim() || null,
        notes: form.notes.trim() || null,
        ...feePayload(form),
      },
      {
        onSuccess: (vendor) => {
          toast({
            title: "Vendor created",
            description: `${vendor.name} (${vendor.slug})`,
            variant: "success",
          });
          setForm(EMPTY_FORM);
          setOpen(false);
        },
        onError: (err) => {
          toast({
            title: "Could not create vendor",
            description: err.message,
            variant: "destructive",
          });
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button size="sm" className="gap-2" onClick={() => setOpen(true)}>
        <Plus className="h-4 w-4" />
        Add vendor
      </Button>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New vendor</DialogTitle>
          <DialogDescription>
            A vendor manages a slice of the traffic — an agency, or your own
            in-house team. The slug is derived from the name.
          </DialogDescription>
        </DialogHeader>
        <VendorFormFields state={form} onChange={setForm} />
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            className="gap-2"
            disabled={!form.name.trim() || create.isPending}
            onClick={submit}
          >
            <Save className="h-4 w-4" />
            {create.isPending ? "Creating…" : "Create vendor"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EditVendorDialog({
  vendor,
  open,
  onOpenChange,
}: {
  vendor: Vendor;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { toast } = useToast();
  const update = useUpdateVendor();
  const [form, setForm] = useState<VendorFormState>({
    name: vendor.name,
    kind: (vendor.kind as VendorKind) ?? "agency",
    color: vendor.color ?? "",
    notes: vendor.notes ?? "",
    flatMonthlyFee: vendor.flat_monthly_fee,
    monthlyFee: vendor.monthly_fee != null ? String(vendor.monthly_fee) : "",
    currency: vendor.fee_currency || "USD",
  });

  function submit() {
    update.mutate(
      {
        id: vendor.id,
        patch: {
          name: form.name.trim(),
          kind: form.kind,
          color: form.color.trim() || null,
          notes: form.notes.trim() || null,
          ...feePayload(form),
        },
      },
      {
        onSuccess: () => {
          toast({ title: "Vendor saved", variant: "success" });
          onOpenChange(false);
        },
        onError: (err) => {
          toast({
            title: "Could not save vendor",
            description: err.message,
            variant: "destructive",
          });
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>Edit {vendor.name}</DialogTitle>
          <DialogDescription>
            Slug <code className="font-mono">{vendor.slug}</code> is immutable —
            it ties the vendor to its resolved traffic.
          </DialogDescription>
        </DialogHeader>
        <VendorFormFields
          state={form}
          onChange={setForm}
          perMonthSlot={
            <MonthlyCostsEditor
              vendorId={vendor.id}
              currency={form.currency || "USD"}
            />
          }
        />
        <VendorClaimsEditor vendorId={vendor.id} vendorName={vendor.name} />
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            className="gap-2"
            disabled={!form.name.trim() || update.isPending}
            onClick={submit}
          >
            <Save className="h-4 w-4" />
            {update.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function VendorRow({ vendor }: { vendor: Vendor }) {
  const { toast } = useToast();
  const update = useUpdateVendor();
  const [editOpen, setEditOpen] = useState(false);

  function toggleActive(next: boolean) {
    update.mutate(
      { id: vendor.id, patch: { active: next } },
      {
        onError: (err) =>
          toast({
            title: "Could not update vendor",
            description: err.message,
            variant: "destructive",
          }),
      },
    );
  }

  return (
    <tr className="border-b last:border-0 align-middle">
      <td className="px-3 py-2">
        <div className="flex items-center gap-2">
          {vendor.color ? (
            <span
              className="h-3 w-3 shrink-0 rounded-full border"
              style={{ backgroundColor: vendor.color }}
              aria-hidden
            />
          ) : (
            <span className="h-3 w-3 shrink-0" aria-hidden />
          )}
          <span className="font-medium">{vendor.name}</span>
        </div>
      </td>
      <td className="px-3 py-2">{kindBadge(vendor.kind)}</td>
      <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
        {vendor.slug}
      </td>
      <td className="px-3 py-2 tabular-nums">{feeSummary(vendor)}</td>
      <td className="px-3 py-2">
        {vendor.source_node_id ? (
          <Badge variant="success">Linked</Badge>
        ) : (
          <span
            className="text-xs text-muted-foreground"
            title="No resolved traffic carries this vendor yet"
          >
            No traffic yet
          </span>
        )}
      </td>
      <td className="px-3 py-2">
        <Switch
          checked={vendor.active}
          onCheckedChange={toggleActive}
          aria-label={`${vendor.name} active`}
        />
      </td>
      <td className="px-3 py-2 text-right">
        <Button variant="ghost" size="sm" onClick={() => setEditOpen(true)}>
          Edit
        </Button>
        {/* Mount only while open so the form re-seeds from the current vendor
            (props can change after a refetch). */}
        {editOpen ? (
          <EditVendorDialog
            vendor={vendor}
            open={editOpen}
            onOpenChange={setEditOpen}
          />
        ) : null}
      </td>
    </tr>
  );
}

export function VendorsManager() {
  const { data, isLoading, isError, error } = useVendors();
  const vendors = data ?? [];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>Vendors</CardTitle>
            <CardDescription>
              Who manages each slice of the traffic — agencies and your own
              in-house team — and what each costs per month. Anything not bound
              to a vendor stays Unassigned. Binding rules and cost-per-lead land
              in later steps.
            </CardDescription>
          </div>
          <CreateVendorDialog />
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : isError ? (
          <p className="py-6 text-center text-sm text-destructive">
            Failed to load vendors: {(error as Error)?.message}
          </p>
        ) : vendors.length === 0 ? (
          <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
            No vendors yet. Add your agencies and your in-house team to start
            distributing traffic.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Name</th>
                  <th className="px-3 py-2 font-medium">Kind</th>
                  <th className="px-3 py-2 font-medium">Slug</th>
                  <th className="px-3 py-2 font-medium">Monthly fee</th>
                  <th className="px-3 py-2 font-medium">Traffic</th>
                  <th className="px-3 py-2 font-medium">Active</th>
                  <th className="px-3 py-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {vendors.map((v) => (
                  <VendorRow key={v.id} vendor={v} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
