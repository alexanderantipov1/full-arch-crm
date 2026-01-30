import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { 
  GraduationCap, 
  BookOpen,
  Video,
  CheckCircle2,
  Circle,
  Play,
  Award,
  Clock,
  TrendingUp,
  Users,
  FileText,
  Stethoscope,
  DollarSign,
  Shield
} from "lucide-react";

interface TrainingModule {
  id: string;
  title: string;
  description: string;
  category: string;
  duration: string;
  lessons: TrainingLesson[];
  completed: boolean;
  progress: number;
}

interface TrainingLesson {
  id: string;
  title: string;
  duration: string;
  type: "video" | "interactive" | "quiz";
  completed: boolean;
}

interface TrainingStats {
  totalModules: number;
  completedModules: number;
  totalLessons: number;
  completedLessons: number;
  overallProgress: number;
  certificationsEarned: number;
  hoursCompleted: number;
}

const trainingModules: TrainingModule[] = [
  {
    id: "billing-basics",
    title: "Medical Billing Fundamentals",
    description: "Learn the basics of dental implant medical billing",
    category: "Billing",
    duration: "2 hours",
    completed: false,
    progress: 0,
    lessons: [
      { id: "bb-1", title: "Introduction to Medical vs Dental Billing", duration: "15 min", type: "video", completed: false },
      { id: "bb-2", title: "Understanding CDT and CPT Codes", duration: "20 min", type: "video", completed: false },
      { id: "bb-3", title: "ICD-10 Diagnosis Coding Basics", duration: "25 min", type: "video", completed: false },
      { id: "bb-4", title: "Interactive: Code Mapping Exercise", duration: "30 min", type: "interactive", completed: false },
      { id: "bb-5", title: "Quiz: Billing Fundamentals", duration: "15 min", type: "quiz", completed: false },
    ]
  },
  {
    id: "cross-coding",
    title: "CDT to CPT Cross-Coding Mastery",
    description: "Master the art of cross-coding for maximum reimbursement",
    category: "Coding",
    duration: "3 hours",
    completed: false,
    progress: 0,
    lessons: [
      { id: "cc-1", title: "When to Use Medical vs Dental Codes", duration: "20 min", type: "video", completed: false },
      { id: "cc-2", title: "Full Arch Implant Cross-Coding", duration: "30 min", type: "video", completed: false },
      { id: "cc-3", title: "Bone Grafting Cross-Coding", duration: "25 min", type: "video", completed: false },
      { id: "cc-4", title: "Interactive: Cross-Code Practice Cases", duration: "45 min", type: "interactive", completed: false },
      { id: "cc-5", title: "Modifier Usage and Pitfalls", duration: "20 min", type: "video", completed: false },
      { id: "cc-6", title: "Quiz: Cross-Coding Certification", duration: "20 min", type: "quiz", completed: false },
    ]
  },
  {
    id: "prior-auth",
    title: "Prior Authorization Workflow",
    description: "Streamline prior authorizations for faster approvals",
    category: "Authorization",
    duration: "1.5 hours",
    completed: false,
    progress: 0,
    lessons: [
      { id: "pa-1", title: "Understanding Prior Auth Requirements", duration: "15 min", type: "video", completed: false },
      { id: "pa-2", title: "Document Assembly Best Practices", duration: "20 min", type: "video", completed: false },
      { id: "pa-3", title: "Using the ImplantBill AI Prior Auth Tool", duration: "25 min", type: "interactive", completed: false },
      { id: "pa-4", title: "Peer-to-Peer Review Preparation", duration: "20 min", type: "video", completed: false },
      { id: "pa-5", title: "Quiz: Prior Auth Process", duration: "10 min", type: "quiz", completed: false },
    ]
  },
  {
    id: "appeals",
    title: "Appeals & Denial Management",
    description: "Turn denials into approvals with effective appeals",
    category: "Appeals",
    duration: "2.5 hours",
    completed: false,
    progress: 0,
    lessons: [
      { id: "ap-1", title: "Understanding Denial Codes", duration: "20 min", type: "video", completed: false },
      { id: "ap-2", title: "Root Cause Analysis", duration: "25 min", type: "video", completed: false },
      { id: "ap-3", title: "Writing Effective Appeal Letters", duration: "30 min", type: "video", completed: false },
      { id: "ap-4", title: "Using the AI Appeals Engine", duration: "25 min", type: "interactive", completed: false },
      { id: "ap-5", title: "Escalation Strategies", duration: "20 min", type: "video", completed: false },
      { id: "ap-6", title: "Quiz: Appeals Mastery", duration: "15 min", type: "quiz", completed: false },
    ]
  },
  {
    id: "documentation",
    title: "Clinical Documentation Excellence",
    description: "Create documentation that gets claims approved",
    category: "Documentation",
    duration: "2 hours",
    completed: false,
    progress: 0,
    lessons: [
      { id: "doc-1", title: "Medical Necessity Documentation", duration: "25 min", type: "video", completed: false },
      { id: "doc-2", title: "Using the AI Documentation Engine", duration: "30 min", type: "interactive", completed: false },
      { id: "doc-3", title: "Operative Report Best Practices", duration: "20 min", type: "video", completed: false },
      { id: "doc-4", title: "Progress Notes That Support Claims", duration: "20 min", type: "video", completed: false },
      { id: "doc-5", title: "Quiz: Documentation Standards", duration: "15 min", type: "quiz", completed: false },
    ]
  }
];

