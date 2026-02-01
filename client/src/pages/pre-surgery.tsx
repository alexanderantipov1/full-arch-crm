import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/hooks/use-toast";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { 
  Syringe, Plus, Clock, CheckCircle, XCircle, 
  FileText, Pill, Droplet, ScanLine, User, AlertCircle
} from "lucide-react";
import type { PreSurgeryTask, Patient } from "@shared/schema";

const taskFormSchema = z.object({
  patientId: z.number().min(1, "Patient is required"),
  taskType: z.string().min(1, "Task type is required"),
  taskName: z.string().min(1, "Task name is required"),
  description: z.string().optional(),
  dueDate: z.string().optional(),
  assignedTo: z.string().optional(),
});

type TaskFormData = z.infer<typeof taskFormSchema>;

const taskTypes = [
  { value: "prescription", label: "Prescription", icon: Pill },
  { value: "blood_work", label: "Blood Work", icon: Droplet },
  { value: "ct_scan", label: "CT Scan / CBCT", icon: ScanLine },
  { value: "instructions", label: "Pre-Op Instructions", icon: FileText },
  { value: "clearance", label: "Medical Clearance", icon: CheckCircle },
  { value: "consent", label: "Consent Forms", icon: FileText },
  { value: "payment", label: "Payment Collection", icon: AlertCircle },
  { value: "other", label: "Other", icon: FileText },
];

const defaultTasks = [
  { type: "prescription", name: "Antibiotics (Amoxicillin 500mg)", description: "1 hour before surgery, then 3x daily for 7 days" },
  { type: "prescription", name: "Pain Management (Ibuprofen 600mg)", description: "As needed for pain, max 3x daily" },
  { type: "prescription", name: "Mouth Rinse (Chlorhexidine)", description: "Rinse 2x daily starting 3 days before surgery" },
  { type: "blood_work", name: "CBC & Metabolic Panel", description: "Complete blood count and comprehensive metabolic panel" },
  { type: "blood_work", name: "Coagulation Studies (PT/INR)", description: "For patients on anticoagulants" },
  { type: "ct_scan", name: "CBCT Scan", description: "Full arch CBCT for surgical planning" },
  { type: "instructions", name: "NPO Instructions", description: "Nothing to eat or drink 8 hours before surgery" },
  { type: "instructions", name: "Driver Arrangement", description: "Arrange for someone to drive home after sedation" },
];

