import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { queryClient, apiRequest } from "@/lib/queryClient";
import { useAuth } from "@/hooks/use-auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import {
  Mail,
  Send,
  Plus,
  Circle,
  Clock,
  AlertTriangle,
  ArrowLeft,
  Inbox,
  SendHorizonal,
} from "lucide-react";
import type { InternalMessage, User } from "@shared/schema";

function formatTime(date: string | Date) {
  const d = new Date(date);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString();
}

function priorityColor(priority: string | null) {
  switch (priority) {
    case "urgent": return "destructive";
    case "high": return "default";
    default: return "secondary";
  }
}

function ComposeDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { toast } = useToast();
  const [recipientId, setRecipientId] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [priority, setPriority] = useState("normal");
  const [category, setCategory] = useState("general");

  const { data: allUsers = [] } = useQuery<User[]>({
    queryKey: ["/api/users/all"],
  });

  const sendMutation = useMutation({
    mutationFn: async (data: any) => {
      const res = await apiRequest("POST", "/api/messages", data);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/messages/sent"] });
      queryClient.invalidateQueries({ queryKey: ["/api/messages/inbox"] });
      queryClient.invalidateQueries({ queryKey: ["/api/messages/unread-count"] });
      toast({ title: "Message sent" });
      setRecipientId("");
      setSubject("");
      setBody("");
      setPriority("normal");
      setCategory("general");
      onOpenChange(false);
    },
    onError: () => {
      toast({ title: "Failed to send message", variant: "destructive" });
    },
  });

  const selectedUser = allUsers.find((u) => u.id === recipientId);
  const recipientName = selectedUser
    ? `${selectedUser.firstName || ""} ${selectedUser.lastName || ""}`.trim() || selectedUser.email || "Unknown"
    : "";

  const handleSend = () => {
    if (!recipientId || !subject || !body) {
      toast({ title: "Please fill in all fields", variant: "destructive" });
      return;
    }
    sendMutation.mutate({
      recipientId,
      recipientName,
      subject,
      body,
      priority,
      category,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>New Message</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="space-y-2">
            <label className="text-sm font-medium text-muted-foreground">To</label>
            <Select value={recipientId} onValueChange={setRecipientId}>
              <SelectTrigger data-testid="select-recipient">
                <SelectValue placeholder="Select team member" />
              </SelectTrigger>
              <SelectContent>
                {allUsers.map((u) => (
                  <SelectItem key={u.id} value={u.id} data-testid={`recipient-${u.id}`}>
                    {`${u.firstName || ""} ${u.lastName || ""}`.trim() || u.email || u.id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex gap-3 flex-wrap">
            <div className="flex-1 min-w-[150px] space-y-2">
              <label className="text-sm font-medium text-muted-foreground">Priority</label>
              <Select value={priority} onValueChange={setPriority}>
                <SelectTrigger data-testid="select-priority">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="normal">Normal</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="urgent">Urgent</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex-1 min-w-[150px] space-y-2">
              <label className="text-sm font-medium text-muted-foreground">Category</label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger data-testid="select-category">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="general">General</SelectItem>
                  <SelectItem value="patient">Patient Related</SelectItem>
                  <SelectItem value="billing">Billing</SelectItem>
                  <SelectItem value="clinical">Clinical</SelectItem>
                  <SelectItem value="scheduling">Scheduling</SelectItem>
                  <SelectItem value="surgery">Surgery</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-muted-foreground">Subject</label>
            <Input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Message subject"
              data-testid="input-subject"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-muted-foreground">Message</label>
            <Textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Type your message..."
              className="min-h-[120px]"
              data-testid="input-body"
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="button-cancel-message">
              Cancel
            </Button>
            <Button onClick={handleSend} disabled={sendMutation.isPending} data-testid="button-send-message">
              <Send className="h-4 w-4 mr-2" />
              {sendMutation.isPending ? "Sending..." : "Send"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function MessageRow({
  message,
  showSender,
  onClick,
}: {
  message: InternalMessage;
  showSender: boolean;
  onClick: () => void;
}) {
  return (
    <div
      className={`flex items-start gap-3 p-3 rounded-md cursor-pointer hover-elevate ${!message.isRead && showSender ? "bg-primary/5" : ""}`}
      onClick={onClick}
      data-testid={`message-row-${message.id}`}
    >
      <div className="pt-1">
        {!message.isRead && showSender ? (
          <Circle className="h-2.5 w-2.5 fill-primary text-primary" />
        ) : (
          <Circle className="h-2.5 w-2.5 text-transparent" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-sm truncate ${!message.isRead && showSender ? "font-semibold" : "font-medium"}`}>
            {showSender ? message.senderName : message.recipientName}
          </span>
          {message.priority === "urgent" && (
            <Badge variant={priorityColor(message.priority)} className="text-xs">
              <AlertTriangle className="h-3 w-3 mr-1" />
              Urgent
            </Badge>
          )}
          {message.priority === "high" && (
            <Badge variant={priorityColor(message.priority)} className="text-xs">
              High
            </Badge>
          )}
          {message.category && message.category !== "general" && (
            <Badge variant="outline" className="text-xs capitalize">
              {message.category}
            </Badge>
          )}
        </div>
        <p className={`text-sm truncate ${!message.isRead && showSender ? "font-medium" : "text-muted-foreground"}`}>
          {message.subject}
        </p>
        <p className="text-xs text-muted-foreground truncate mt-0.5">{message.body}</p>
      </div>
      <div className="flex items-center gap-1 text-xs text-muted-foreground whitespace-nowrap">
        <Clock className="h-3 w-3" />
        {formatTime(message.createdAt)}
      </div>
    </div>
  );
}

function MessageDetail({
  message,
  onBack,
  isSent,
}: {
  message: InternalMessage;
  onBack: () => void;
  isSent: boolean;
}) {
  const markedRef = useRef(false);
  const markReadMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("PATCH", `/api/messages/${message.id}/read`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/messages/inbox"] });
      queryClient.invalidateQueries({ queryKey: ["/api/messages/unread-count"] });
    },
  });

  useEffect(() => {
    if (!message.isRead && !isSent && !markedRef.current) {
      markedRef.current = true;
      markReadMutation.mutate();
    }
  }, [message.id]);

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" onClick={onBack} data-testid="button-back-to-list">
        <ArrowLeft className="h-4 w-4 mr-1" />
        Back
      </Button>
      <Card>
        <CardHeader>
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <CardTitle className="text-lg">{message.subject}</CardTitle>
              {message.priority && message.priority !== "normal" && (
                <Badge variant={priorityColor(message.priority)} className="capitalize">
                  {message.priority}
                </Badge>
              )}
              {message.category && message.category !== "general" && (
                <Badge variant="outline" className="capitalize">
                  {message.category}
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-4 text-sm text-muted-foreground flex-wrap">
              <span>
                {isSent ? "To" : "From"}: <strong className="text-foreground">{isSent ? message.recipientName : message.senderName}</strong>
              </span>
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {new Date(message.createdAt).toLocaleString()}
              </span>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="whitespace-pre-wrap text-sm" data-testid="message-body-detail">
            {message.body}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function MessagesPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState("inbox");
  const [selectedMessage, setSelectedMessage] = useState<InternalMessage | null>(null);
  const [composeOpen, setComposeOpen] = useState(false);

  const { data: inboxMessages = [], isLoading: inboxLoading } = useQuery<InternalMessage[]>({
    queryKey: ["/api/messages/inbox"],
  });

  const { data: sentMessages = [], isLoading: sentLoading } = useQuery<InternalMessage[]>({
    queryKey: ["/api/messages/sent"],
  });

  const { data: unreadData } = useQuery<{ count: number }>({
    queryKey: ["/api/messages/unread-count"],
  });

  const unreadCount = unreadData?.count || 0;

  if (selectedMessage) {
    return (
      <div data-testid="messages-page">
        <MessageDetail
          message={selectedMessage}
          onBack={() => setSelectedMessage(null)}
          isSent={activeTab === "sent"}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="messages-page">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Messages</h1>
          <p className="text-muted-foreground">Internal team communication</p>
        </div>
        <Button onClick={() => setComposeOpen(true)} data-testid="button-compose">
          <Plus className="h-4 w-4 mr-2" />
          New Message
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10">
              <Inbox className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-bold" data-testid="text-inbox-count">{inboxMessages.length}</p>
              <p className="text-xs text-muted-foreground">Inbox Messages</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-blue-500/10">
              <Mail className="h-5 w-5 text-blue-500" />
            </div>
            <div>
              <p className="text-2xl font-bold" data-testid="text-unread-count">{unreadCount}</p>
              <p className="text-xs text-muted-foreground">Unread</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-green-500/10">
              <SendHorizonal className="h-5 w-5 text-green-500" />
            </div>
            <div>
              <p className="text-2xl font-bold" data-testid="text-sent-count">{sentMessages.length}</p>
              <p className="text-xs text-muted-foreground">Sent</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="pt-6">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="inbox" data-testid="tab-inbox">
                <Inbox className="h-4 w-4 mr-1.5" />
                Inbox
                {unreadCount > 0 && (
                  <Badge variant="destructive" className="ml-1.5 text-xs">
                    {unreadCount}
                  </Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="sent" data-testid="tab-sent">
                <SendHorizonal className="h-4 w-4 mr-1.5" />
                Sent
              </TabsTrigger>
            </TabsList>

            <TabsContent value="inbox" className="mt-4">
              {inboxLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : inboxMessages.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Inbox className="h-12 w-12 mx-auto mb-3 opacity-30" />
                  <p className="font-medium">No messages yet</p>
                  <p className="text-sm">Your inbox is empty</p>
                </div>
              ) : (
                <div className="space-y-1">
                  {inboxMessages.map((msg) => (
                    <MessageRow
                      key={msg.id}
                      message={msg}
                      showSender={true}
                      onClick={() => {
                        setSelectedMessage(msg);
                      }}
                    />
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="sent" className="mt-4">
              {sentLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : sentMessages.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <SendHorizonal className="h-12 w-12 mx-auto mb-3 opacity-30" />
                  <p className="font-medium">No sent messages</p>
                  <p className="text-sm">Messages you send will appear here</p>
                </div>
              ) : (
                <div className="space-y-1">
                  {sentMessages.map((msg) => (
                    <MessageRow
                      key={msg.id}
                      message={msg}
                      showSender={false}
                      onClick={() => {
                        setSelectedMessage(msg);
                      }}
                    />
                  ))}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <ComposeDialog open={composeOpen} onOpenChange={setComposeOpen} />
    </div>
  );
}
