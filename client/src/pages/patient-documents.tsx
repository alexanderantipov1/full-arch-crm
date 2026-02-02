import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Image, FileText, Upload, Search, Plus, Trash2, Eye, X, Download, Camera, Film } from "lucide-react";
import { format } from "date-fns";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import type { Patient, PatientDocument } from "@shared/schema";

const documentFormSchema = z.object({
  patientId: z.string().min(1, "Patient is required"),
  documentType: z.string().min(1, "Document type is required"),
  category: z.string().min(1, "Category is required"),
  fileName: z.string().min(1, "File name is required"),
  fileUrl: z.string().min(1, "File URL is required"),
  description: z.string().optional(),
});

type DocumentFormData = z.infer<typeof documentFormSchema>;

const documentTypes = [
  { value: "xray", label: "X-Ray" },
  { value: "photo", label: "Clinical Photo" },
  { value: "scan", label: "CT Scan" },
  { value: "intraoral", label: "Intraoral Image" },
  { value: "panoramic", label: "Panoramic X-Ray" },
  { value: "cbct", label: "CBCT Scan" },
  { value: "model", label: "Digital Model" },
  { value: "consent", label: "Signed Consent" },
  { value: "insurance", label: "Insurance Document" },
  { value: "other", label: "Other" },
];

const categoryOptions = [
  { value: "pre-treatment", label: "Pre-Treatment" },
  { value: "during-treatment", label: "During Treatment" },
  { value: "post-treatment", label: "Post-Treatment" },
  { value: "diagnostic", label: "Diagnostic" },
  { value: "administrative", label: "Administrative" },
];

