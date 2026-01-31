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
import { useToast } from "@/hooks/use-toast";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { 
  Star, Plus, Video, Camera, MessageSquare, 
  CheckCircle, Clock, ThumbsUp
} from "lucide-react";
import type { Testimonial, Patient } from "@shared/schema";

const testimonialFormSchema = z.object({
  patientId: z.number().min(1, "Patient is required"),
  testimonialType: z.string().min(1, "Type is required"),
  rating: z.number().min(1).max(5),
  content: z.string().optional(),
  videoUrl: z.string().optional(),
});

type TestimonialFormData = z.infer<typeof testimonialFormSchema>;

const testimonialTypes = [
  { value: "written", label: "Written Review", icon: MessageSquare },
  { value: "video", label: "Video Testimonial", icon: Video },
  { value: "photo_review", label: "Photo + Review", icon: Camera },
  { value: "google_review", label: "Google Review", icon: Star },
];

export default function TestimonialsPage() {
  const { toast } = useToast();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  const { data: testimonials = [], isLoading } = useQuery<Testimonial[]>({
    queryKey: ["/api/testimonials"],
  });

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const form = useForm<TestimonialFormData>({
    resolver: zodResolver(testimonialFormSchema),
    defaultValues: {
      patientId: 0,
      testimonialType: "",
      rating: 5,
      content: "",
      videoUrl: "",
    },
  });

  const createTestimonialMutation = useMutation({
    mutationFn: async (data: TestimonialFormData) => {
      const res = await apiRequest("POST", "/api/testimonials", {
        ...data,
        consentToPublish: false,
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/testimonials"] });
      setIsAddDialogOpen(false);
      form.reset();
      toast({ title: "Testimonial Added", description: "Review has been submitted" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    },
  });

  const updateTestimonialMutation = useMutation({
    mutationFn: async ({ id, updates }: { id: number; updates: Record<string, unknown> }) => {
      const res = await apiRequest("PATCH", `/api/testimonials/${id}`, updates);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/testimonials"] });
      toast({ title: "Updated", description: "Testimonial status updated" });
    },
  });

  const onSubmit = (data: TestimonialFormData) => {
    createTestimonialMutation.mutate(data);
  };

  const getPatientName = (patientId: number | null) => {
    if (!patientId) return "Unknown";
    const patient = patients.find(p => p.id === patientId);
    return patient ? `${patient.firstName} ${patient.lastName}` : "Unknown";
  };

  const approveTestimonial = (id: number) => {
    updateTestimonialMutation.mutate({ 
      id, 
      updates: { consentToPublish: true, publishedAt: new Date() } 
    });
  };

  const renderStars = (rating: number) => {
    return (
      <div className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((star) => (
          <Star 
            key={star} 
            className={`w-4 h-4 ${star <= rating ? "fill-yellow-400 text-yellow-400" : "text-gray-300"}`} 
          />
        ))}
      </div>
    );
  };

  const pendingCount = testimonials.filter(t => !t.consentToPublish).length;
  const approvedCount = testimonials.filter(t => t.consentToPublish).length;
  const videoCount = testimonials.filter(t => t.testimonialType === "video").length;
  const avgRating = testimonials.length > 0 
    ? (testimonials.reduce((sum, t) => sum + (t.rating || 0), 0) / testimonials.length).toFixed(1)
    : "0";

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" data-testid="text-page-title">Testimonials & Reviews</h1>
          <p className="text-muted-foreground">Collect and manage patient testimonials</p>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="button-add-testimonial">
              <Plus className="w-4 h-4 mr-2" />
              Add Testimonial
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Add Testimonial</DialogTitle>
              <DialogDescription>Record a new patient testimonial</DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
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
                <div className="grid grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="testimonialType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Type</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-type">
                              <SelectValue placeholder="Select type" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {testimonialTypes.map((type) => (
                              <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="rating"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Rating</FormLabel>
                        <Select onValueChange={(v) => field.onChange(parseInt(v))} value={field.value.toString()}>
                          <FormControl>
                            <SelectTrigger data-testid="select-rating">
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {[5, 4, 3, 2, 1].map((rating) => (
                              <SelectItem key={rating} value={rating.toString()}>
                                {rating} Stars
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
                  name="content"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Review Content</FormLabel>
                      <FormControl>
                        <Textarea {...field} placeholder="Patient's testimonial..." data-testid="input-content" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="videoUrl"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Video URL (Optional)</FormLabel>
                      <FormControl>
                        <Input {...field} placeholder="https://..." data-testid="input-video" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createTestimonialMutation.isPending} data-testid="button-submit">
                    {createTestimonialMutation.isPending ? "Adding..." : "Add Testimonial"}
                  </Button>
                </div>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Average Rating</CardTitle>
            <Star className="h-4 w-4 text-yellow-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-avg-rating">{avgRating}</div>
            <p className="text-xs text-muted-foreground">Out of 5 stars</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Pending Review</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600" data-testid="stat-pending">{pendingCount}</div>
            <p className="text-xs text-muted-foreground">Awaiting approval</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Approved</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600" data-testid="stat-approved">{approvedCount}</div>
            <p className="text-xs text-muted-foreground">Published reviews</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Video Testimonials</CardTitle>
            <Video className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-videos">{videoCount}</div>
            <p className="text-xs text-muted-foreground">Video reviews</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Patient Testimonials</CardTitle>
          <CardDescription>Reviews and feedback from patients</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground text-center py-4">Loading...</p>
          ) : testimonials.length === 0 ? (
            <div className="text-center py-12">
              <Star className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No Testimonials Yet</h3>
              <p className="text-muted-foreground mb-4">Start collecting patient reviews</p>
              <Button onClick={() => setIsAddDialogOpen(true)} data-testid="button-add-first">
                <Plus className="w-4 h-4 mr-2" />
                Add Testimonial
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {testimonials.map((testimonial) => (
                <Card key={testimonial.id} className="relative" data-testid={`testimonial-${testimonial.id}`}>
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-lg">{getPatientName(testimonial.patientId)}</CardTitle>
                        <div className="flex items-center gap-2 mt-1">
                          {renderStars(testimonial.rating || 5)}
                          <Badge variant="outline">
                            {testimonialTypes.find(t => t.value === testimonial.testimonialType)?.label || testimonial.testimonialType}
                          </Badge>
                        </div>
                      </div>
                      <Badge className={testimonial.consentToPublish ? "bg-green-100 text-green-800" : "bg-orange-100 text-orange-800"}>
                        {testimonial.consentToPublish ? "Published" : "Pending"}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {testimonial.content && (
                      <p className="text-sm text-muted-foreground mb-3">"{testimonial.content}"</p>
                    )}
                    {testimonial.videoUrl && (
                      <div className="flex items-center gap-2 mb-3">
                        <Video className="w-4 h-4" />
                        <a href={testimonial.videoUrl} className="text-sm text-blue-600 hover:underline" target="_blank" rel="noopener noreferrer">
                          View Video
                        </a>
                      </div>
                    )}
                    {!testimonial.consentToPublish && (
                      <Button 
                        size="sm" 
                        onClick={() => approveTestimonial(testimonial.id)}
                        data-testid={`approve-${testimonial.id}`}
                      >
                        <ThumbsUp className="w-4 h-4 mr-1" />
                        Approve
                      </Button>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
