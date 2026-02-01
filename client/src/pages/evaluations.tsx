import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Stethoscope, Plus, Search, User, Calendar, FileText } from "lucide-react";
import { format } from "date-fns";
import type { Patient, FullArchExam, FacialEvaluation } from "@shared/schema";

export default function EvaluationsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState("full-arch");

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const { data: fullArchExams = [], isLoading: loadingExams } = useQuery<FullArchExam[]>({
    queryKey: ["/api/full-arch-exams"],
  });

  const { data: facialEvals = [], isLoading: loadingFacial } = useQuery<FacialEvaluation[]>({
    queryKey: ["/api/facial-evaluations"],
  });

  const getPatientName = (patientId: number) => {
    const patient = patients.find((p) => p.id === patientId);
    return patient ? `${patient.firstName} ${patient.lastName}` : "Unknown Patient";
  };

  const filteredExams = fullArchExams.filter((exam) => {
    const patientName = getPatientName(exam.patientId);
    return patientName.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const filteredFacialEvals = facialEvals.filter((evalItem) => {
    const patientName = getPatientName(evalItem.patientId);
    return patientName.toLowerCase().includes(searchQuery.toLowerCase());
  });

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2" data-testid="text-page-title">
            <Stethoscope className="h-8 w-8 text-primary" />
            Exams & Evaluations
          </h1>
          <p className="text-muted-foreground">Manage full arch exams and facial evaluations</p>
        </div>
        <Button data-testid="button-add-evaluation">
          <Plus className="h-4 w-4 mr-2" />
          New Evaluation
        </Button>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <CardTitle>Patient Evaluations</CardTitle>
              <CardDescription>Full arch exams and facial assessments</CardDescription>
            </div>
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by patient..."
                className="pl-8 w-64"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                data-testid="input-search"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-4">
              <TabsTrigger value="full-arch" data-testid="tab-full-arch">
                Full Arch Exams ({fullArchExams.length})
              </TabsTrigger>
              <TabsTrigger value="facial" data-testid="tab-facial">
                Facial Evaluations ({facialEvals.length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="full-arch">
              {loadingExams ? (
                <p className="text-center py-8 text-muted-foreground">Loading exams...</p>
              ) : filteredExams.length === 0 ? (
                <div className="text-center py-12">
                  <FileText className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-medium mb-2">No Full Arch Exams</h3>
                  <p className="text-muted-foreground mb-4">Start by adding a comprehensive exam</p>
                  <Button data-testid="button-add-exam">
                    <Plus className="h-4 w-4 mr-2" />
                    Add Exam
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {filteredExams.map((exam) => (
                    <div
                      key={exam.id}
                      className="p-4 border rounded-lg hover-elevate cursor-pointer"
                      data-testid={`exam-row-${exam.id}`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <User className="h-5 w-5 text-muted-foreground" />
                          <div>
                            <p className="font-medium">{getPatientName(exam.patientId)}</p>
                            <p className="text-sm text-muted-foreground">
                              Chief Complaint: {exam.chiefComplaint || "Not specified"}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="text-sm text-muted-foreground flex items-center gap-1">
                            <Calendar className="h-4 w-4" />
                            {format(new Date(exam.examDate), "MMM d, yyyy")}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="facial">
              {loadingFacial ? (
                <p className="text-center py-8 text-muted-foreground">Loading evaluations...</p>
              ) : filteredFacialEvals.length === 0 ? (
                <div className="text-center py-12">
                  <Stethoscope className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-medium mb-2">No Facial Evaluations</h3>
                  <p className="text-muted-foreground mb-4">Add facial assessment data for patients</p>
                  <Button data-testid="button-add-facial">
                    <Plus className="h-4 w-4 mr-2" />
                    Add Evaluation
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {filteredFacialEvals.map((evalItem) => (
                    <div
                      key={evalItem.id}
                      className="p-4 border rounded-lg hover-elevate cursor-pointer"
                      data-testid={`facial-row-${evalItem.id}`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <User className="h-5 w-5 text-muted-foreground" />
                          <div>
                            <p className="font-medium">{getPatientName(evalItem.patientId)}</p>
                            <p className="text-sm text-muted-foreground">
                              Facial Profile: {evalItem.facialProfile || "Not assessed"}
                            </p>
                          </div>
                        </div>
                        <div className="text-sm text-muted-foreground flex items-center gap-1">
                          <Calendar className="h-4 w-4" />
                          {format(new Date(evalItem.updatedAt), "MMM d, yyyy")}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
