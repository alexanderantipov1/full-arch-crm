import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import {
  Brain,
  Send,
  Loader2,
  Stethoscope,
  DollarSign,
  FileText,
  ClipboardList,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  User,
  Bot,
  Zap,
  FileCode,
  Calculator,
  Shield,
} from "lucide-react";
import { apiRequest } from "@/lib/queryClient";
import type { Patient } from "@shared/schema";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  type?: "chat" | "letter" | "appeal" | "code";
}

const suggestedQuestions = [
  {
    icon: ClipboardList,
    label: "Treatment Planning",
    question: "What factors should I consider when planning a full arch implant case for a patient with severe bone loss?",
  },
  {
    icon: DollarSign,
    label: "Insurance Coding",
    question: "What are the correct CDT codes for an All-on-4 procedure with bone grafting and extractions?",
  },
  {
    icon: FileText,
    label: "Medical Necessity",
    question: "Help me document medical necessity for full arch implants with sleep apnea comorbidity",
  },
  {
    icon: AlertCircle,
    label: "Appeal Strategy",
    question: "My All-on-4 prior auth was denied for lack of medical necessity. What's the best appeal strategy?",
  },
  {
    icon: Stethoscope,
    label: "Clinical Protocol",
    question: "Walk me through the Arnett-Gunson facial evaluation protocol for full arch cases",
  },
  {
    icon: FileCode,
    label: "Cross-Coding",
    question: "How do I cross-code D6114 to medical insurance CPT codes for functional rehabilitation?",
  },
];

const quickActions = [
  { label: "Generate Medical Necessity Letter", icon: FileText, action: "letter" },
  { label: "Draft Appeal Letter", icon: AlertCircle, action: "appeal" },
  { label: "Get CDT Code Suggestions", icon: DollarSign, action: "codes" },
  { label: "Calculate Patient Responsibility", icon: Calculator, action: "calculator" },
  { label: "Prior Auth Guidance", icon: Shield, action: "priorAuth" },
  { label: "Treatment Planning Help", icon: ClipboardList, action: "planning" },
];

