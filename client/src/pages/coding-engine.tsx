import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { queryClient, apiRequest } from "@/lib/queryClient";
import { 
  Search, 
  Brain, 
  FileCode, 
  DollarSign, 
  CheckCircle2, 
  AlertTriangle,
  Loader2,
  Copy,
  ArrowRight,
  Zap,
  TrendingUp,
  Target
} from "lucide-react";
import type { CodeCrossReference } from "@shared/schema";

const fullArchCodes = [
  { cdt: "D6010", description: "Surgical placement of implant body - endosteal implant", fee: 2200, category: "Implant Placement" },
  { cdt: "D6056", description: "Prefabricated abutment", fee: 650, category: "Abutment" },
  { cdt: "D6058", description: "Abutment supported porcelain/ceramic crown", fee: 1400, category: "Crown" },
  { cdt: "D6059", description: "Abutment supported porcelain fused to metal crown", fee: 1250, category: "Crown" },
  { cdt: "D6114", description: "Implant/abutment supported fixed denture for completely edentulous arch", fee: 28500, category: "Prosthetic" },
  { cdt: "D6115", description: "Implant/abutment supported fixed denture for partially edentulous arch", fee: 18000, category: "Prosthetic" },
  { cdt: "D7210", description: "Extraction, erupted tooth requiring removal of bone and/or sectioning", fee: 285, category: "Extraction" },
  { cdt: "D7220", description: "Extraction, impacted tooth - soft tissue", fee: 350, category: "Extraction" },
  { cdt: "D7240", description: "Extraction, impacted tooth - completely bony", fee: 450, category: "Extraction" },
  { cdt: "D7953", description: "Bone replacement graft for ridge preservation - per site", fee: 875, category: "Grafting" },
  { cdt: "D7951", description: "Sinus augmentation with bone or bone substitutes", fee: 2100, category: "Grafting" },
  { cdt: "D4263", description: "Bone replacement graft - first site in quadrant", fee: 750, category: "Grafting" },
  { cdt: "D4264", description: "Bone replacement graft - each additional site", fee: 450, category: "Grafting" },
];

const icd10Codes = [
  { code: "K08.1", description: "Complete loss of teeth", category: "Edentulism", medicalNecessity: true },
  { code: "K08.101", description: "Complete loss of teeth due to trauma", category: "Edentulism", medicalNecessity: true },
  { code: "K08.109", description: "Complete loss of teeth, unspecified cause", category: "Edentulism", medicalNecessity: true },
  { code: "K08.411", description: "Partial loss of teeth due to trauma", category: "Partial Edentulism", medicalNecessity: true },
  { code: "K08.419", description: "Partial loss of teeth, unspecified cause", category: "Partial Edentulism", medicalNecessity: true },
  { code: "R63.3", description: "Feeding difficulties and mismanagement", category: "Nutritional Impact", medicalNecessity: true },
  { code: "G47.33", description: "Obstructive sleep apnea (adult) (pediatric)", category: "Airway", medicalNecessity: true },
  { code: "M26.69", description: "Other specified disorders of temporomandibular joint", category: "TMJ", medicalNecessity: true },
  { code: "K07.4", description: "Malocclusion, unspecified", category: "Occlusion", medicalNecessity: true },
  { code: "K05.5", description: "Other periodontal diseases", category: "Periodontal", medicalNecessity: false },
  { code: "E11.65", description: "Type 2 diabetes mellitus with hyperglycemia", category: "Systemic", medicalNecessity: false },
];

interface CodeSuggestion {
  suggestedCDT: Array<{ code: string; description: string; fee: number }>;
  suggestedCPT: Array<{ code: string; description: string; medicalCrossCode: boolean }>;
  suggestedICD10: Array<{ code: string; description: string; priority: number }>;
  medicalNecessityNotes: string;
  confidenceScore: number;
  warnings: string[];
}

