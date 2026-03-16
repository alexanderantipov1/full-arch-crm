import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";
import { apiRequest } from "@/lib/queryClient";
import {
  MapPin, Plus, Save, Loader2, Building2, Phone, Mail,
  Users, Settings, TrendingUp, DollarSign,
} from "lucide-react";

interface PracticeLocation {
  id: number; name: string; address: string; city: string; state: string;
  zip: string | null; phone: string | null; email: string | null;
  npi: string | null; taxId: string | null; isMain: boolean; isActive: boolean;
  operatories: number | null; providerCount: number | null; notes: string | null;
}

const US_STATES = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"];

function LocationDialog({ open, onClose, onSaved, edit }: {
  open: boolean; onClose: () => void; onSaved: () => void;
  edit?: PracticeLocation | null;
}) {
  const { toast } = useToast();
  const [form, setForm] = useState({
    name: edit?.name || "", address: edit?.address || "",
    city: edit?.city || "", state: edit?.state || "CA", zip: edit?.zip || "",
    phone: edit?.phone || "", email: edit?.email || "",
    npi: edit?.npi || "", taxId: edit?.taxId || "",
    isMain: edit?.isMain || false, isActive: edit?.isActive !== false,
    operatories: edit?.operatories?.toString() || "4",
    providerCount: edit?.providerCount?.toString() || "1",
    notes: edit?.notes || "",
  });

  const mut = useMutation({
    mutationFn: () => {
      const payload = {
        ...form,
        operatories: parseInt(form.operatories) || 4,
        providerCount: parseInt(form.providerCount) || 1,
        zip: form.zip || null, npi: form.npi || null, taxId: form.taxId || null,
        phone: form.phone || null, email: form.email || null,
      };
      if (edit) return apiRequest("PUT", `/api/locations/${edit.id}`, payload);
      return apiRequest("POST", "/api/locations", payload);
    },
    onSuccess: () => { toast({ title: edit ? "Location updated" : "Location added" }); onSaved(); onClose(); },
    onError: () => toast({ title: "Error", variant: "destructive" }),
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MapPin className="h-4 w-4" /> {edit ? "Edit Location" : "Add Location"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <Label>Practice Name *</Label>
            <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Downtown Dental" data-testid="input-location-name" />
          </div>
          <div>
            <Label>Street Address *</Label>
            <Input value={form.address} onChange={e => setForm(f => ({ ...f, address: e.target.value }))} placeholder="123 Main St" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <Label>City *</Label>
              <Input value={form.city} onChange={e => setForm(f => ({ ...f, city: e.target.value }))} />
            </div>
            <div>
              <Label>State</Label>
              <Select value={form.state} onValueChange={v => setForm(f => ({ ...f, state: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{US_STATES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>ZIP Code</Label><Input value={form.zip} onChange={e => setForm(f => ({ ...f, zip: e.target.value }))} /></div>
            <div><Label>Phone</Label><Input value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Email</Label><Input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} /></div>
            <div><Label>NPI</Label><Input value={form.npi} onChange={e => setForm(f => ({ ...f, npi: e.target.value }))} /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Operatories</Label><Input type="number" value={form.operatories} onChange={e => setForm(f => ({ ...f, operatories: e.target.value }))} /></div>
            <div><Label>Provider Count</Label><Input type="number" value={form.providerCount} onChange={e => setForm(f => ({ ...f, providerCount: e.target.value }))} /></div>
          </div>
          <div className="flex items-center justify-between">
            <Label>Main / Headquarters Location</Label>
            <Switch checked={form.isMain} onCheckedChange={v => setForm(f => ({ ...f, isMain: v }))} />
          </div>
          <div><Label>Notes</Label><Textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} rows={2} /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending || !form.name || !form.address || !form.city} data-testid="button-save-location">
            {mut.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Save className="h-4 w-4 mr-1" />}
            Save Location
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function MultiLocationPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editLocation, setEditLocation] = useState<PracticeLocation | null>(null);

  const { data: locations = [], isLoading } = useQuery<PracticeLocation[]>({
    queryKey: ["/api/locations"],
    queryFn: () => fetch("/api/locations", { credentials: "include" }).then(r => r.json()),
  });
  const { data: patients = [] } = useQuery<any[]>({ queryKey: ["/api/patients"] });
  const { data: providers = [] } = useQuery<any[]>({ queryKey: ["/api/practice-providers"] });

  const totalOps = locations.reduce((a, l) => a + (l.operatories || 0), 0);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Multi-Location Management</h1>
          <p className="text-sm text-muted-foreground">Manage multiple practice locations, operatories, and provider assignments</p>
        </div>
        <Button onClick={() => { setEditLocation(null); setDialogOpen(true); }} data-testid="button-add-location">
          <Plus className="h-4 w-4 mr-1.5" /> Add Location
        </Button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Locations", value: locations.length },
          { label: "Total Operatories", value: totalOps },
          { label: "Active Providers", value: providers.length },
          { label: "Total Patients", value: patients.length },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-4 pb-4">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">{k.label}</div>
              <div className="text-2xl font-bold font-mono" data-testid={`kpi-${k.label.toLowerCase().replace(/ /g, "-")}`}>{k.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : locations.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="pt-12 pb-12 flex flex-col items-center gap-3 text-muted-foreground">
            <MapPin className="h-10 w-10 opacity-30" />
            <p className="text-sm">No locations — add your first practice location</p>
            <Button onClick={() => setDialogOpen(true)} variant="outline" size="sm"><Plus className="h-4 w-4 mr-1" /> Add Location</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {locations.map(loc => (
            <Card key={loc.id} className="hover:border-primary/40 transition-colors" data-testid={`card-location-${loc.id}`}>
              <CardContent className="pt-4 pb-4">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Building2 className="h-5 w-5 text-primary shrink-0" />
                    <div>
                      <div className="font-semibold text-sm">{loc.name}</div>
                      {loc.isMain && <Badge className="text-[10px] bg-primary/10 text-primary border-primary/30 mt-0.5">HQ</Badge>}
                    </div>
                  </div>
                  <button onClick={() => { setEditLocation(loc); setDialogOpen(true); }} className="text-muted-foreground hover:text-primary" data-testid={`edit-${loc.id}`}>
                    <Settings className="h-4 w-4" />
                  </button>
                </div>
                <div className="space-y-1 text-xs text-muted-foreground">
                  <div className="flex items-center gap-1"><MapPin className="h-3 w-3 shrink-0" /><span>{loc.address}, {loc.city}, {loc.state}</span></div>
                  {loc.phone && <div className="flex items-center gap-1"><Phone className="h-3 w-3" />{loc.phone}</div>}
                  {loc.email && <div className="flex items-center gap-1"><Mail className="h-3 w-3" /><span className="truncate">{loc.email}</span></div>}
                </div>
                <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t text-center text-xs">
                  <div><div className="text-muted-foreground">Operatories</div><div className="font-bold text-base">{loc.operatories || 0}</div></div>
                  <div><div className="text-muted-foreground">Providers</div><div className="font-bold text-base">{loc.providerCount || 0}</div></div>
                </div>
                {loc.npi && <div className="mt-2 text-[10px] text-muted-foreground">NPI: {loc.npi}</div>}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <LocationDialog open={dialogOpen} onClose={() => setDialogOpen(false)} onSaved={() => queryClient.invalidateQueries({ queryKey: ["/api/locations"] })} edit={editLocation} />
    </div>
  );
}