export default function PreSurgeryPage() {
  const { toast } = useToast();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const { data: tasks = [], isLoading } = useQuery<PreSurgeryTask[]>({
    queryKey: ["/api/pre-surgery-tasks"],
  });

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const form = useForm<TaskFormData>({
    resolver: zodResolver(taskFormSchema),
    defaultValues: {
      patientId: 0,
      taskType: "",
      taskName: "",
      description: "",
      dueDate: "",
      assignedTo: "",
    },
  });

  const createTaskMutation = useMutation({
    mutationFn: async (data: TaskFormData) => {
      const res = await apiRequest("POST", "/api/pre-surgery-tasks", {
        ...data,
        status: "pending",
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/pre-surgery-tasks"] });
      setIsAddDialogOpen(false);
      form.reset();
      toast({ title: "Task Created", description: "Pre-surgery task has been added" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: async ({ id, status, completedDate }: { id: number; status: string; completedDate?: Date }) => {
      const res = await apiRequest("PATCH", `/api/pre-surgery-tasks/${id}`, { 
        status, 
        completedDate: status === "completed" ? new Date() : undefined 
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/pre-surgery-tasks"] });
      toast({ title: "Task Updated", description: "Task status has been updated" });
    },
  });

  const createBulkTasksMutation = useMutation({
    mutationFn: async (patientId: number) => {
      const promises = defaultTasks.map(task => 
        apiRequest("POST", "/api/pre-surgery-tasks", {
          patientId,
          taskType: task.type,
          taskName: task.name,
          description: task.description,
          status: "pending",
        })
      );
      return Promise.all(promises);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/pre-surgery-tasks"] });
      toast({ title: "Tasks Created", description: "Default pre-surgery tasks have been added" });
    },
  });

  const onSubmit = (data: TaskFormData) => {
    createTaskMutation.mutate(data);
  };

  const getPatientName = (patientId: number | null) => {
    if (!patientId) return "Unknown";
    const patient = patients.find(p => p.id === patientId);
    return patient ? `${patient.firstName} ${patient.lastName}` : "Unknown";
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "pending":
        return <Badge variant="outline"><Clock className="w-3 h-3 mr-1" /> Pending</Badge>;
      case "in_progress":
        return <Badge className="bg-blue-100 text-blue-800"><Clock className="w-3 h-3 mr-1" /> In Progress</Badge>;
      case "completed":
        return <Badge className="bg-green-100 text-green-800"><CheckCircle className="w-3 h-3 mr-1" /> Completed</Badge>;
      case "cancelled":
        return <Badge variant="destructive"><XCircle className="w-3 h-3 mr-1" /> Cancelled</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getTaskIcon = (taskType: string) => {
    const type = taskTypes.find(t => t.value === taskType);
    if (!type) return FileText;
    return type.icon;
  };

  const formatDate = (date: Date | string | null) => {
    if (!date) return "N/A";
    return new Date(date).toLocaleDateString();
  };

  const filteredTasks = tasks.filter(t => {
    if (selectedPatient && t.patientId !== selectedPatient) return false;
    if (statusFilter !== "all" && t.status !== statusFilter) return false;
    return true;
  });

  const pendingCount = tasks.filter(t => t.status === "pending").length;
  const completedCount = tasks.filter(t => t.status === "completed").length;
  const groupedByPatient = tasks.reduce((acc, task) => {
    const key = task.patientId;
    if (!acc[key]) acc[key] = [];
    acc[key].push(task);
    return acc;
  }, {} as Record<number, PreSurgeryTask[]>);

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" data-testid="text-page-title">Pre-Surgery Workflow</h1>
          <p className="text-muted-foreground">Manage pre-operative tasks and requirements</p>
        </div>
        <div className="flex gap-2">
          <Select value={selectedPatient?.toString() || "all"} onValueChange={(v) => setSelectedPatient(v === "all" ? null : parseInt(v))}>
            <SelectTrigger className="w-48" data-testid="filter-patient">
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
          <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
            <DialogTrigger asChild>
              <Button data-testid="button-add-task">
                <Plus className="w-4 h-4 mr-2" />
                Add Task
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Add Pre-Surgery Task</DialogTitle>
                <DialogDescription>Create a new pre-operative task for a patient</DialogDescription>
              </DialogHeader>
              <Form {...form}>
                <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <FormField
                      control={form.control}
                      name="patientId"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Patient</FormLabel>
                          <Select onValueChange={(v) => field.onChange(parseInt(v))} value={field.value?.toString()}>
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
                    <FormField
                      control={form.control}
                      name="taskType"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Task Type</FormLabel>
                          <Select onValueChange={field.onChange} value={field.value}>
                            <FormControl>
                              <SelectTrigger data-testid="select-type">
                                <SelectValue placeholder="Select type" />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {taskTypes.map((type) => (
                                <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>
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
                    name="taskName"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Task Name</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="Enter task name" data-testid="input-name" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <div className="grid grid-cols-2 gap-4">
                    <FormField
                      control={form.control}
                      name="dueDate"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Due Date</FormLabel>
                          <FormControl>
                            <Input {...field} type="date" data-testid="input-due" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="assignedTo"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Assigned To</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="Staff member" data-testid="input-assigned" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                  <FormField
                    control={form.control}
                    name="description"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Description</FormLabel>
                        <FormControl>
                          <Textarea {...field} placeholder="Task details and instructions..." data-testid="input-description" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <div className="flex justify-end gap-2">
                    <Button type="button" variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                      Cancel
                    </Button>
                    <Button type="submit" disabled={createTaskMutation.isPending} data-testid="button-submit">
                      {createTaskMutation.isPending ? "Creating..." : "Create Task"}
                    </Button>
                  </div>
                </form>
              </Form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Total Tasks</CardTitle>
            <Syringe className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-total">{tasks.length}</div>
            <p className="text-xs text-muted-foreground">All tasks</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Pending</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600" data-testid="stat-pending">{pendingCount}</div>
            <p className="text-xs text-muted-foreground">Need attention</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600" data-testid="stat-completed">{completedCount}</div>
            <p className="text-xs text-muted-foreground">Done</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Patients</CardTitle>
            <User className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-patients">{Object.keys(groupedByPatient).length}</div>
            <p className="text-xs text-muted-foreground">With active tasks</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="md:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Pre-Surgery Tasks</CardTitle>
                <CardDescription>Track and complete pre-operative requirements</CardDescription>
              </div>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-36" data-testid="filter-status">
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="in_progress">In Progress</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <p className="text-muted-foreground text-center py-4">Loading...</p>
            ) : filteredTasks.length === 0 ? (
              <div className="text-center py-12">
                <Syringe className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="text-lg font-medium mb-2">No Pre-Surgery Tasks</h3>
                <p className="text-muted-foreground mb-4">Add tasks or use quick setup for a patient</p>
                <Button onClick={() => setIsAddDialogOpen(true)} data-testid="button-add-first">
                  <Plus className="w-4 h-4 mr-2" />
                  Add Task
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredTasks.map((task) => {
                  const TaskIcon = getTaskIcon(task.taskType);
                  return (
                    <div key={task.id} className="flex items-center justify-between p-4 border rounded-lg" data-testid={`task-row-${task.id}`}>
                      <div className="flex items-center gap-4">
                        <Checkbox 
                          checked={task.status === "completed"}
                          onCheckedChange={(checked) => 
                            updateStatusMutation.mutate({ 
                              id: task.id, 
                              status: checked ? "completed" : "pending" 
                            })
                          }
                          data-testid={`check-${task.id}`}
                        />
                        <div className="flex items-center justify-center w-10 h-10 rounded-full bg-primary/10">
                          <TaskIcon className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                          <p className={`font-semibold ${task.status === "completed" ? "line-through text-muted-foreground" : ""}`}>
                            {task.taskName}
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge variant="outline" className="text-xs">
                              {getPatientName(task.patientId)}
                            </Badge>
                            {getStatusBadge(task.status)}
                          </div>
                          {task.description && (
                            <p className="text-sm text-muted-foreground mt-1">{task.description}</p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        {task.dueDate && (
                          <div className="text-right text-sm">
                            <p className="text-muted-foreground">Due: {formatDate(task.dueDate)}</p>
                          </div>
                        )}
                        {task.status !== "completed" && (
                          <Button 
                            size="sm"
                            onClick={() => updateStatusMutation.mutate({ id: task.id, status: "completed" })}
                            data-testid={`complete-${task.id}`}
                          >
                            Complete
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Pill className="w-5 h-5" />
                Quick Setup
              </CardTitle>
              <CardDescription>Add default pre-surgery tasks for a patient</CardDescription>
            </CardHeader>
            <CardContent>
              <Select onValueChange={(v) => v && createBulkTasksMutation.mutate(parseInt(v))}>
                <SelectTrigger data-testid="select-quick-setup">
                  <SelectValue placeholder="Select patient for quick setup" />
                </SelectTrigger>
                <SelectContent>
                  {patients.map((patient) => (
                    <SelectItem key={patient.id} value={patient.id.toString()}>
                      {patient.firstName} {patient.lastName}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground mt-2">
                Adds standard pre-surgery tasks: prescriptions, blood work, CT scan, and instructions
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5" />
                Standard Prescriptions
              </CardTitle>
              <CardDescription>Common pre-surgery medications</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="p-3 border rounded-lg">
                  <h4 className="font-semibold text-sm">Amoxicillin 500mg</h4>
                  <p className="text-xs text-muted-foreground">1 hour before, then TID x 7 days</p>
                </div>
                <div className="p-3 border rounded-lg">
                  <h4 className="font-semibold text-sm">Ibuprofen 600mg</h4>
                  <p className="text-xs text-muted-foreground">PRN pain, max TID</p>
                </div>
                <div className="p-3 border rounded-lg">
                  <h4 className="font-semibold text-sm">Chlorhexidine 0.12%</h4>
                  <p className="text-xs text-muted-foreground">Rinse BID starting 3 days pre-op</p>
                </div>
                <div className="p-3 border rounded-lg">
                  <h4 className="font-semibold text-sm">Dexamethasone 4mg</h4>
                  <p className="text-xs text-muted-foreground">Day before and morning of surgery</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