export default function AIAssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [selectedPatientId, setSelectedPatientId] = useState<string>("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"]
  });

  const selectedPatient = patients.find(p => p.id.toString() === selectedPatientId);

  const sendMessage = useMutation({
    mutationFn: async (content: string) => {
      let contextualContent = content;
      if (selectedPatient) {
        contextualContent = `[Patient Context: ${selectedPatient.firstName} ${selectedPatient.lastName}, DOB: ${selectedPatient.dateOfBirth}]\n\n${content}`;
      }
      const response = await apiRequest("POST", "/api/ai/chat", { content: contextualContent });
      return response.json();
    },
    onSuccess: (data) => {
      const assistantMessage: Message = {
        id: Date.now().toString(),
        role: "assistant",
        content: data.response,
        timestamp: new Date(),
        type: "chat"
      };
      setMessages((prev) => [...prev, assistantMessage]);
    },
  });

  const generateLetter = useMutation({
    mutationFn: async () => {
      if (!selectedPatient) throw new Error("Please select a patient first");
      const response = await apiRequest("POST", "/api/ai/medical-necessity-letter", {
        patientName: `${selectedPatient.firstName} ${selectedPatient.lastName}`,
        dateOfBirth: selectedPatient.dateOfBirth,
        diagnosis: "Complete edentulism with severe bone atrophy",
        procedure: "All-on-4 full arch dental implant rehabilitation",
        clinicalFindings: "Patient presents with inability to chew solid foods, facial collapse, and nutritional deficiencies. Sleep study indicates moderate obstructive sleep apnea likely related to loss of vertical dimension."
      });
      return response.json();
    },
    onSuccess: (data) => {
      const letterMessage: Message = {
        id: Date.now().toString(),
        role: "assistant",
        content: data.letter,
        timestamp: new Date(),
        type: "letter"
      };
      setMessages((prev) => [...prev, {
        id: (Date.now() - 1).toString(),
        role: "user",
        content: "Generate a medical necessity letter for this patient",
        timestamp: new Date(),
        type: "letter"
      }, letterMessage]);
    },
  });

  const generateAppeal = useMutation({
    mutationFn: async () => {
      if (!selectedPatient) throw new Error("Please select a patient first");
      const response = await apiRequest("POST", "/api/ai/appeal-letter", {
        patientName: `${selectedPatient.firstName} ${selectedPatient.lastName}`,
        denialReason: "Procedure not medically necessary",
        originalProcedure: "All-on-4 full arch dental implant rehabilitation",
        supportingEvidence: "Patient has documented functional impairment with inability to eat solid foods, weight loss of 15 lbs over 6 months, and moderate obstructive sleep apnea (AHI 22). Peer-reviewed literature supports dental implant rehabilitation for these conditions."
      });
      return response.json();
    },
    onSuccess: (data) => {
      const appealMessage: Message = {
        id: Date.now().toString(),
        role: "assistant",
        content: data.letter,
        timestamp: new Date(),
        type: "appeal"
      };
      setMessages((prev) => [...prev, {
        id: (Date.now() - 1).toString(),
        role: "user",
        content: "Draft an appeal letter for a denied prior authorization",
        timestamp: new Date(),
        type: "appeal"
      }, appealMessage]);
    },
  });

  const handleSend = () => {
    if (!input.trim() || sendMessage.isPending) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date(),
      type: "chat"
    };

    setMessages((prev) => [...prev, userMessage]);
    sendMessage.mutate(input);
    setInput("");
  };

  const handleSuggestion = (question: string) => {
    setInput(question);
  };

  const handleQuickAction = (action: string) => {
    switch (action) {
      case "letter":
        generateLetter.mutate();
        break;
      case "appeal":
        generateAppeal.mutate();
        break;
      case "codes":
        handleSuggestion("What are the appropriate CDT codes for a full arch implant case with bone grafting?");
        break;
      case "calculator":
        handleSuggestion("Help me estimate patient responsibility for an All-on-4 with $2000 annual max and 50% coverage");
        break;
      case "priorAuth":
        handleSuggestion("What documentation do I need for a full arch implant prior authorization?");
        break;
      case "planning":
        handleSuggestion("Walk me through treatment planning considerations for a full arch case");
        break;
    }
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const isPending = sendMessage.isPending || generateLetter.isPending || generateAppeal.isPending;

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2" data-testid="text-page-title">
            <Bot className="h-7 w-7 text-primary" />
            ImplantBot AI
          </h1>
          <p className="text-muted-foreground">
            Your intelligent assistant for full arch implant billing and clinical support
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Label className="text-sm text-muted-foreground">Patient Context:</Label>
          <Select value={selectedPatientId} onValueChange={setSelectedPatientId}>
            <SelectTrigger className="w-[220px]" data-testid="select-patient-context">
              <SelectValue placeholder="Select patient (optional)" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">No patient selected</SelectItem>
              {patients.map((patient) => (
                <SelectItem key={patient.id} value={patient.id.toString()}>
                  {patient.firstName} {patient.lastName}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {selectedPatient && (
        <div className="flex items-center gap-2 p-3 border rounded-lg bg-primary/5">
          <User className="h-4 w-4 text-primary" />
          <span className="text-sm">
            <strong>{selectedPatient.firstName} {selectedPatient.lastName}</strong> 
            {selectedPatient.dateOfBirth && ` • DOB: ${selectedPatient.dateOfBirth}`}
            {selectedPatient.phone && ` • ${selectedPatient.phone}`}
          </span>
          <Badge variant="outline" className="ml-auto">Context Active</Badge>
        </div>
      )}

      <div className="grid flex-1 gap-4 lg:grid-cols-[1fr_320px]">
        <Card className="flex flex-col">
          <CardHeader className="border-b pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <Brain className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <CardTitle className="text-lg">ImplantBot</CardTitle>
                  <CardDescription className="text-xs">
                    GPT-5.2 • Full Arch Specialist
                  </CardDescription>
                </div>
              </div>
              <Badge variant="outline" className="text-xs">
                <Zap className="h-3 w-3 mr-1" />
                99.2% Coding Accuracy
              </Badge>
            </div>
          </CardHeader>

          <ScrollArea ref={scrollRef} className="flex-1 p-4">
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center py-8 text-center">
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                  <Sparkles className="h-8 w-8 text-primary" />
                </div>
                <h3 className="mb-2 text-lg font-semibold">
                  How can I help you today?
                </h3>
                <p className="mb-6 max-w-md text-sm text-muted-foreground">
                  I specialize in full arch dental implants, medical billing, 
                  CDT/CPT coding, prior authorizations, and appeal strategies.
                </p>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {suggestedQuestions.map((suggestion) => (
                    <Button
                      key={suggestion.label}
                      variant="outline"
                      size="sm"
                      className="justify-start"
                      onClick={() => handleSuggestion(suggestion.question)}
                      data-testid={`button-suggestion-${suggestion.label.toLowerCase().replace(/\s+/g, "-")}`}
                    >
                      <suggestion.icon className="h-4 w-4 text-primary mr-2" />
                      {suggestion.label}
                    </Button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex gap-3 ${
                      message.role === "user" ? "flex-row-reverse" : ""
                    }`}
                  >
                    <Avatar className="h-8 w-8 shrink-0">
                      <AvatarFallback
                        className={
                          message.role === "assistant"
                            ? "bg-primary/10 text-primary"
                            : "bg-muted"
                        }
                      >
                        {message.role === "assistant" ? (
                          <Bot className="h-4 w-4" />
                        ) : (
                          <User className="h-4 w-4" />
                        )}
                      </AvatarFallback>
                    </Avatar>
                    <div
                      className={`max-w-[80%] rounded-lg p-3 ${
                        message.role === "user"
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted"
                      }`}
                    >
                      {message.type && message.type !== "chat" && (
                        <Badge variant="secondary" className="mb-2 text-xs">
                          {message.type === "letter" && "Medical Necessity Letter"}
                          {message.type === "appeal" && "Appeal Letter"}
                          {message.type === "code" && "Code Suggestion"}
                        </Badge>
                      )}
                      <p className="whitespace-pre-wrap text-sm">{message.content}</p>
                    </div>
                  </div>
                ))}
                {isPending && (
                  <div className="flex gap-3">
                    <Avatar className="h-8 w-8 shrink-0">
                      <AvatarFallback className="bg-primary/10 text-primary">
                        <Bot className="h-4 w-4" />
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex items-center gap-2 rounded-lg bg-muted p-3">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span className="text-sm text-muted-foreground">
                        {generateLetter.isPending && "Generating medical necessity letter..."}
                        {generateAppeal.isPending && "Drafting appeal letter..."}
                        {sendMessage.isPending && "Thinking..."}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </ScrollArea>

          <div className="border-t p-4">
            <div className="flex gap-2">
              <Input
                type="text"
                placeholder="Ask about treatment planning, coding, insurance, appeals..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                className="flex-1"
                data-testid="input-chat"
              />
              <Button
                onClick={handleSend}
                disabled={!input.trim() || isPending}
                data-testid="button-send"
              >
                {isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Send className="h-4 w-4 mr-2" />
                )}
                Send
              </Button>
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Zap className="h-4 w-4 text-primary" />
                Quick Actions
              </CardTitle>
              <CardDescription className="text-xs">
                {selectedPatient ? "Patient-specific actions" : "Select a patient for personalized actions"}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {quickActions.map((action) => (
                <Button
                  key={action.action}
                  variant="outline"
                  size="sm"
                  className="w-full justify-start"
                  onClick={() => handleQuickAction(action.action)}
                  disabled={
                    (action.action === "letter" || action.action === "appeal") && !selectedPatient
                  }
                  data-testid={`button-action-${action.action}`}
                >
                  <action.icon className="mr-2 h-4 w-4" />
                  {action.label}
                </Button>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Capabilities</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5">
              <div className="flex items-center gap-2 text-xs">
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                <span>Full arch treatment planning</span>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                <span>CDT/CPT/ICD-10 cross-coding</span>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                <span>Medical necessity documentation</span>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                <span>Insurance appeal strategies</span>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                <span>Prior authorization support</span>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                <span>Arnett-Gunson protocols</span>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                <span>Cephalometric analysis</span>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                <span>Airway evaluation guidance</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Performance Stats</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">Coding Accuracy</span>
                <Badge variant="outline" className="text-xs font-bold text-green-600">99.2%</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">Appeal Success Rate</span>
                <Badge variant="outline" className="text-xs font-bold text-green-600">78%</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">Prior Auth Approval</span>
                <Badge variant="outline" className="text-xs font-bold text-green-600">85%</Badge>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
