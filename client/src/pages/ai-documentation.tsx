import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { 
  FileText, 
  Stethoscope, 
  ClipboardList,
  FileCheck,
  Loader2,
  Copy,
  Download,
  Sparkles,
  User,
  Calendar,
  Building2
} from "lucide-react";

interface Patient {
  id: number;
  firstName: string;
  lastName: string;
  dateOfBirth: string;
}

interface TreatmentPlan {
  id: number;
  patientId: number;
  planName: string;
  status: string;
}

interface GeneratedDocument {
  id: number;
  patientId: number;
  documentType: string;
  title: string;
  content: string;
  createdAt: string;
}

const documentTypes = [
  { 
    id: "medical-necessity", 
    label: "Medical Necessity Letter", 
    icon: FileText,
    description: "Insurance-ready letter justifying medical need for treatment"
  },
  { 
    id: "operative-report", 
    label: "Operative Report", 
    icon: Stethoscope,
    description: "Complete surgical documentation with implant details"
  },
  { 
    id: "progress-note", 
    label: "Progress Note", 
    icon: ClipboardList,
    description: "Follow-up visit documentation with outcomes"
  },
  { 
    id: "history-physical", 
    label: "History & Physical", 
    icon: FileCheck,
    description: "Comprehensive H&P from patient intake data"
  },
  { 
    id: "peer-to-peer", 
    label: "Peer-to-Peer Prep", 
    icon: Building2,
    description: "Talking points for insurance clinical reviews"
  }
];