export default function PatientDocumentsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [patientFilter, setPatientFilter] = useState("all");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<PatientDocument | null>(null);
  const { toast } = useToast();

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const { data: documents = [], isLoading } = useQuery<PatientDocument[]>({
    queryKey: ["/api/documents"],
  });

  const form = useForm<DocumentFormData>({
    resolver: zodResolver(documentFormSchema),
    defaultValues: {
      patientId: "",
      documentType: "",
      category: "",
      fileName: "",
      fileUrl: "",
      description: "",
    },
  });

  const createDocumentMutation = useMutation({
    mutationFn: async (data: DocumentFormData) => {
      return apiRequest("/api/documents", {
        method: "POST",
        body: JSON.stringify({
          patientId: parseInt(data.patientId),
          documentType: data.documentType,
          category: data.category,
          fileName: data.fileName,
          fileUrl: data.fileUrl,
          description: data.description,
          mimeType: data.documentType.includes("photo") || data.documentType === "intraoral" ? "image/jpeg" : "application/pdf",
        }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/documents"] });
      toast({ title: "Document uploaded successfully" });
      setIsDialogOpen(false);
      form.reset();
    },
    onError: () => {
      toast({ title: "Failed to upload document", variant: "destructive" });
    },
  });

  const deleteDocumentMutation = useMutation({
    mutationFn: async (id: number) => {
      return apiRequest(`/api/documents/${id}`, {
        method: "DELETE",
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/documents"] });
      toast({ title: "Document deleted" });
    },
    onError: () => {
      toast({ title: "Failed to delete document", variant: "destructive" });
    },
  });

  const onSubmit = (data: DocumentFormData) => {
    createDocumentMutation.mutate(data);
  };

  const getPatientName = (patientId: number) => {
    const patient = patients.find((p) => p.id === patientId);
    return patient ? `${patient.firstName} ${patient.lastName}` : "Unknown";
  };

  const getDocTypeLabel = (type: string) => {
    return documentTypes.find(t => t.value === type)?.label || type;
  };

  const getDocIcon = (type: string) => {
    if (type.includes("xray") || type.includes("scan") || type === "panoramic" || type === "cbct") {
      return <Film className="h-4 w-4" />;
    } else if (type.includes("photo") || type === "intraoral") {
      return <Camera className="h-4 w-4" />;
    }
    return <FileText className="h-4 w-4" />;
  };

  const isImageType = (doc: PatientDocument) => {
    return doc.mimeType?.startsWith("image/") || 
           doc.documentType === "photo" || 
           doc.documentType === "intraoral";
  };

  const filteredDocuments = documents.filter((doc) => {
    const patientName = getPatientName(doc.patientId);
    const matchesSearch = 
      patientName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.fileName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.description?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = typeFilter === "all" || doc.documentType === typeFilter;
    const matchesPatient = patientFilter === "all" || doc.patientId.toString() === patientFilter;
    return matchesSearch && matchesType && matchesPatient;
  });

  const photoCount = documents.filter(d => d.documentType === "photo" || d.documentType === "intraoral").length;
  const xrayCount = documents.filter(d => d.documentType.includes("xray") || d.documentType === "panoramic" || d.documentType === "cbct").length;

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2" data-testid="text-page-title">
            <Image className="h-8 w-8 text-primary" />
            Patient Documents
          </h1>
          <p className="text-muted-foreground">Manage photos, X-rays, and clinical documentation</p>
        </div>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="button-upload">
              <Upload className="h-4 w-4 mr-2" />
              Upload Document
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Upload Document</DialogTitle>
              <DialogDescription>Add a new clinical photo, X-ray, or document</DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="patientId"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Patient</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger data-testid="select-patient">
                            <SelectValue placeholder="Select patient" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {patients.map((patient) => (
                            <SelectItem key={patient.id} value={patient.id.toString()}>
                              {patient.firstName} {patient.lastName}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="grid grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="documentType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Document Type</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-type">
                              <SelectValue placeholder="Select type" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {documentTypes.map((type) => (
                              <SelectItem key={type.value} value={type.value}>
                                {type.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="category"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Category</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-category">
                              <SelectValue placeholder="Select category" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {categoryOptions.map((cat) => (
                              <SelectItem key={cat.value} value={cat.value}>
                                {cat.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <FormField
                  control={form.control}
                  name="fileName"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>File Name</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., panoramic_xray_2024.jpg" {...field} data-testid="input-filename" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="fileUrl"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>File URL</FormLabel>
                      <FormControl>
                        <Input placeholder="https://storage.example.com/..." {...field} data-testid="input-url" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="description"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Description (Optional)</FormLabel>
                      <FormControl>
                        <Textarea placeholder="Add notes about this document..." {...field} data-testid="input-description" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <DialogFooter>
                  <Button type="submit" disabled={createDocumentMutation.isPending} data-testid="button-submit">
                    {createDocumentMutation.isPending ? "Uploading..." : "Upload Document"}
                  </Button>
                </DialogFooter>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Total Documents</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-total">{documents.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Clinical Photos</CardTitle>
            <Camera className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600" data-testid="stat-photos">{photoCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">X-Rays & Scans</CardTitle>
            <Film className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600" data-testid="stat-xrays">{xrayCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Patients with Docs</CardTitle>
            <Image className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600" data-testid="stat-patients">
              {new Set(documents.map(d => d.patientId)).size}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Documents List */}
      <Card>
        <CardHeader>
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <CardTitle>All Documents</CardTitle>
              <CardDescription>Browse and manage patient clinical images</CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search documents..."
                  className="pl-8 w-48"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  data-testid="input-search"
                />
              </div>
              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="w-32" data-testid="filter-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  {documentTypes.map((type) => (
                    <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={patientFilter} onValueChange={setPatientFilter}>
                <SelectTrigger className="w-40" data-testid="filter-patient">
                  <SelectValue placeholder="All Patients" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Patients</SelectItem>
                  {patients.map((patient) => (
                    <SelectItem key={patient.id} value={patient.id.toString()}>
                      {patient.firstName} {patient.lastName}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-center py-8 text-muted-foreground">Loading documents...</p>
          ) : filteredDocuments.length === 0 ? (
            <div className="text-center py-12">
              <Image className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No Documents</h3>
              <p className="text-muted-foreground mb-4">Upload clinical photos, X-rays, and documentation</p>
              <Button onClick={() => setIsDialogOpen(true)} data-testid="button-add-first">
                <Upload className="h-4 w-4 mr-2" />
                Upload First Document
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredDocuments.map((doc) => (
                <div
                  key={doc.id}
                  className="border rounded-lg overflow-hidden hover-elevate"
                  data-testid={`doc-card-${doc.id}`}
                >
                  <div className="h-40 bg-muted flex items-center justify-center">
                    {isImageType(doc) ? (
                      <img
                        src={doc.fileUrl}
                        alt={doc.fileName}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          e.currentTarget.style.display = "none";
                          e.currentTarget.parentElement!.innerHTML = '<div class="text-muted-foreground text-center"><svg class="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg><p class="mt-2 text-sm">Image not available</p></div>';
                        }}
                      />
                    ) : (
                      <div className="text-muted-foreground text-center">
                        <FileText className="w-12 h-12 mx-auto mb-2" />
                        <p className="text-sm">{getDocTypeLabel(doc.documentType)}</p>
                      </div>
                    )}
                  </div>
                  <div className="p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {getDocIcon(doc.documentType)}
                        <span className="font-medium truncate max-w-32">{doc.fileName}</span>
                      </div>
                      <Badge variant="secondary" className="text-xs">
                        {doc.category || "Uncategorized"}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{getPatientName(doc.patientId)}</p>
                    {doc.description && (
                      <p className="text-xs text-muted-foreground line-clamp-2">{doc.description}</p>
                    )}
                    <div className="flex items-center justify-between pt-2">
                      <span className="text-xs text-muted-foreground">
                        {format(new Date(doc.createdAt), "MMM d, yyyy")}
                      </span>
                      <div className="flex gap-1">
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => setPreviewDoc(doc)}
                          data-testid={`button-view-${doc.id}`}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => window.open(doc.fileUrl, "_blank")}
                          data-testid={`button-download-${doc.id}`}
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => deleteDocumentMutation.mutate(doc.id)}
                          data-testid={`button-delete-${doc.id}`}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Preview Dialog */}
      <Dialog open={!!previewDoc} onOpenChange={() => setPreviewDoc(null)}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {previewDoc && getDocIcon(previewDoc.documentType)}
              {previewDoc?.fileName}
            </DialogTitle>
            <DialogDescription>
              {previewDoc && getPatientName(previewDoc.patientId)} • {previewDoc?.category}
            </DialogDescription>
          </DialogHeader>
          {previewDoc && (
            <div className="space-y-4">
              {isImageType(previewDoc) ? (
                <img
                  src={previewDoc.fileUrl}
                  alt={previewDoc.fileName}
                  className="w-full max-h-[60vh] object-contain rounded-lg"
                />
              ) : (
                <div className="bg-muted rounded-lg p-8 text-center">
                  <FileText className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
                  <p className="mb-4">Document preview not available</p>
                  <Button onClick={() => window.open(previewDoc.fileUrl, "_blank")}>
                    <Download className="h-4 w-4 mr-2" />
                    Download to View
                  </Button>
                </div>
              )}
              {previewDoc.description && (
                <div className="border-t pt-4">
                  <h4 className="font-medium mb-2">Description</h4>
                  <p className="text-muted-foreground">{previewDoc.description}</p>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
