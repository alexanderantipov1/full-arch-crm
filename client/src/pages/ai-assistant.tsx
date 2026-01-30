import { useState, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
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
} from "lucide-react";
import { apiRequest } from "@/lib/queryClient";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

const suggestedQuestions = [
  {
    icon: ClipboardList,
    label: "Treatment Planning",
    question: "What factors should I consider when planning a full arch implant case?",
  },
  {
    icon: DollarSign,
    label: "Insurance Coding",
    question: "What are the correct CDT codes for an All-on-4 procedure with bone grafting?",
  },
  {
    icon: FileText,
    label: "Medical Necessity",
    question: "Help me write a medical necessity letter for a full arch implant case",
  },
  {
    icon: AlertCircle,
    label: "Appeal Letter",
    question: "How do I appeal a denied prior authorization for dental implants?",
  },
];

export default function AIAssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const sendMessage = useMutation({
    mutationFn: async (content: string) => {
      const response = await apiRequest("POST", "/api/ai/chat", { content });
      return response.json();
    },
    onSuccess: (data) => {
      const assistantMessage: Message = {
        id: Date.now().toString(),
        role: "assistant",
        content: data.response,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    },
  });

  const handleSend = () => {
    if (!input.trim() || sendMessage.isPending) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    sendMessage.mutate(input);
    setInput("");
  };

  const handleSuggestion = (question: string) => {
    setInput(question);
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">AI Assistant</h1>
        <p className="text-muted-foreground">
          Get AI-powered help with diagnosis, treatment planning, coding, and insurance
        </p>
      </div>

      <div className="grid flex-1 gap-6 lg:grid-cols-[1fr_300px]">
        <Card className="flex flex-col">
          <CardHeader className="border-b pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Brain className="h-5 w-5 text-primary" />
              </div>
              <div>
                <CardTitle className="text-lg">Dental Implant AI</CardTitle>
                <CardDescription>
                  Specialized for full arch implants and oral surgery
                </CardDescription>
              </div>
            </div>
          </CardHeader>

          <ScrollArea ref={scrollRef} className="flex-1 p-4">
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center py-12 text-center">
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                  <Sparkles className="h-8 w-8 text-primary" />
                </div>
                <h3 className="mb-2 text-lg font-semibold">
                  How can I help you today?
                </h3>
                <p className="mb-6 max-w-md text-sm text-muted-foreground">
                  I can assist with treatment planning, insurance coding, medical necessity
                  letters, appeal letters, and clinical questions about dental implants.
                </p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {suggestedQuestions.map((suggestion) => (
                    <Button
                      key={suggestion.label}
                      variant="outline"
                      className="h-auto flex-col items-start gap-2 p-4 text-left hover-elevate"
                      onClick={() => handleSuggestion(suggestion.question)}
                      data-testid={`button-suggestion-${suggestion.label.toLowerCase().replace(/\s+/g, "-")}`}
                    >
                      <div className="flex items-center gap-2">
                        <suggestion.icon className="h-4 w-4 text-primary" />
                        <span className="font-medium">{suggestion.label}</span>
                      </div>
                      <span className="text-xs text-muted-foreground line-clamp-2">
                        {suggestion.question}
                      </span>
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
                          <Brain className="h-4 w-4" />
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
                      <p className="whitespace-pre-wrap text-sm">{message.content}</p>
                    </div>
                  </div>
                ))}
                {sendMessage.isPending && (
                  <div className="flex gap-3">
                    <Avatar className="h-8 w-8 shrink-0">
                      <AvatarFallback className="bg-primary/10 text-primary">
                        <Brain className="h-4 w-4" />
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex items-center gap-2 rounded-lg bg-muted p-3">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span className="text-sm text-muted-foreground">Thinking...</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </ScrollArea>

          <div className="border-t p-4">
            <div className="flex gap-2">
              <Textarea
                placeholder="Ask about treatment planning, coding, insurance..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                className="min-h-[60px] resize-none"
                data-testid="input-chat"
              />
              <Button
                onClick={handleSend}
                disabled={!input.trim() || sendMessage.isPending}
                size="icon"
                className="h-[60px] w-[60px]"
                data-testid="button-send"
              >
                {sendMessage.isPending ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <Send className="h-5 w-5" />
                )}
              </Button>
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Capabilities</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span>Treatment planning guidance</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span>CDT & ICD-10 coding help</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span>Medical necessity letters</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span>Insurance appeal drafting</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span>Prior authorization support</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span>Full arch implant expertise</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start"
                onClick={() =>
                  handleSuggestion(
                    "Generate a medical necessity letter for full arch dental implants"
                  )
                }
              >
                <FileText className="mr-2 h-4 w-4" />
                Medical Necessity Letter
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start"
                onClick={() =>
                  handleSuggestion(
                    "What CDT codes should I use for a full arch zirconia prosthesis with 6 implants?"
                  )
                }
              >
                <DollarSign className="mr-2 h-4 w-4" />
                Get CDT Codes
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start"
                onClick={() =>
                  handleSuggestion(
                    "Help me draft an appeal letter for a denied dental implant claim"
                  )
                }
              >
                <AlertCircle className="mr-2 h-4 w-4" />
                Draft Appeal Letter
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