export default function AIDocumentationPage() {
  const { toast } = useToast();
  const [selectedPatient, setSelectedPatient] = useState<string>("");
  const [selectedDocType, setSelectedDocType] = useState<string>("medical-necessity");
  const [additionalContext, setAdditionalContext] = useState("");
  const [generatedContent, setGeneratedContent] = useState("");

  const { data: patients, isLoading: patientsLoading } = useQuery<Patient[]>({
    queryKey: ["/api/patients"]
  });

  const { data: treatmentPlans } = useQuery<TreatmentPlan[]>({
    queryKey: ["/api/treatment-plans"],
    enabled: !!selectedPatient
  });

  const { data: recentDocs, isLoading: docsLoading } = useQuery<GeneratedDocument[]>({
    queryKey: ["/api/ai/documents/recent"]
  });

  const generateMutation = useMutation({
    mutationFn: async (data: { patientId: number; documentType: string; additionalContext: string }) => {
      const res = await apiRequest("POST", "/api/ai/generate-document", data);
      return res.json();
    },
    onSuccess: (data) => {
      setGeneratedContent(data.content);
      queryClient.invalidateQueries({ queryKey: ["/api/ai/documents/recent"] });
      toast({ title: "Document Generated", description: "Your document has been created successfully" });
    },
    onError: (error: Error) => {
      toast({ title: "Generation Failed", description: error.message, variant: "destructive" });
    }
  });

  const handleGenerate = () => {
    if (!selectedPatient) {
      toast({ title: "Select Patient", description: "Please select a patient first", variant: "destructive" });
      return;
    }
    generateMutation.mutate({
      patientId: parseInt(selectedPatient),
      documentType: selectedDocType,
      additionalContext
    });
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(generatedContent);
    toast({ title: "Copied", description: "Document copied to clipboard" });
  };

  const downloadDocument = () => {
    const blob = new Blob([generatedContent], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selectedDocType}-${new Date().toISOString().split("T")[0]}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const selectedDocInfo = documentTypes.find(d => d.id === selectedDocType);

  return (
    <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(100vh-80px)]">
      <div>
        <h1 className="text-3xl font-bold" data-testid="text-page-title">AI Documentation Engine</h1>
        <p className="text-muted-foreground">
          Generate insurance-ready clinical documentation in seconds with AI
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                Generate Document
              </CardTitle>
              <CardDescription>
                Select patient and document type to generate AI-powered clinical documentation
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Select Patient</Label>
                  <Select value={selectedPatient} onValueChange={setSelectedPatient}>
                    <SelectTrigger data-testid="select-patient">
                      <SelectValue placeholder="Choose a patient..." />
                    </SelectTrigger>
                    <SelectContent>
                      {patients?.map((patient) => (
                        <SelectItem key={patient.id} value={patient.id.toString()}>
                          <div className="flex items-center gap-2">
                            <User className="h-4 w-4" />
                            {patient.firstName} {patient.lastName}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Document Type</Label>
                  <Select value={selectedDocType} onValueChange={setSelectedDocType}>
                    <SelectTrigger data-testid="select-doc-type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {documentTypes.map((doc) => (
                        <SelectItem key={doc.id} value={doc.id}>
                          <div className="flex items-center gap-2">
                            <doc.icon className="h-4 w-4" />
                            {doc.label}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {selectedDocInfo && (
                <div className="p-3 bg-muted/50 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <selectedDocInfo.icon className="h-4 w-4 text-primary" />
                    <span className="font-medium">{selectedDocInfo.label}</span>
                  </div>
                  <p className="text-sm text-muted-foreground">{selectedDocInfo.description}</p>
                </div>
              )}

              <div className="space-y-2">
                <Label>Additional Context (Optional)</Label>
                <Textarea
                  placeholder="Add any specific details, clinical findings, or context for the AI to include..."
                  value={additionalContext}
                  onChange={(e) => setAdditionalContext(e.target.value)}
                  rows={3}
                  data-testid="input-context"
                />
              </div>

              <Button 
                onClick={handleGenerate} 
                disabled={generateMutation.isPending || !selectedPatient}
                className="w-full"
                data-testid="button-generate"
              >
                {generateMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-2 h-4 w-4" />
                    Generate Document
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {generatedContent && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Generated Document</CardTitle>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={copyToClipboard} data-testid="button-copy">
                      <Copy className="h-4 w-4 mr-1" />
                      Copy
                    </Button>
                    <Button variant="outline" size="sm" onClick={downloadDocument} data-testid="button-download">
                      <Download className="h-4 w-4 mr-1" />
                      Download
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="bg-muted/30 p-4 rounded-lg whitespace-pre-wrap font-mono text-sm" data-testid="text-generated-content">
                  {generatedContent}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Document Templates</CardTitle>
              <CardDescription>Quick access to common document types</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {documentTypes.map((doc) => (
                <Button
                  key={doc.id}
                  variant={selectedDocType === doc.id ? "default" : "ghost"}
                  className="w-full justify-start"
                  onClick={() => setSelectedDocType(doc.id)}
                  data-testid={`button-template-${doc.id}`}
                >
                  <doc.icon className="h-4 w-4 mr-2" />
                  {doc.label}
                </Button>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Recent Documents</CardTitle>
              <CardDescription>Previously generated documentation</CardDescription>
            </CardHeader>
            <CardContent>
              {docsLoading ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-16" />
                  ))}
                </div>
              ) : recentDocs && recentDocs.length > 0 ? (
                <div className="space-y-2">
                  {recentDocs.slice(0, 5).map((doc) => (
                    <div 
                      key={doc.id} 
                      className="p-3 border rounded-lg hover-elevate cursor-pointer"
                      data-testid={`doc-${doc.id}`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-sm">{doc.title}</span>
                        <Badge variant="outline" className="text-xs">
                          {doc.documentType.replace("-", " ")}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                        <Calendar className="h-3 w-3" />
                        {new Date(doc.createdAt).toLocaleDateString()}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No documents generated yet
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">AI Capabilities</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-green-500" />
                <span className="text-sm">30-second generation time</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-green-500" />
                <span className="text-sm">Payer-specific formatting</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-green-500" />
                <span className="text-sm">ICD-10/CPT code integration</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-green-500" />
                <span className="text-sm">Medical necessity optimization</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
