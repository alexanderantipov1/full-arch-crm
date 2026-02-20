import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { queryClient, apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import {
  Building2, Users, Mail, Calendar, FileText, BarChart3, Plus, Phone, Globe,
  MapPin, Target, ArrowRight, CheckCircle, Clock, AlertCircle, Send,
  Handshake, TrendingUp, Star, ChevronRight, ExternalLink, Loader2,
} from "lucide-react";
import type { UnionOrganization, UnionContact, UnionOutreach, UnionEvent, UnionAgreement } from "@shared/schema";

const PIPELINE_STAGES = [
  { key: "prospect", label: "Prospect", color: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300", icon: Target },
  { key: "contacted", label: "Contacted", color: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300", icon: Mail },
  { key: "meeting_scheduled", label: "Meeting Set", color: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300", icon: Calendar },
  { key: "proposal_sent", label: "Proposal Sent", color: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300", icon: FileText },
  { key: "negotiating", label: "Negotiating", color: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300", icon: Handshake },
  { key: "partner", label: "Partner", color: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300", icon: CheckCircle },
  { key: "inactive", label: "Inactive", color: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400", icon: AlertCircle },
];

const CATEGORIES = [
  { key: "construction", label: "Construction & Trades" },
  { key: "public_sector", label: "Public Sector" },
  { key: "healthcare", label: "Healthcare" },
  { key: "transportation", label: "Transportation" },
  { key: "retail", label: "Retail & Services" },
];

function StageLabel({ stage }: { stage: string }) {
  const s = PIPELINE_STAGES.find(p => p.key === stage) || PIPELINE_STAGES[0];
  return <Badge className={`${s.color} border-0`}>{s.label}</Badge>;
}

function CategoryLabel({ category }: { category: string }) {
  const c = CATEGORIES.find(cat => cat.key === category);
  return <span className="text-xs text-muted-foreground">{c?.label || category}</span>;
}

function PipelineTab({ unions }: { unions: UnionOrganization[] }) {
  const { toast } = useToast();
  const [selectedUnion, setSelectedUnion] = useState<UnionOrganization | null>(null);
  const [showAddDialog, setShowAddDialog] = useState(false);

  const updateStageMutation = useMutation({
    mutationFn: async ({ id, stage }: { id: number; stage: string }) => {
      await apiRequest("PATCH", `/api/unions/${id}`, { pipelineStage: stage });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/unions"] });
      toast({ title: "Pipeline stage updated" });
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: any) => {
      await apiRequest("POST", "/api/unions", data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/unions"] });
      setShowAddDialog(false);
      toast({ title: "Union added to pipeline" });
    },
  });

  const handleAddUnion = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    createMutation.mutate({
      name: fd.get("name"),
      localNumber: fd.get("localNumber") || undefined,
      category: fd.get("category"),
      memberCount: fd.get("memberCount") ? parseInt(fd.get("memberCount") as string) : undefined,
      phone: fd.get("phone") || undefined,
      email: fd.get("email") || undefined,
      website: fd.get("website") || undefined,
      address: fd.get("address") || undefined,
      city: fd.get("city") || undefined,
      state: fd.get("state") || "CA",
      zipCode: fd.get("zipCode") || undefined,
      notes: fd.get("notes") || undefined,
      pipelineStage: "prospect",
      priorityScore: 50,
    });
  };

  const stagesWithCounts = PIPELINE_STAGES.map(s => ({
    ...s,
    unions: unions.filter(u => u.pipelineStage === s.key),
    count: unions.filter(u => u.pipelineStage === s.key).length,
  }));

  const totalMembers = unions.reduce((sum, u) => sum + (u.memberCount || 0), 0);
  const activePartners = unions.filter(u => u.pipelineStage === "partner").length;
  const inPipeline = unions.filter(u => !["partner", "inactive", "prospect"].includes(u.pipelineStage)).length;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900">
                <Building2 className="h-5 w-5 text-blue-600 dark:text-blue-300" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Total Unions</p>
                <p className="text-2xl font-bold" data-testid="text-total-unions">{unions.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-green-100 dark:bg-green-900">
                <Handshake className="h-5 w-5 text-green-600 dark:text-green-300" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Active Partners</p>
                <p className="text-2xl font-bold" data-testid="text-active-partners">{activePartners}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-amber-100 dark:bg-amber-900">
                <TrendingUp className="h-5 w-5 text-amber-600 dark:text-amber-300" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">In Pipeline</p>
                <p className="text-2xl font-bold" data-testid="text-in-pipeline">{inPipeline}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-purple-100 dark:bg-purple-900">
                <Users className="h-5 w-5 text-purple-600 dark:text-purple-300" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Total Members</p>
                <p className="text-2xl font-bold" data-testid="text-total-members">{totalMembers.toLocaleString()}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Partnership Pipeline</h3>
        <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
          <DialogTrigger asChild>
            <Button data-testid="button-add-union"><Plus className="h-4 w-4 mr-2" /> Add Union</Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Add Union Organization</DialogTitle>
              <DialogDescription>Add a new union to your outreach pipeline.</DialogDescription>
            </DialogHeader>
            <form onSubmit={handleAddUnion} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <Label htmlFor="name">Union Name</Label>
                  <Input id="name" name="name" placeholder="e.g., IBEW Local 340" required data-testid="input-union-name" />
                </div>
                <div>
                  <Label htmlFor="localNumber">Local Number</Label>
                  <Input id="localNumber" name="localNumber" placeholder="e.g., 340" data-testid="input-local-number" />
                </div>
                <div>
                  <Label htmlFor="category">Category</Label>
                  <select name="category" id="category" className="w-full rounded-md border px-3 py-2 text-sm" required data-testid="select-category">
                    {CATEGORIES.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
                  </select>
                </div>
                <div>
                  <Label htmlFor="memberCount">Est. Members</Label>
                  <Input id="memberCount" name="memberCount" type="number" placeholder="e.g., 2500" data-testid="input-member-count" />
                </div>
                <div>
                  <Label htmlFor="phone">Phone</Label>
                  <Input id="phone" name="phone" placeholder="(916) 555-0100" data-testid="input-phone" />
                </div>
                <div>
                  <Label htmlFor="email">Email</Label>
                  <Input id="email" name="email" type="email" placeholder="office@union.org" data-testid="input-email" />
                </div>
                <div>
                  <Label htmlFor="website">Website</Label>
                  <Input id="website" name="website" placeholder="union.org" data-testid="input-website" />
                </div>
                <div className="col-span-2">
                  <Label htmlFor="address">Address</Label>
                  <Input id="address" name="address" placeholder="Street address" />
                </div>
                <div>
                  <Label htmlFor="city">City</Label>
                  <Input id="city" name="city" placeholder="Sacramento" />
                </div>
                <div>
                  <Label htmlFor="state">State</Label>
                  <Input id="state" name="state" defaultValue="CA" />
                </div>
                <div>
                  <Label htmlFor="zipCode">ZIP</Label>
                  <Input id="zipCode" name="zipCode" placeholder="95834" />
                </div>
                <div className="col-span-2">
                  <Label htmlFor="notes">Notes</Label>
                  <Textarea id="notes" name="notes" placeholder="Key contacts, dental plan info, strategy notes..." rows={3} data-testid="input-notes" />
                </div>
              </div>
              <Button type="submit" className="w-full" disabled={createMutation.isPending} data-testid="button-submit-union">
                {createMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Plus className="h-4 w-4 mr-2" />}
                Add to Pipeline
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-7 gap-3">
        {stagesWithCounts.map((stage) => (
          <div key={stage.key} className="space-y-2">
            <div className="flex items-center gap-2 p-2 rounded-lg bg-muted/50">
              <stage.icon className="h-4 w-4 text-muted-foreground" />
              <span className="text-xs font-medium">{stage.label}</span>
              <Badge variant="secondary" className="ml-auto text-xs">{stage.count}</Badge>
            </div>
            <div className="space-y-2 min-h-[100px]">
              {stage.unions.map((union) => (
                <Card
                  key={union.id}
                  className="cursor-pointer border-l-4 hover:shadow-md transition-shadow"
                  style={{ borderLeftColor: union.priorityScore && union.priorityScore >= 85 ? '#f59e0b' : union.priorityScore && union.priorityScore >= 70 ? '#3b82f6' : '#94a3b8' }}
                  onClick={() => setSelectedUnion(union)}
                  data-testid={`card-union-${union.id}`}
                >
                  <CardContent className="p-3">
                    <p className="text-sm font-medium leading-tight">{union.name}</p>
                    <CategoryLabel category={union.category} />
                    {union.memberCount && (
                      <p className="text-xs text-muted-foreground mt-1">{union.memberCount.toLocaleString()} members</p>
                    )}
                    {union.priorityScore && union.priorityScore >= 85 && (
                      <div className="flex items-center gap-1 mt-1">
                        <Star className="h-3 w-3 text-amber-500" />
                        <span className="text-xs text-amber-600 dark:text-amber-400">High Priority</span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        ))}
      </div>

      {selectedUnion && (
        <Dialog open={!!selectedUnion} onOpenChange={() => setSelectedUnion(null)}>
          <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{selectedUnion.name}</DialogTitle>
              <DialogDescription>{selectedUnion.localNumber ? `Local ${selectedUnion.localNumber}` : ''} - <CategoryLabel category={selectedUnion.category} /></DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3 text-sm">
                {selectedUnion.phone && (
                  <div className="flex items-center gap-2"><Phone className="h-4 w-4 text-muted-foreground" /><span>{selectedUnion.phone}</span></div>
                )}
                {selectedUnion.email && (
                  <div className="flex items-center gap-2"><Mail className="h-4 w-4 text-muted-foreground" /><a href={`mailto:${selectedUnion.email}`} className="text-blue-600 hover:underline">{selectedUnion.email}</a></div>
                )}
                {selectedUnion.website && (
                  <div className="flex items-center gap-2"><Globe className="h-4 w-4 text-muted-foreground" /><a href={`https://${selectedUnion.website}`} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">{selectedUnion.website} <ExternalLink className="h-3 w-3 inline" /></a></div>
                )}
                {selectedUnion.address && (
                  <div className="flex items-center gap-2"><MapPin className="h-4 w-4 text-muted-foreground" /><span>{selectedUnion.address}, {selectedUnion.city} {selectedUnion.state} {selectedUnion.zipCode}</span></div>
                )}
                {selectedUnion.memberCount && (
                  <div className="flex items-center gap-2"><Users className="h-4 w-4 text-muted-foreground" /><span>{selectedUnion.memberCount.toLocaleString()} members</span></div>
                )}
              </div>
              {selectedUnion.notes && (
                <div className="p-3 bg-muted/50 rounded-lg text-sm whitespace-pre-wrap">{selectedUnion.notes}</div>
              )}
              <div>
                <Label>Move to Stage</Label>
                <div className="flex flex-wrap gap-2 mt-2">
                  {PIPELINE_STAGES.map((stage) => (
                    <Button
                      key={stage.key}
                      size="sm"
                      variant={selectedUnion.pipelineStage === stage.key ? "default" : "outline"}
                      onClick={() => {
                        updateStageMutation.mutate({ id: selectedUnion.id, stage: stage.key });
                        setSelectedUnion({ ...selectedUnion, pipelineStage: stage.key });
                      }}
                      data-testid={`button-stage-${stage.key}`}
                    >
                      <stage.icon className="h-3 w-3 mr-1" />
                      {stage.label}
                    </Button>
                  ))}
                </div>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

function ContactsTab({ unions }: { unions: UnionOrganization[] }) {
  const { toast } = useToast();
  const [selectedUnionId, setSelectedUnionId] = useState<number | null>(null);
  const [showAddContact, setShowAddContact] = useState(false);

  const { data: contacts = [], isLoading } = useQuery<UnionContact[]>({
    queryKey: ["/api/unions", selectedUnionId, "contacts"],
    enabled: !!selectedUnionId,
  });

  const createContactMutation = useMutation({
    mutationFn: async (data: any) => {
      await apiRequest("POST", "/api/unions/contacts", data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/unions", selectedUnionId, "contacts"] });
      setShowAddContact(false);
      toast({ title: "Contact added" });
    },
  });

  const handleAddContact = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    createContactMutation.mutate({
      unionId: selectedUnionId,
      firstName: fd.get("firstName"),
      lastName: fd.get("lastName"),
      title: fd.get("title") || undefined,
      email: fd.get("email") || undefined,
      phone: fd.get("phone") || undefined,
      isPrimary: fd.get("isPrimary") === "true",
      notes: fd.get("notes") || undefined,
    });
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div className="space-y-2">
        <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider">Select Union</h3>
        <div className="space-y-1">
          {unions.map((union) => (
            <button
              key={union.id}
              className={`w-full text-left p-3 rounded-lg border transition-colors ${selectedUnionId === union.id ? 'bg-primary/10 border-primary' : 'hover:bg-muted/50 border-transparent'}`}
              onClick={() => setSelectedUnionId(union.id)}
              data-testid={`button-select-union-${union.id}`}
            >
              <p className="text-sm font-medium">{union.name}</p>
              <div className="flex items-center gap-2 mt-1">
                <StageLabel stage={union.pipelineStage} />
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="md:col-span-2">
        {!selectedUnionId ? (
          <div className="flex items-center justify-center h-64 text-muted-foreground">
            <div className="text-center">
              <Users className="h-12 w-12 mx-auto mb-3 opacity-40" />
              <p>Select a union to view contacts</p>
            </div>
          </div>
        ) : isLoading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">Contacts ({contacts.length})</h3>
              <Dialog open={showAddContact} onOpenChange={setShowAddContact}>
                <DialogTrigger asChild>
                  <Button size="sm" data-testid="button-add-contact"><Plus className="h-4 w-4 mr-1" /> Add Contact</Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Add Contact</DialogTitle>
                    <DialogDescription>Add a key contact for this union.</DialogDescription>
                  </DialogHeader>
                  <form onSubmit={handleAddContact} className="space-y-4">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <Label htmlFor="firstName">First Name</Label>
                        <Input id="firstName" name="firstName" required data-testid="input-contact-first" />
                      </div>
                      <div>
                        <Label htmlFor="lastName">Last Name</Label>
                        <Input id="lastName" name="lastName" required data-testid="input-contact-last" />
                      </div>
                      <div>
                        <Label htmlFor="title">Title/Role</Label>
                        <Input id="title" name="title" placeholder="e.g., Business Manager" data-testid="input-contact-title" />
                      </div>
                      <div>
                        <Label htmlFor="email">Email</Label>
                        <Input id="email" name="email" type="email" data-testid="input-contact-email" />
                      </div>
                      <div>
                        <Label htmlFor="phone">Phone</Label>
                        <Input id="phone" name="phone" data-testid="input-contact-phone" />
                      </div>
                      <div>
                        <Label htmlFor="isPrimary">Primary Contact</Label>
                        <select name="isPrimary" className="w-full rounded-md border px-3 py-2 text-sm" data-testid="select-is-primary">
                          <option value="false">No</option>
                          <option value="true">Yes</option>
                        </select>
                      </div>
                    </div>
                    <div>
                      <Label htmlFor="notes">Notes</Label>
                      <Textarea id="notes" name="notes" rows={2} />
                    </div>
                    <Button type="submit" className="w-full" disabled={createContactMutation.isPending} data-testid="button-submit-contact">
                      {createContactMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                      Add Contact
                    </Button>
                  </form>
                </DialogContent>
              </Dialog>
            </div>

            {contacts.length === 0 ? (
              <div className="text-center p-8 text-muted-foreground border rounded-lg border-dashed">
                <p>No contacts yet. Add the Business Agent or Benefits Coordinator first.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {contacts.map((contact) => (
                  <Card key={contact.id} data-testid={`card-contact-${contact.id}`}>
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="font-medium">{contact.firstName} {contact.lastName}</p>
                            {contact.isPrimary && <Badge variant="default" className="text-xs">Primary</Badge>}
                          </div>
                          {contact.title && <p className="text-sm text-muted-foreground">{contact.title}</p>}
                        </div>
                      </div>
                      <div className="flex items-center gap-4 mt-2 text-sm">
                        {contact.email && (
                          <a href={`mailto:${contact.email}`} className="flex items-center gap-1 text-blue-600 hover:underline">
                            <Mail className="h-3 w-3" /> {contact.email}
                          </a>
                        )}
                        {contact.phone && (
                          <span className="flex items-center gap-1 text-muted-foreground">
                            <Phone className="h-3 w-3" /> {contact.phone}
                          </span>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function OutreachTab({ unions }: { unions: UnionOrganization[] }) {
  const { toast } = useToast();
  const [showAddOutreach, setShowAddOutreach] = useState(false);

  const { data: outreach = [], isLoading } = useQuery<UnionOutreach[]>({
    queryKey: ["/api/unions/outreach/all"],
  });

  const createMutation = useMutation({
    mutationFn: async (data: any) => {
      await apiRequest("POST", "/api/unions/outreach", data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/unions/outreach/all"] });
      setShowAddOutreach(false);
      toast({ title: "Outreach logged" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: any }) => {
      await apiRequest("PATCH", `/api/unions/outreach/${id}`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/unions/outreach/all"] });
      toast({ title: "Outreach updated" });
    },
  });

  const handleAdd = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    createMutation.mutate({
      unionId: parseInt(fd.get("unionId") as string),
      type: fd.get("type"),
      subject: fd.get("subject") || undefined,
      body: fd.get("body") || undefined,
      status: fd.get("status"),
      followUpDate: fd.get("followUpDate") || undefined,
    });
  };

  const statusColors: Record<string, string> = {
    draft: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    sent: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    delivered: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300",
    opened: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
    replied: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    no_response: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Outreach Tracker</h3>
          <p className="text-sm text-muted-foreground">Track all emails, calls, and visits to union contacts</p>
        </div>
        <Dialog open={showAddOutreach} onOpenChange={setShowAddOutreach}>
          <DialogTrigger asChild>
            <Button data-testid="button-add-outreach"><Plus className="h-4 w-4 mr-2" /> Log Outreach</Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Log Outreach Activity</DialogTitle>
              <DialogDescription>Record an email, call, or visit.</DialogDescription>
            </DialogHeader>
            <form onSubmit={handleAdd} className="space-y-4">
              <div>
                <Label>Union</Label>
                <select name="unionId" className="w-full rounded-md border px-3 py-2 text-sm" required data-testid="select-outreach-union">
                  <option value="">Select union...</option>
                  {unions.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Type</Label>
                  <select name="type" className="w-full rounded-md border px-3 py-2 text-sm" required data-testid="select-outreach-type">
                    <option value="email">Email</option>
                    <option value="phone">Phone Call</option>
                    <option value="in_person">In-Person Visit</option>
                    <option value="mail">Physical Mail</option>
                  </select>
                </div>
                <div>
                  <Label>Status</Label>
                  <select name="status" className="w-full rounded-md border px-3 py-2 text-sm" required data-testid="select-outreach-status">
                    <option value="draft">Draft</option>
                    <option value="sent">Sent</option>
                    <option value="delivered">Delivered</option>
                    <option value="replied">Replied</option>
                    <option value="no_response">No Response</option>
                  </select>
                </div>
              </div>
              <div>
                <Label>Subject</Label>
                <Input name="subject" placeholder="e.g., Free Oral Health Screening Offer" data-testid="input-outreach-subject" />
              </div>
              <div>
                <Label>Message / Notes</Label>
                <Textarea name="body" rows={4} placeholder="Email content or call notes..." data-testid="input-outreach-body" />
              </div>
              <div>
                <Label>Follow-up Date</Label>
                <Input name="followUpDate" type="date" data-testid="input-followup-date" />
              </div>
              <Button type="submit" className="w-full" disabled={createMutation.isPending} data-testid="button-submit-outreach">
                {createMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />}
                Log Outreach
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-32"><Loader2 className="h-8 w-8 animate-spin" /></div>
      ) : outreach.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="p-8 text-center text-muted-foreground">
            <Send className="h-12 w-12 mx-auto mb-3 opacity-40" />
            <p className="font-medium">No outreach logged yet</p>
            <p className="text-sm">Start by sending the initial email to IBEW Local 340 or UFCW 8</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {outreach.map((item) => {
            const union = unions.find(u => u.id === item.unionId);
            return (
              <Card key={item.id} data-testid={`card-outreach-${item.id}`}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium">{item.subject || 'Outreach'}</p>
                        <Badge className={`${statusColors[item.status] || ''} border-0 text-xs`}>{item.status.replace('_', ' ')}</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">{union?.name || 'Unknown'} - {item.type}</p>
                    </div>
                    <div className="flex gap-2">
                      {item.status === "sent" && (
                        <Button size="sm" variant="outline" onClick={() => updateMutation.mutate({ id: item.id, data: { status: "replied" } })} data-testid={`button-mark-replied-${item.id}`}>
                          Mark Replied
                        </Button>
                      )}
                      {item.status === "sent" && (
                        <Button size="sm" variant="ghost" onClick={() => updateMutation.mutate({ id: item.id, data: { status: "no_response" } })}>
                          No Response
                        </Button>
                      )}
                    </div>
                  </div>
                  {item.body && <p className="text-sm mt-2 text-muted-foreground line-clamp-2">{item.body}</p>}
                  <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                    <span>Created: {new Date(item.createdAt).toLocaleDateString()}</span>
                    {item.followUpDate && (
                      <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> Follow-up: {item.followUpDate}</span>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function EventsTab({ unions }: { unions: UnionOrganization[] }) {
  const { toast } = useToast();
  const [showAddEvent, setShowAddEvent] = useState(false);

  const { data: events = [], isLoading } = useQuery<UnionEvent[]>({
    queryKey: ["/api/unions/events/all"],
  });

  const createMutation = useMutation({
    mutationFn: async (data: any) => {
      await apiRequest("POST", "/api/unions/events", data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/unions/events/all"] });
      setShowAddEvent(false);
      toast({ title: "Event created" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: any }) => {
      await apiRequest("PATCH", `/api/unions/events/${id}`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/unions/events/all"] });
      toast({ title: "Event updated" });
    },
  });

  const handleAdd = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    createMutation.mutate({
      unionId: fd.get("unionId") ? parseInt(fd.get("unionId") as string) : undefined,
      title: fd.get("title"),
      type: fd.get("type"),
      date: fd.get("date"),
      time: fd.get("time") || undefined,
      location: fd.get("location") || undefined,
      description: fd.get("description") || undefined,
      status: "planned",
    });
  };

  const eventTypeIcons: Record<string, string> = {
    health_fair: "Health Fair",
    lunch_learn: "Lunch & Learn",
    screening: "Oral Screening",
    open_enrollment: "Open Enrollment",
    meeting: "Meeting",
  };

  const statusColors: Record<string, string> = {
    planned: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    confirmed: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    completed: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    cancelled: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Events & Screenings</h3>
          <p className="text-sm text-muted-foreground">Health fairs, lunch-and-learns, and on-site screenings</p>
        </div>
        <Dialog open={showAddEvent} onOpenChange={setShowAddEvent}>
          <DialogTrigger asChild>
            <Button data-testid="button-add-event"><Plus className="h-4 w-4 mr-2" /> Schedule Event</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Schedule Event</DialogTitle>
              <DialogDescription>Plan a health fair, screening, or meeting.</DialogDescription>
            </DialogHeader>
            <form onSubmit={handleAdd} className="space-y-4">
              <div>
                <Label>Event Title</Label>
                <Input name="title" placeholder="e.g., Oral Health Screening Day" required data-testid="input-event-title" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Type</Label>
                  <select name="type" className="w-full rounded-md border px-3 py-2 text-sm" required data-testid="select-event-type">
                    <option value="screening">Oral Screening</option>
                    <option value="health_fair">Health Fair</option>
                    <option value="lunch_learn">Lunch & Learn</option>
                    <option value="open_enrollment">Open Enrollment</option>
                    <option value="meeting">Meeting</option>
                  </select>
                </div>
                <div>
                  <Label>Union (Optional)</Label>
                  <select name="unionId" className="w-full rounded-md border px-3 py-2 text-sm" data-testid="select-event-union">
                    <option value="">Multi-union / General</option>
                    {unions.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Date</Label>
                  <Input name="date" type="date" required data-testid="input-event-date" />
                </div>
                <div>
                  <Label>Time</Label>
                  <Input name="time" placeholder="10:00 AM - 2:00 PM" data-testid="input-event-time" />
                </div>
              </div>
              <div>
                <Label>Location</Label>
                <Input name="location" placeholder="Union Hall / Job Site" data-testid="input-event-location" />
              </div>
              <div>
                <Label>Description</Label>
                <Textarea name="description" rows={3} placeholder="Event details, what to bring..." data-testid="input-event-description" />
              </div>
              <Button type="submit" className="w-full" disabled={createMutation.isPending} data-testid="button-submit-event">
                {createMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Calendar className="h-4 w-4 mr-2" />}
                Schedule Event
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-32"><Loader2 className="h-8 w-8 animate-spin" /></div>
      ) : events.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="p-8 text-center text-muted-foreground">
            <Calendar className="h-12 w-12 mx-auto mb-3 opacity-40" />
            <p className="font-medium">No events scheduled</p>
            <p className="text-sm">Schedule your first oral health screening at a union hall</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {events.map((event) => {
            const union = unions.find(u => u.id === event.unionId);
            return (
              <Card key={event.id} data-testid={`card-event-${event.id}`}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-medium">{event.title}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge className={`${statusColors[event.status] || ''} border-0 text-xs`}>{event.status}</Badge>
                        <span className="text-xs text-muted-foreground">{eventTypeIcons[event.type] || event.type}</span>
                      </div>
                    </div>
                    {event.status === "planned" && (
                      <Button size="sm" variant="outline" onClick={() => updateMutation.mutate({ id: event.id, data: { status: "confirmed" } })} data-testid={`button-confirm-event-${event.id}`}>
                        Confirm
                      </Button>
                    )}
                    {event.status === "confirmed" && (
                      <Button size="sm" variant="outline" onClick={() => updateMutation.mutate({ id: event.id, data: { status: "completed" } })}>
                        Complete
                      </Button>
                    )}
                  </div>
                  <div className="mt-3 space-y-1 text-sm text-muted-foreground">
                    <div className="flex items-center gap-2"><Calendar className="h-3 w-3" /> {event.date} {event.time && `at ${event.time}`}</div>
                    {event.location && <div className="flex items-center gap-2"><MapPin className="h-3 w-3" /> {event.location}</div>}
                    {union && <div className="flex items-center gap-2"><Building2 className="h-3 w-3" /> {union.name}</div>}
                  </div>
                  {event.status === "completed" && (
                    <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                      <div className="p-2 bg-muted/50 rounded">
                        <p className="text-lg font-bold">{event.attendeeCount || '—'}</p>
                        <p className="text-xs text-muted-foreground">Attendees</p>
                      </div>
                      <div className="p-2 bg-muted/50 rounded">
                        <p className="text-lg font-bold">{event.screeningsPerformed || '—'}</p>
                        <p className="text-xs text-muted-foreground">Screenings</p>
                      </div>
                      <div className="p-2 bg-muted/50 rounded">
                        <p className="text-lg font-bold">{event.leadsGenerated || '—'}</p>
                        <p className="text-xs text-muted-foreground">Leads</p>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function AgreementsTab({ unions }: { unions: UnionOrganization[] }) {
  const { toast } = useToast();
  const [showAddAgreement, setShowAddAgreement] = useState(false);

  const { data: agreements = [], isLoading } = useQuery<UnionAgreement[]>({
    queryKey: ["/api/unions/agreements/all"],
  });

  const createMutation = useMutation({
    mutationFn: async (data: any) => {
      await apiRequest("POST", "/api/unions/agreements", data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/unions/agreements/all"] });
      setShowAddAgreement(false);
      toast({ title: "Agreement created" });
    },
  });

  const handleAdd = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    createMutation.mutate({
      unionId: parseInt(fd.get("unionId") as string),
      type: fd.get("type"),
      title: fd.get("title"),
      status: "draft",
      startDate: fd.get("startDate") || undefined,
      endDate: fd.get("endDate") || undefined,
      discountPercentage: fd.get("discountPercentage") || undefined,
      terms: fd.get("terms") || undefined,
    });
  };

  const typeLabels: Record<string, string> = {
    preferred_provider: "Preferred Provider",
    discount_schedule: "Discount Schedule",
    mou: "MOU (Memorandum of Understanding)",
    sponsorship: "Sponsorship",
  };

  const statusColors: Record<string, string> = {
    draft: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    pending_review: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
    active: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    expired: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    terminated: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Partnership Agreements</h3>
          <p className="text-sm text-muted-foreground">MOUs, preferred provider arrangements, and discount schedules</p>
        </div>
        <Dialog open={showAddAgreement} onOpenChange={setShowAddAgreement}>
          <DialogTrigger asChild>
            <Button data-testid="button-add-agreement"><Plus className="h-4 w-4 mr-2" /> New Agreement</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Agreement</DialogTitle>
              <DialogDescription>Draft a new partnership agreement.</DialogDescription>
            </DialogHeader>
            <form onSubmit={handleAdd} className="space-y-4">
              <div>
                <Label>Union</Label>
                <select name="unionId" className="w-full rounded-md border px-3 py-2 text-sm" required data-testid="select-agreement-union">
                  <option value="">Select union...</option>
                  {unions.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
                </select>
              </div>
              <div>
                <Label>Title</Label>
                <Input name="title" placeholder="e.g., IBEW 340 Preferred Provider Agreement" required data-testid="input-agreement-title" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Type</Label>
                  <select name="type" className="w-full rounded-md border px-3 py-2 text-sm" required data-testid="select-agreement-type">
                    <option value="preferred_provider">Preferred Provider</option>
                    <option value="discount_schedule">Discount Schedule</option>
                    <option value="mou">MOU</option>
                    <option value="sponsorship">Sponsorship</option>
                  </select>
                </div>
                <div>
                  <Label>Discount %</Label>
                  <Input name="discountPercentage" type="number" placeholder="e.g., 15" data-testid="input-discount" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Start Date</Label>
                  <Input name="startDate" type="date" data-testid="input-start-date" />
                </div>
                <div>
                  <Label>End Date</Label>
                  <Input name="endDate" type="date" data-testid="input-end-date" />
                </div>
              </div>
              <div>
                <Label>Terms & Conditions</Label>
                <Textarea name="terms" rows={4} placeholder="Outline the key terms: pricing, scheduling priority, services covered..." data-testid="input-terms" />
              </div>
              <Button type="submit" className="w-full" disabled={createMutation.isPending} data-testid="button-submit-agreement">
                {createMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <FileText className="h-4 w-4 mr-2" />}
                Create Agreement
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-32"><Loader2 className="h-8 w-8 animate-spin" /></div>
      ) : agreements.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="p-8 text-center text-muted-foreground">
            <Handshake className="h-12 w-12 mx-auto mb-3 opacity-40" />
            <p className="font-medium">No agreements yet</p>
            <p className="text-sm">Create your first preferred provider agreement once a union partnership is confirmed</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {agreements.map((agreement) => {
            const union = unions.find(u => u.id === agreement.unionId);
            return (
              <Card key={agreement.id} data-testid={`card-agreement-${agreement.id}`}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-medium">{agreement.title}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge className={`${statusColors[agreement.status] || ''} border-0 text-xs`}>{agreement.status.replace('_', ' ')}</Badge>
                        <span className="text-xs text-muted-foreground">{typeLabels[agreement.type] || agreement.type}</span>
                        {union && <span className="text-xs text-muted-foreground">- {union.name}</span>}
                      </div>
                    </div>
                    {agreement.discountPercentage && (
                      <Badge variant="outline" className="text-sm">{agreement.discountPercentage}% discount</Badge>
                    )}
                  </div>
                  {agreement.terms && <p className="text-sm mt-2 text-muted-foreground line-clamp-2">{agreement.terms}</p>}
                  <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                    {agreement.startDate && <span>Start: {agreement.startDate}</span>}
                    {agreement.endDate && <span>End: {agreement.endDate}</span>}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function AnalyticsTab({ unions }: { unions: UnionOrganization[] }) {
  const byCategory = CATEGORIES.map(cat => ({
    ...cat,
    count: unions.filter(u => u.category === cat.key).length,
    members: unions.filter(u => u.category === cat.key).reduce((sum, u) => sum + (u.memberCount || 0), 0),
  }));

  const byStage = PIPELINE_STAGES.map(s => ({
    ...s,
    count: unions.filter(u => u.pipelineStage === s.key).length,
  }));

  const totalMembers = unions.reduce((sum, u) => sum + (u.memberCount || 0), 0);
  const activePartners = unions.filter(u => u.pipelineStage === "partner").length;
  const conversionRate = unions.length > 0 ? Math.round((activePartners / unions.length) * 100) : 0;
  const avgPriority = unions.length > 0 ? Math.round(unions.reduce((sum, u) => sum + (u.priorityScore || 50), 0) / unions.length) : 0;

  const topTargets = [...unions]
    .filter(u => u.pipelineStage !== "partner" && u.pipelineStage !== "inactive")
    .sort((a, b) => (b.priorityScore || 0) - (a.priorityScore || 0))
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-primary">{totalMembers.toLocaleString()}</p>
            <p className="text-sm text-muted-foreground">Total Reachable Members</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-green-600">{conversionRate}%</p>
            <p className="text-sm text-muted-foreground">Conversion Rate</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-amber-600">{avgPriority}</p>
            <p className="text-sm text-muted-foreground">Avg Priority Score</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-purple-600">{unions.length}</p>
            <p className="text-sm text-muted-foreground">Unions in Database</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Pipeline Distribution</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {byStage.filter(s => s.count > 0).map((stage) => (
              <div key={stage.key} className="flex items-center gap-3">
                <stage.icon className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm w-28">{stage.label}</span>
                <Progress value={(stage.count / Math.max(unions.length, 1)) * 100} className="flex-1" />
                <span className="text-sm font-medium w-6 text-right">{stage.count}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">By Category</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {byCategory.filter(c => c.count > 0).map((cat) => (
              <div key={cat.key} className="flex items-center justify-between p-2 bg-muted/30 rounded">
                <div>
                  <p className="text-sm font-medium">{cat.label}</p>
                  <p className="text-xs text-muted-foreground">{cat.count} union{cat.count !== 1 ? 's' : ''}</p>
                </div>
                <p className="text-sm font-medium">{cat.members.toLocaleString()} members</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Top Outreach Targets</CardTitle>
          <CardDescription>Highest priority unions not yet partnered</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {topTargets.map((union, i) => (
              <div key={union.id} className="flex items-center gap-4 p-3 bg-muted/30 rounded-lg" data-testid={`row-top-target-${union.id}`}>
                <span className="text-lg font-bold text-muted-foreground w-6">#{i + 1}</span>
                <div className="flex-1">
                  <p className="font-medium">{union.name}</p>
                  <div className="flex items-center gap-2">
                    <CategoryLabel category={union.category} />
                    <span className="text-xs text-muted-foreground">- {union.memberCount?.toLocaleString() || '?'} members</span>
                  </div>
                </div>
                <StageLabel stage={union.pipelineStage} />
                <div className="text-right">
                  <p className="text-lg font-bold text-amber-600">{union.priorityScore}</p>
                  <p className="text-xs text-muted-foreground">Priority</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">5-Phase Implementation Roadmap</CardTitle>
          <CardDescription>Structured approach to union engagement</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[
              { phase: 1, title: "Identify & Prioritize", desc: "Target unions with strongest presence in Roseville/Sacramento corridor. Focus on construction trades, public sector, and healthcare workers.", status: "active" },
              { phase: 2, title: "Build Value Proposition", desc: "Structure pitch around Access (one-roof care), Affordability (union-specific pricing, $14,995 full arch), and Accountability (dedicated contact).", status: "active" },
              { phase: 3, title: "Engagement Strategy", desc: "Contact Business Agents, offer free lunch-and-learns / oral screenings, negotiate preferred provider agreements, create co-branded materials.", status: "upcoming" },
              { phase: 4, title: "Retention & Expansion", desc: "Quarterly check-ins with utilization data, member testimonials, referral programs, annual benefits education presentations.", status: "upcoming" },
              { phase: 5, title: "Scale It", desc: "Use 2-3 proven partnerships as case studies. Approach Sacramento Central Labor Council to access 98 affiliated unions (~200K members).", status: "future" },
            ].map((phase) => (
              <div key={phase.phase} className="flex gap-4">
                <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold ${
                  phase.status === "active" ? "bg-primary text-primary-foreground" : phase.status === "upcoming" ? "bg-muted text-muted-foreground" : "bg-muted/50 text-muted-foreground/50"
                }`}>
                  {phase.phase}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">{phase.title}</p>
                    {phase.status === "active" && <Badge className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 border-0 text-xs">Active</Badge>}
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">{phase.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function UnionFlowPage() {
  const { toast } = useToast();

  const { data: unions = [], isLoading } = useQuery<UnionOrganization[]>({
    queryKey: ["/api/unions"],
  });

  const seedMutation = useMutation({
    mutationFn: async () => {
      await apiRequest("POST", "/api/unions/seed", {});
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/unions"] });
      toast({ title: "Sacramento/Roseville unions loaded!", description: "8 local unions with contacts pre-loaded." });
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight" data-testid="text-page-title">Union Partnership Flow</h1>
          <p className="text-muted-foreground">
            Build partnerships with local unions to drive patient acquisition
          </p>
        </div>
        {unions.length === 0 && (
          <Button onClick={() => seedMutation.mutate()} disabled={seedMutation.isPending} variant="default" data-testid="button-seed-unions">
            {seedMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Building2 className="h-4 w-4 mr-2" />}
            Load Sacramento/Roseville Unions
          </Button>
        )}
      </div>

      <Tabs defaultValue="pipeline">
        <TabsList className="grid w-full grid-cols-6" data-testid="tabs-union-flow">
          <TabsTrigger value="pipeline" data-testid="tab-pipeline">Pipeline</TabsTrigger>
          <TabsTrigger value="contacts" data-testid="tab-contacts">Contacts</TabsTrigger>
          <TabsTrigger value="outreach" data-testid="tab-outreach">Outreach</TabsTrigger>
          <TabsTrigger value="events" data-testid="tab-events">Events</TabsTrigger>
          <TabsTrigger value="agreements" data-testid="tab-agreements">Agreements</TabsTrigger>
          <TabsTrigger value="analytics" data-testid="tab-analytics">Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="pipeline">
          <PipelineTab unions={unions} />
        </TabsContent>
        <TabsContent value="contacts">
          <ContactsTab unions={unions} />
        </TabsContent>
        <TabsContent value="outreach">
          <OutreachTab unions={unions} />
        </TabsContent>
        <TabsContent value="events">
          <EventsTab unions={unions} />
        </TabsContent>
        <TabsContent value="agreements">
          <AgreementsTab unions={unions} />
        </TabsContent>
        <TabsContent value="analytics">
          <AnalyticsTab unions={unions} />
        </TabsContent>
      </Tabs>
    </div>
  );
}