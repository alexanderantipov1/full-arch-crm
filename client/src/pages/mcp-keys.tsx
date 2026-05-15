import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { apiRequest } from "@/lib/queryClient";
import { format } from "date-fns";
import { Copy, Key, Plus, Shield, Trash2, AlertTriangle } from "lucide-react";

interface McpApiKeyRow {
  id: number;
  label: string;
  tenantId: string | null;
  capabilities: string[];
  enabled: boolean;
  createdBy: string | null;
  lastUsedAt: string | null;
  createdAt: string;
  revokedAt: string | null;
}

interface CreatedKey {
  id: number;
  label: string;
  token: string;
  capabilities: string[];
}

interface TenantRow {
  id: string;
  slug: string;
  name: string;
  enabled: boolean;
}

const ALL_CAPS = ["phi.read", "phi.write"] as const;
const TENANT_INHERIT = "__inherit__";

export default function McpKeysPage() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [revealedKey, setRevealedKey] = useState<CreatedKey | null>(null);
  const [newLabel, setNewLabel] = useState("");
  const [newCaps, setNewCaps] = useState<string[]>(["phi.read"]);
  // Sentinel value (TENANT_INHERIT) means "inherit from admin's tenant" —
  // the server uses principalFromReq when the body's tenantId is empty.
  const [newTenantId, setNewTenantId] = useState<string>(TENANT_INHERIT);

  const { data: keys = [], isLoading } = useQuery<McpApiKeyRow[]>({
    queryKey: ["/api/admin/mcp-keys"],
  });

  // Tenant list powers the picker. Single-tenant deployments simply show
  // one option; multi-tenant admins can scope each key to a specific clinic.
  const { data: tenants = [] } = useQuery<TenantRow[]>({
    queryKey: ["/api/admin/tenants"],
  });

  const createMutation = useMutation({
    mutationFn: async (input: {
      label: string;
      capabilities: string[];
      tenantId?: string;
    }) => {
      const res = await apiRequest("POST", "/api/admin/mcp-keys", input);
      return (await res.json()) as CreatedKey;
    },
    onSuccess: (created) => {
      setRevealedKey(created);
      setCreateOpen(false);
      setNewLabel("");
      setNewCaps(["phi.read"]);
      setNewTenantId(TENANT_INHERIT);
      qc.invalidateQueries({ queryKey: ["/api/admin/mcp-keys"] });
    },
    onError: (err: any) => {
      toast({
        title: "Failed to create key",
        description: err?.message ?? "Unknown error",
        variant: "destructive",
      });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await apiRequest("POST", `/api/admin/mcp-keys/${id}/revoke`, {});
      return res.json();
    },
    onSuccess: () => {
      toast({ title: "Key revoked" });
      qc.invalidateQueries({ queryKey: ["/api/admin/mcp-keys"] });
    },
    onError: (err: any) => {
      toast({
        title: "Failed to revoke",
        description: err?.message ?? "Unknown error",
        variant: "destructive",
      });
    },
  });

  function toggleCap(cap: string, checked: boolean) {
    setNewCaps((prev) => (checked ? [...prev, cap] : prev.filter((c) => c !== cap)));
  }

  // tenantId → tenant name, for rendering row badges without an extra fetch
  // per key. Memo-equivalent: tiny dataset, cheap to recompute on render.
  const tenantNameById = new Map(tenants.map((t) => [t.id, t.name]));

  function copyToken(token: string) {
    navigator.clipboard.writeText(token).then(
      () => toast({ title: "Token copied to clipboard" }),
      () => toast({ title: "Copy failed — copy manually", variant: "destructive" }),
    );
  }

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Key className="h-7 w-7" />
            MCP API Keys
          </h1>
          <p className="text-muted-foreground mt-1">
            Bearer tokens that let external AI clients (Claude Code, Codex, …) reach the
            <code className="mx-1 px-1 py-0.5 rounded bg-muted text-xs">/mcp</code>
            tool surface.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)} data-testid="mcp-keys-create">
          <Plus className="h-4 w-4 mr-2" />
          New key
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Issued keys</CardTitle>
          <CardDescription>
            Plaintext is shown only at creation. Lost keys must be revoked and reissued — the
            database stores only a SHA-256 hash.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-muted-foreground py-8 text-center">Loading…</div>
          ) : keys.length === 0 ? (
            <div className="text-muted-foreground py-8 text-center">
              No keys yet. Click "New key" to mint one.
            </div>
          ) : (
            <div className="divide-y">
              {keys.map((k) => (
                <div
                  key={k.id}
                  className="flex items-start justify-between py-3 gap-4"
                  data-testid={`mcp-key-row-${k.id}`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-sm font-medium">{k.label}</span>
                      {k.enabled ? (
                        <Badge variant="outline" className="text-green-600 border-green-600">
                          enabled
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-muted-foreground">
                          revoked
                        </Badge>
                      )}
                      {k.tenantId && (
                        <Badge variant="outline" className="text-xs">
                          tenant: {tenantNameById.get(k.tenantId) ?? k.tenantId.slice(0, 8)}
                        </Badge>
                      )}
                      {(k.capabilities ?? []).map((c) => (
                        <Badge key={c} variant="secondary" className="font-mono text-xs">
                          {c}
                        </Badge>
                      ))}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1 space-x-3">
                      <span>id: {k.id}</span>
                      <span>created: {format(new Date(k.createdAt), "yyyy-MM-dd HH:mm")}</span>
                      <span>
                        last used:{" "}
                        {k.lastUsedAt
                          ? format(new Date(k.lastUsedAt), "yyyy-MM-dd HH:mm")
                          : "never"}
                      </span>
                      {k.createdBy && <span>by: {k.createdBy}</span>}
                    </div>
                  </div>
                  {k.enabled && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        if (confirm(`Revoke "${k.label}"? This is immediate and not reversible.`)) {
                          revokeMutation.mutate(k.id);
                        }
                      }}
                      disabled={revokeMutation.isPending}
                      data-testid={`mcp-key-revoke-${k.id}`}
                    >
                      <Trash2 className="h-4 w-4 mr-1" />
                      Revoke
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New MCP API key</DialogTitle>
            <DialogDescription>
              The bearer token is shown once after creation. Save it immediately into the
              AI client's secret store — there is no way to retrieve it later.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="mcp-key-label">Label</Label>
              <Input
                id="mcp-key-label"
                placeholder="claude-code-clinical, codex-marketing, …"
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
                data-testid="mcp-key-label-input"
              />
            </div>
            <div className="space-y-2">
              <Label>Tenant</Label>
              <p className="text-xs text-muted-foreground">
                Bind this key to a single tenant. A key minted for clinic A can never
                reach clinic B data, even if the token leaks.
              </p>
              <Select value={newTenantId} onValueChange={setNewTenantId}>
                <SelectTrigger data-testid="mcp-key-tenant-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={TENANT_INHERIT}>
                    Inherit (your tenant)
                  </SelectItem>
                  {tenants.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name} ({t.slug})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Capabilities</Label>
              <p className="text-xs text-muted-foreground">
                Scope a key to the minimum it needs. A marketing-AI key can have neither.
              </p>
              {ALL_CAPS.map((cap) => (
                <label key={cap} className="flex items-center gap-2 text-sm cursor-pointer">
                  <Checkbox
                    checked={newCaps.includes(cap)}
                    onCheckedChange={(v) => toggleCap(cap, !!v)}
                    data-testid={`mcp-key-cap-${cap}`}
                  />
                  <span className="font-mono">{cap}</span>
                </label>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() =>
                createMutation.mutate({
                  label: newLabel,
                  capabilities: newCaps,
                  // Empty string here → server uses admin's tenant.
                  tenantId: newTenantId === TENANT_INHERIT ? undefined : newTenantId,
                })
              }
              disabled={!newLabel.trim() || createMutation.isPending}
              data-testid="mcp-key-create-confirm"
            >
              Create key
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reveal dialog — shown ONCE after creation */}
      <Dialog open={!!revealedKey} onOpenChange={(open) => !open && setRevealedKey(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-orange-600">
              <AlertTriangle className="h-5 w-5" />
              Save this token now
            </DialogTitle>
            <DialogDescription>
              This is the only time the plaintext will be visible. Once you close this dialog,
              there's no way to retrieve it — only revoke and reissue.
            </DialogDescription>
          </DialogHeader>
          {revealedKey && (
            <div className="space-y-3 py-2">
              <div>
                <Label>Label</Label>
                <p className="font-mono text-sm">{revealedKey.label}</p>
              </div>
              <div>
                <Label>Capabilities</Label>
                <div className="flex gap-1 flex-wrap mt-1">
                  {revealedKey.capabilities.length === 0 ? (
                    <span className="text-xs text-muted-foreground">(none — read-only)</span>
                  ) : (
                    revealedKey.capabilities.map((c) => (
                      <Badge key={c} variant="secondary" className="font-mono text-xs">
                        {c}
                      </Badge>
                    ))
                  )}
                </div>
              </div>
              <div>
                <Label>Bearer token</Label>
                <div className="flex gap-2 mt-1">
                  <Input
                    readOnly
                    value={revealedKey.token}
                    className="font-mono text-xs"
                    onFocus={(e) => e.currentTarget.select()}
                    data-testid="mcp-key-revealed-token"
                  />
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => copyToken(revealedKey.token)}
                    data-testid="mcp-key-copy"
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground mt-2 flex items-start gap-1">
                  <Shield className="h-3 w-3 mt-0.5 flex-shrink-0" />
                  Use as <code className="px-1 mx-1 rounded bg-muted">Authorization: Bearer …</code>{" "}
                  against the <code className="px-1 mx-1 rounded bg-muted">/mcp</code> endpoint.
                </p>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setRevealedKey(null)} data-testid="mcp-key-revealed-close">
              I've saved it
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
