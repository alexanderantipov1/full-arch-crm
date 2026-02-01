import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { FileText, Plus, Search, Calendar, User } from "lucide-react";
import { format } from "date-fns";
import type { Patient, ClinicalNote } from "@shared/schema";

export default function ClinicalNotesPage() {
  const [searchQuery, setSearchQuery] = useState("");

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const { data: notes = [], isLoading } = useQuery<ClinicalNote[]>({
    queryKey: ["/api/clinical-notes"],
  });

  const filteredNotes = notes.filter((note) => {
    const patient = patients.find((p) => p.id === note.patientId);
    const patientName = patient ? `${patient.firstName} ${patient.lastName}` : "";
    return (
      patientName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      note.noteType.toLowerCase().includes(searchQuery.toLowerCase()) ||
      note.content?.toLowerCase().includes(searchQuery.toLowerCase())
    );
  });

  const getPatientName = (patientId: number) => {
    const patient = patients.find((p) => p.id === patientId);
    return patient ? `${patient.firstName} ${patient.lastName}` : "Unknown Patient";
  };

  const noteTypeColors: Record<string, string> = {
    progress: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
    consultation: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
    procedure: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
    followup: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
    other: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
  };

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2" data-testid="text-page-title">
            <FileText className="h-8 w-8 text-primary" />
            Clinical Notes
          </h1>
          <p className="text-muted-foreground">View and manage patient clinical documentation</p>
        </div>
        <Button data-testid="button-add-note">
          <Plus className="h-4 w-4 mr-2" />
          Add Note
        </Button>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <CardTitle>All Clinical Notes</CardTitle>
              <CardDescription>Documentation from patient visits and procedures</CardDescription>
            </div>
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search notes..."
                className="pl-8 w-64"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                data-testid="input-search"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-center py-8 text-muted-foreground">Loading clinical notes...</p>
          ) : filteredNotes.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No Clinical Notes Yet</h3>
              <p className="text-muted-foreground mb-4">Start documenting patient visits and procedures</p>
              <Button data-testid="button-add-first-note">
                <Plus className="h-4 w-4 mr-2" />
                Add First Note
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredNotes.map((note) => (
                <div
                  key={note.id}
                  className="p-4 border rounded-lg hover-elevate cursor-pointer"
                  data-testid={`note-row-${note.id}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium">{getPatientName(note.patientId)}</span>
                        <Badge className={noteTypeColors[note.noteType] || noteTypeColors.other}>
                          {note.noteType}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground line-clamp-2">
                        {note.content || "No content available"}
                      </p>
                    </div>
                    <div className="text-right text-sm text-muted-foreground flex items-center gap-1">
                      <Calendar className="h-4 w-4" />
                      {format(new Date(note.createdAt), "MMM d, yyyy")}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