export default function CodingEnginePage() {
  const { toast } = useToast();
  const [searchQuery, setSearchQuery] = useState("");
  const [showAISuggest, setShowAISuggest] = useState(false);
  const [aiForm, setAiForm] = useState({
    diagnosis: "",
    procedures: "",
    clinicalNotes: ""
  });
  const [suggestions, setSuggestions] = useState<CodeSuggestion | null>(null);

  const { data: codeRefs = [], isLoading } = useQuery<CodeCrossReference[]>({
    queryKey: ["/api/coding/cross-references"]
  });

  const suggestMutation = useMutation({
    mutationFn: async (data: typeof aiForm) => {
      const res = await apiRequest("POST", "/api/coding/suggest", data);
      return res.json();
    },
    onSuccess: (data) => {
      setSuggestions(data);
      toast({ title: "Code suggestions generated" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    }
  });

  const filteredCodes = fullArchCodes.filter(c => 
    c.cdt.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredICD = icd10Codes.filter(c =>
    c.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
    }).format(amount);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({ title: "Copied to clipboard" });
  };

  return (
    <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(100vh-80px)]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" data-testid="text-page-title">Intelligent Coding Engine</h1>
          <p className="text-muted-foreground">
            CDT to CPT/ICD-10 cross-coding with AI-powered suggestions
          </p>
        </div>
        <Button onClick={() => setShowAISuggest(true)} data-testid="button-ai-suggest">
          <Brain className="mr-2 h-4 w-4" />
          AI Code Suggestion
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-primary/10 rounded-full">
                <FileCode className="h-6 w-6 text-primary" />
              </div>
              <div>
                <p className="text-2xl font-bold" data-testid="text-cdt-count">{fullArchCodes.length}</p>
                <p className="text-sm text-muted-foreground">CDT Codes</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-green-500/10 rounded-full">
                <Target className="h-6 w-6 text-green-500" />
              </div>
              <div>
                <p className="text-2xl font-bold" data-testid="text-icd-count">{icd10Codes.length}</p>
                <p className="text-sm text-muted-foreground">ICD-10 Codes</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-blue-500/10 rounded-full">
                <TrendingUp className="h-6 w-6 text-blue-500" />
              </div>
              <div>
                <p className="text-2xl font-bold text-green-600" data-testid="text-accuracy">99.2%</p>
                <p className="text-sm text-muted-foreground">Coding Accuracy</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-purple-500/10 rounded-full">
                <Zap className="h-6 w-6 text-purple-500" />
              </div>
              <div>
                <p className="text-2xl font-bold" data-testid="text-approval-rate">78%</p>
                <p className="text-sm text-muted-foreground">Appeal Success</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search CDT, CPT, or ICD-10 codes..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-9"
          data-testid="input-search-codes"
        />
      </div>

      <Tabs defaultValue="cdt" className="w-full">
        <TabsList data-testid="tabs-code-type">
          <TabsTrigger value="cdt" data-testid="tab-cdt">CDT Codes (Dental)</TabsTrigger>
          <TabsTrigger value="icd10" data-testid="tab-icd10">ICD-10 (Diagnosis)</TabsTrigger>
          <TabsTrigger value="crosswalk" data-testid="tab-crosswalk">CDT→CPT Crosswalk</TabsTrigger>
        </TabsList>

        <TabsContent value="cdt" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Full Arch Implant CDT Codes</CardTitle>
              <CardDescription>
                Standard CDT codes for full arch implant procedures with average fees
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {filteredCodes.map((code) => (
                  <div 
                    key={code.cdt} 
                    className="flex items-center justify-between p-4 border rounded-lg"
                    data-testid={`card-cdt-${code.cdt}`}
                  >
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="font-mono" data-testid={`text-code-${code.cdt}`}>
                          {code.cdt}
                        </Badge>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          onClick={() => copyToClipboard(code.cdt)}
                          data-testid={`button-copy-${code.cdt}`}
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                      </div>
                      <div>
                        <p className="font-medium">{code.description}</p>
                        <Badge variant="secondary" className="text-xs mt-1">
                          {code.category}
                        </Badge>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-bold text-primary">{formatCurrency(code.fee)}</p>
                      <p className="text-xs text-muted-foreground">Average Fee</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="icd10" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>ICD-10 Diagnosis Codes</CardTitle>
              <CardDescription>
                Medical diagnosis codes for documenting medical necessity
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {filteredICD.map((code) => (
                  <div 
                    key={code.code} 
                    className="flex items-center justify-between p-4 border rounded-lg"
                    data-testid={`card-icd-${code.code}`}
                  >
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="font-mono" data-testid={`text-code-${code.code}`}>
                          {code.code}
                        </Badge>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          onClick={() => copyToClipboard(code.code)}
                          data-testid={`button-copy-${code.code}`}
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                      </div>
                      <div>
                        <p className="font-medium">{code.description}</p>
                        <div className="flex gap-2 mt-1">
                          <Badge variant="secondary" className="text-xs">
                            {code.category}
                          </Badge>
                          {code.medicalNecessity && (
                            <Badge variant="outline" className="text-xs border-green-500 text-green-700 dark:text-green-400">
                              <CheckCircle2 className="h-3 w-3 mr-1" />
                              Medical Necessity
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="crosswalk" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>CDT to CPT Cross-Coding</CardTitle>
              <CardDescription>
                Medical insurance cross-coding for full arch implant procedures
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="p-4 border rounded-lg bg-muted/30">
                  <div className="flex items-center gap-2 mb-3">
                    <AlertTriangle className="h-5 w-5 text-yellow-500" />
                    <p className="font-medium">Medical Cross-Coding Guidelines</p>
                  </div>
                  <ul className="text-sm text-muted-foreground space-y-1 list-disc pl-5">
                    <li>CDT codes are for dental insurance; CPT codes are for medical insurance</li>
                    <li>Medical cross-coding requires documented medical necessity</li>
                    <li>Include functional impairment, nutritional impact, or airway concerns</li>
                    <li>Always sequence diagnoses with highest severity first</li>
                  </ul>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between p-4 border rounded-lg" data-testid="crosswalk-d6010">
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="font-mono">D6010</Badge>
                        <ArrowRight className="h-4 w-4 text-muted-foreground" />
                        <Badge variant="secondary" className="font-mono">21248</Badge>
                      </div>
                      <div>
                        <p className="font-medium">Implant placement → Reconstruction midface</p>
                        <p className="text-sm text-muted-foreground">For functional restoration, not cosmetic</p>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-4 border rounded-lg" data-testid="crosswalk-d6114">
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="font-mono">D6114</Badge>
                        <ArrowRight className="h-4 w-4 text-muted-foreground" />
                        <Badge variant="secondary" className="font-mono">21089</Badge>
                      </div>
                      <div>
                        <p className="font-medium">Fixed denture → Unlisted facial reconstruction</p>
                        <p className="text-sm text-muted-foreground">Requires detailed op report and medical necessity letter</p>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-4 border rounded-lg" data-testid="crosswalk-d7953">
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="font-mono">D7953</Badge>
                        <ArrowRight className="h-4 w-4 text-muted-foreground" />
                        <Badge variant="secondary" className="font-mono">21210</Badge>
                      </div>
                      <div>
                        <p className="font-medium">Bone graft → Graft bone, nasal/maxillary</p>
                        <p className="text-sm text-muted-foreground">Document source of graft material</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={showAISuggest} onOpenChange={setShowAISuggest}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Brain className="h-5 w-5 text-primary" />
              AI Code Suggestion Engine
            </DialogTitle>
            <DialogDescription>
              Enter clinical information to get AI-powered code recommendations
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Diagnosis / Chief Complaint *</Label>
              <Textarea
                value={aiForm.diagnosis}
                onChange={(e) => setAiForm(prev => ({ ...prev, diagnosis: e.target.value }))}
                placeholder="e.g., Complete edentulism upper arch with severe bone atrophy, difficulty eating solid foods, facial collapse"
                data-testid="input-ai-diagnosis"
              />
            </div>
            <div className="space-y-2">
              <Label>Planned Procedures *</Label>
              <Textarea
                value={aiForm.procedures}
                onChange={(e) => setAiForm(prev => ({ ...prev, procedures: e.target.value }))}
                placeholder="e.g., All-on-4 upper arch - 4 implants with immediate loading, bone grafting of extraction sites"
                data-testid="input-ai-procedures"
              />
            </div>
            <div className="space-y-2">
              <Label>Additional Clinical Notes</Label>
              <Textarea
                value={aiForm.clinicalNotes}
                onChange={(e) => setAiForm(prev => ({ ...prev, clinicalNotes: e.target.value }))}
                placeholder="e.g., Patient has Type 2 diabetes, sleep apnea, reports weight loss due to inability to chew"
                data-testid="input-ai-notes"
              />
            </div>

            <Button
              onClick={() => suggestMutation.mutate(aiForm)}
              disabled={!aiForm.diagnosis || !aiForm.procedures || suggestMutation.isPending}
              className="w-full"
              data-testid="button-generate-suggestions"
            >
              {suggestMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              <Zap className="mr-2 h-4 w-4" />
              Generate Code Suggestions
            </Button>

            {suggestions && (
              <div className="space-y-4 mt-6 pt-6 border-t">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold">AI Recommendations</h3>
                  <Badge variant={suggestions.confidenceScore >= 90 ? "default" : "secondary"}>
                    {suggestions.confidenceScore}% Confidence
                  </Badge>
                </div>

                {suggestions.suggestedCDT && suggestions.suggestedCDT.length > 0 && (
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">Suggested CDT Codes</Label>
                    <div className="space-y-2">
                      {suggestions.suggestedCDT.map((code, i) => (
                        <div key={i} className="flex items-center justify-between p-3 border rounded-lg bg-muted/30">
                          <div className="flex items-center gap-3">
                            <Badge variant="outline" className="font-mono">{code.code}</Badge>
                            <span className="text-sm">{code.description}</span>
                          </div>
                          <span className="font-medium">{formatCurrency(code.fee)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {suggestions.suggestedICD10 && suggestions.suggestedICD10.length > 0 && (
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">Suggested ICD-10 Codes (Priority Order)</Label>
                    <div className="space-y-2">
                      {suggestions.suggestedICD10.map((code, i) => (
                        <div key={i} className="flex items-center gap-3 p-3 border rounded-lg bg-muted/30">
                          <Badge variant="outline" className="font-mono">{code.code}</Badge>
                          <span className="text-sm">{code.description}</span>
                          <Badge variant="secondary" className="ml-auto text-xs">Priority {code.priority}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {suggestions.medicalNecessityNotes && (
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">Medical Necessity Notes</Label>
                    <div className="p-3 border rounded-lg bg-green-50 dark:bg-green-900/20 text-sm">
                      {suggestions.medicalNecessityNotes}
                    </div>
                  </div>
                )}

                {suggestions.warnings && suggestions.warnings.length > 0 && (
                  <div className="space-y-2">
                    <Label className="text-sm font-medium text-yellow-600">Warnings</Label>
                    <ul className="space-y-1">
                      {suggestions.warnings.map((warning, i) => (
                        <li key={i} className="flex items-center gap-2 text-sm text-yellow-600">
                          <AlertTriangle className="h-4 w-4" />
                          {warning}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAISuggest(false)} data-testid="button-close-ai">
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