export default function TrainingPage() {
  const { toast } = useToast();
  const [selectedModule, setSelectedModule] = useState<TrainingModule | null>(null);

  const { data: stats, isLoading: statsLoading } = useQuery<TrainingStats>({
    queryKey: ["/api/training/stats"]
  });

  const { data: progress } = useQuery<Record<string, boolean>>({
    queryKey: ["/api/training/progress"]
  });

  const completeLessonMutation = useMutation({
    mutationFn: async (data: { moduleId: string; lessonId: string }) => {
      const res = await apiRequest("POST", "/api/training/complete", data);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/training"] });
      toast({ title: "Lesson Completed", description: "Great job! Keep up the progress." });
    }
  });

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case "Billing": return DollarSign;
      case "Coding": return FileText;
      case "Authorization": return Shield;
      case "Appeals": return TrendingUp;
      case "Documentation": return Stethoscope;
      default: return BookOpen;
    }
  };

  const getLessonIcon = (type: string) => {
    switch (type) {
      case "video": return Video;
      case "interactive": return Play;
      case "quiz": return Award;
      default: return BookOpen;
    }
  };

  const enrichedModules = trainingModules.map(module => {
    const completedLessons = module.lessons.filter(l => progress?.[`${module.id}-${l.id}`]).length;
    return {
      ...module,
      progress: (completedLessons / module.lessons.length) * 100,
      completed: completedLessons === module.lessons.length,
      lessons: module.lessons.map(l => ({
        ...l,
        completed: progress?.[`${module.id}-${l.id}`] || false
      }))
    };
  });

  const overallProgress = stats?.overallProgress || 
    (enrichedModules.reduce((acc, m) => acc + m.progress, 0) / enrichedModules.length);

  return (
    <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(100vh-80px)]">
      <div>
        <h1 className="text-3xl font-bold" data-testid="text-page-title">Training Center</h1>
        <p className="text-muted-foreground">
          Interactive onboarding and staff training modules
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statsLoading ? (
          [...Array(4)].map((_, i) => <Skeleton key={i} className="h-28" />)
        ) : (
          <>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Overall Progress</p>
                    <p className="text-2xl font-bold" data-testid="text-progress">
                      {Math.round(overallProgress)}%
                    </p>
                    <Progress value={overallProgress} className="w-20 h-2 mt-2" />
                  </div>
                  <div className="p-2 bg-primary/10 rounded-full">
                    <TrendingUp className="h-5 w-5 text-primary" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Modules Completed</p>
                    <p className="text-2xl font-bold text-green-600" data-testid="text-completed">
                      {enrichedModules.filter(m => m.completed).length}/{enrichedModules.length}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Training modules</p>
                  </div>
                  <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-full">
                    <CheckCircle2 className="h-5 w-5 text-green-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Hours Completed</p>
                    <p className="text-2xl font-bold" data-testid="text-hours">
                      {stats?.hoursCompleted || 0}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Training time</p>
                  </div>
                  <div className="p-2 bg-muted rounded-full">
                    <Clock className="h-5 w-5 text-muted-foreground" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Certifications</p>
                    <p className="text-2xl font-bold text-yellow-600" data-testid="text-certs">
                      {stats?.certificationsEarned || 0}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Earned badges</p>
                  </div>
                  <div className="p-2 bg-yellow-100 dark:bg-yellow-900/30 rounded-full">
                    <Award className="h-5 w-5 text-yellow-600" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GraduationCap className="h-5 w-5" />
                Training Modules
              </CardTitle>
              <CardDescription>
                Complete these modules to master ImplantBill AI
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {enrichedModules.map((module) => {
                const CategoryIcon = getCategoryIcon(module.category);
                return (
                  <div
                    key={module.id}
                    className={`p-4 border rounded-lg cursor-pointer hover-elevate ${
                      selectedModule?.id === module.id ? "ring-2 ring-primary" : ""
                    }`}
                    onClick={() => setSelectedModule(module)}
                    data-testid={`module-${module.id}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <div className="p-2 bg-primary/10 rounded-lg">
                          <CategoryIcon className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="font-medium">{module.title}</h3>
                            {module.completed && (
                              <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                                <CheckCircle2 className="h-3 w-3 mr-1" />
                                Complete
                              </Badge>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground mt-1">{module.description}</p>
                          <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {module.duration}
                            </span>
                            <span>{module.lessons.length} lessons</span>
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-sm font-medium">{Math.round(module.progress)}%</span>
                        <Progress value={module.progress} className="w-20 h-2 mt-1" />
                      </div>
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </div>

        <div>
          {selectedModule ? (
            <Card>
              <CardHeader>
                <CardTitle>{selectedModule.title}</CardTitle>
                <CardDescription>{selectedModule.lessons.length} lessons • {selectedModule.duration}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {selectedModule.lessons.map((lesson, index) => {
                  const LessonIcon = getLessonIcon(lesson.type);
                  return (
                    <div
                      key={lesson.id}
                      className="flex items-center justify-between p-3 border rounded-lg"
                      data-testid={`lesson-${lesson.id}`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`p-1.5 rounded-full ${lesson.completed ? "bg-green-100 dark:bg-green-900/30" : "bg-muted"}`}>
                          {lesson.completed ? (
                            <CheckCircle2 className="h-4 w-4 text-green-600" />
                          ) : (
                            <Circle className="h-4 w-4 text-muted-foreground" />
                          )}
                        </div>
                        <div>
                          <p className="text-sm font-medium">{lesson.title}</p>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <LessonIcon className="h-3 w-3" />
                            <span>{lesson.type}</span>
                            <span>•</span>
                            <span>{lesson.duration}</span>
                          </div>
                        </div>
                      </div>
                      {!lesson.completed && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={(e) => {
                            e.stopPropagation();
                            completeLessonMutation.mutate({
                              moduleId: selectedModule.id,
                              lessonId: lesson.id
                            });
                          }}
                          data-testid={`button-start-${lesson.id}`}
                        >
                          <Play className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="pt-6">
                <div className="text-center py-8 text-muted-foreground">
                  <BookOpen className="h-12 w-12 mx-auto mb-2" />
                  <p>Select a module to view lessons</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
