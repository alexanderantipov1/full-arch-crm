import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { ClipboardList, User, Heart, FileText, CheckCircle, AlertCircle, ArrowLeft, ArrowRight, Send } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage, FormDescription } from "@/components/ui/form";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";

const intakeFormSchema = z.object({
  firstName: z.string().min(1, "First name is required"),
  lastName: z.string().min(1, "Last name is required"),
  email: z.string().email("Valid email is required"),
  phone: z.string().min(10, "Phone number is required"),
  dateOfBirth: z.string().min(1, "Date of birth is required"),
  gender: z.string().min(1, "Gender is required"),
  address: z.string().min(1, "Address is required"),
  city: z.string().min(1, "City is required"),
  state: z.string().min(1, "State is required"),
  zipCode: z.string().min(5, "Zip code is required"),
  emergencyContact: z.string().optional(),
  emergencyPhone: z.string().optional(),
  referredBy: z.string().optional(),
  conditions: z.array(z.string()).default([]),
  allergies: z.string().optional(),
  medications: z.string().optional(),
  previousSurgeries: z.string().optional(),
  lastDentalVisit: z.string().optional(),
  dentalConcerns: z.string().optional(),
  missingTeeth: z.boolean().default(false),
  currentDentures: z.boolean().default(false),
  implantInterest: z.boolean().default(false),
  insuranceProvider: z.string().optional(),
  insuranceId: z.string().optional(),
  groupNumber: z.string().optional(),
  hipaaConsent: z.boolean().refine((val) => val === true, "HIPAA consent is required"),
  treatmentConsent: z.boolean().refine((val) => val === true, "Treatment consent is required"),
});

type IntakeFormData = z.infer<typeof intakeFormSchema>;

const medicalConditions = [
  "Heart Disease",
  "High Blood Pressure",
  "Diabetes",
  "Bleeding Disorders",
  "Thyroid Problems",
  "Osteoporosis",
  "Cancer",
  "HIV/AIDS",
  "Hepatitis",
  "Kidney Disease",
  "Liver Disease",
  "Asthma",
  "Sleep Apnea",
  "Stroke",
  "Epilepsy",
];

export default function IntakeFormPage() {
  const [currentStep, setCurrentStep] = useState(0);
  const [submitted, setSubmitted] = useState(false);
  const { toast } = useToast();

  const form = useForm<IntakeFormData>({
    resolver: zodResolver(intakeFormSchema),
    defaultValues: {
      firstName: "",
      lastName: "",
      email: "",
      phone: "",
      dateOfBirth: "",
      gender: "",
      address: "",
      city: "",
      state: "",
      zipCode: "",
      emergencyContact: "",
      emergencyPhone: "",
      referredBy: "",
      conditions: [],
      allergies: "",
      medications: "",
      previousSurgeries: "",
      lastDentalVisit: "",
      dentalConcerns: "",
      missingTeeth: false,
      currentDentures: false,
      implantInterest: false,
      insuranceProvider: "",
      insuranceId: "",
      groupNumber: "",
      hipaaConsent: false,
      treatmentConsent: false,
    },
  });

  const submitIntakeMutation = useMutation({
    mutationFn: async (data: IntakeFormData) => {
      const patientData = {
        firstName: data.firstName,
        lastName: data.lastName,
        email: data.email,
        phone: data.phone,
        dateOfBirth: data.dateOfBirth,
        gender: data.gender,
        address: data.address,
        city: data.city,
        state: data.state,
        zipCode: data.zipCode,
        emergencyContact: data.emergencyContact,
        emergencyPhone: data.emergencyPhone,
        referredBy: data.referredBy,
        status: "new",
      };
      return apiRequest("/api/patients", {
        method: "POST",
        body: JSON.stringify(patientData),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/patients"] });
      setSubmitted(true);
      toast({ title: "Intake form submitted successfully!" });
    },
    onError: () => {
      toast({ title: "Failed to submit intake form", variant: "destructive" });
    },
  });

  const steps = [
    { id: 0, title: "Personal Info", icon: User },
    { id: 1, title: "Medical History", icon: Heart },
    { id: 2, title: "Dental History", icon: FileText },
    { id: 3, title: "Insurance", icon: FileText },
    { id: 4, title: "Consent", icon: CheckCircle },
  ];

  const nextStep = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const prevStep = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const onSubmit = (data: IntakeFormData) => {
    submitIntakeMutation.mutate(data);
  };

  const progress = ((currentStep + 1) / steps.length) * 100;

  if (submitted) {
    return (
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-2xl mx-auto text-center py-12">
          <div className="mb-6">
            <div className="w-20 h-20 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle className="w-10 h-10 text-green-600" />
            </div>
          </div>
          <h1 className="text-3xl font-bold mb-4">Thank You!</h1>
          <p className="text-muted-foreground text-lg mb-6">
            Your intake form has been submitted successfully. Our team will review your information and contact you shortly to schedule your consultation.
          </p>
          <Button onClick={() => { setSubmitted(false); form.reset(); setCurrentStep(0); }}>
            Submit Another Form
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="text-center">
          <h1 className="text-3xl font-bold flex items-center justify-center gap-2" data-testid="text-page-title">
            <ClipboardList className="h-8 w-8 text-primary" />
            Patient Intake Form
          </h1>
          <p className="text-muted-foreground mt-2">Please complete all sections to help us serve you better</p>
        </div>

        {/* Progress */}
        <div className="space-y-4">
          <div className="flex justify-between text-sm">
            <span>Step {currentStep + 1} of {steps.length}</span>
            <span>{Math.round(progress)}% complete</span>
          </div>
          <Progress value={progress} className="h-2" />
          <div className="flex justify-between">
            {steps.map((step, index) => {
              const StepIcon = step.icon;
              const isCompleted = index < currentStep;
              const isCurrent = index === currentStep;
              return (
                <div
                  key={step.id}
                  className={`flex flex-col items-center gap-1 ${
                    isCurrent ? "text-primary" : isCompleted ? "text-green-600" : "text-muted-foreground"
                  }`}
                >
                  <div className={`p-2 rounded-full ${
                    isCurrent ? "bg-primary text-white" :
                    isCompleted ? "bg-green-600 text-white" : "bg-muted"
                  }`}>
                    {isCompleted ? <CheckCircle className="h-4 w-4" /> : <StepIcon className="h-4 w-4" />}
                  </div>
                  <span className="text-xs hidden md:block">{step.title}</span>
                </div>
              );
            })}
          </div>
        </div>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <Card>
              <CardContent className="pt-6">
                {/* Step 0: Personal Info */}
                {currentStep === 0 && (
                  <div className="space-y-4">
                    <h2 className="text-xl font-semibold mb-4">Personal Information</h2>
                    <div className="grid grid-cols-2 gap-4">
                      <FormField
                        control={form.control}
                        name="firstName"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>First Name *</FormLabel>
                            <FormControl>
                              <Input {...field} data-testid="input-firstname" />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="lastName"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Last Name *</FormLabel>
                            <FormControl>
                              <Input {...field} data-testid="input-lastname" />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <FormField
                        control={form.control}
                        name="email"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Email *</FormLabel>
                            <FormControl>
                              <Input type="email" {...field} data-testid="input-email" />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="phone"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Phone *</FormLabel>
                            <FormControl>
                              <Input {...field} data-testid="input-phone" />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <FormField
                        control={form.control}
                        name="dateOfBirth"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Date of Birth *</FormLabel>
                            <FormControl>
                              <Input type="date" {...field} data-testid="input-dob" />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="gender"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Gender *</FormLabel>
                            <Select onValueChange={field.onChange} value={field.value}>
                              <FormControl>
                                <SelectTrigger data-testid="select-gender">
                                  <SelectValue placeholder="Select gender" />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                <SelectItem value="male">Male</SelectItem>
                                <SelectItem value="female">Female</SelectItem>
                                <SelectItem value="other">Other</SelectItem>
                                <SelectItem value="prefer_not_to_say">Prefer not to say</SelectItem>
                              </SelectContent>
                            </Select>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                    <FormField
                      control={form.control}
                      name="address"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Address *</FormLabel>
                          <FormControl>
                            <Input {...field} data-testid="input-address" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <div className="grid grid-cols-3 gap-4">
                      <FormField
                        control={form.control}
                        name="city"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>City *</FormLabel>
                            <FormControl>
                              <Input {...field} data-testid="input-city" />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="state"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>State *</FormLabel>
                            <FormControl>
                              <Input {...field} data-testid="input-state" />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="zipCode"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Zip Code *</FormLabel>
                            <FormControl>
                              <Input {...field} data-testid="input-zip" />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <FormField
                        control={form.control}
                        name="emergencyContact"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Emergency Contact Name</FormLabel>
                            <FormControl>
                              <Input {...field} data-testid="input-emergency-name" />
                            </FormControl>
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="emergencyPhone"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Emergency Contact Phone</FormLabel>
                            <FormControl>
                              <Input {...field} data-testid="input-emergency-phone" />
                            </FormControl>
                          </FormItem>
                        )}
                      />
                    </div>
                    <FormField
                      control={form.control}
                      name="referredBy"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>How did you hear about us?</FormLabel>
                          <FormControl>
                            <Input placeholder="Referral source..." {...field} data-testid="input-referral" />
                          </FormControl>
                        </FormItem>
                      )}
                    />
                  </div>
                )}

                {/* Step 1: Medical History */}
                {currentStep === 1 && (
                  <div className="space-y-4">
                    <h2 className="text-xl font-semibold mb-4">Medical History</h2>
                    <div>
                      <Label className="mb-2 block">Do you have any of the following conditions?</Label>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-2">
                        {medicalConditions.map((condition) => (
                          <FormField
                            key={condition}
                            control={form.control}
                            name="conditions"
                            render={({ field }) => (
                              <FormItem className="flex items-center space-x-2">
                                <FormControl>
                                  <Checkbox
                                    checked={field.value?.includes(condition)}
                                    onCheckedChange={(checked) => {
                                      const updatedValue = checked
                                        ? [...(field.value || []), condition]
                                        : (field.value || []).filter((v) => v !== condition);
                                      field.onChange(updatedValue);
                                    }}
                                  />
                                </FormControl>
                                <FormLabel className="text-sm font-normal">{condition}</FormLabel>
                              </FormItem>
                            )}
                          />
                        ))}
                      </div>
                    </div>
                    <FormField
                      control={form.control}
                      name="allergies"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Allergies</FormLabel>
                          <FormControl>
                            <Textarea placeholder="List any allergies (medications, latex, etc.)" {...field} data-testid="input-allergies" />
                          </FormControl>
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="medications"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Current Medications</FormLabel>
                          <FormControl>
                            <Textarea placeholder="List all current medications and dosages" {...field} data-testid="input-medications" />
                          </FormControl>
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="previousSurgeries"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Previous Surgeries</FormLabel>
                          <FormControl>
                            <Textarea placeholder="List any previous surgeries and dates" {...field} data-testid="input-surgeries" />
                          </FormControl>
                        </FormItem>
                      )}
                    />
                  </div>
                )}

                {/* Step 2: Dental History */}
                {currentStep === 2 && (
                  <div className="space-y-4">
                    <h2 className="text-xl font-semibold mb-4">Dental History</h2>
                    <FormField
                      control={form.control}
                      name="lastDentalVisit"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>When was your last dental visit?</FormLabel>
                          <FormControl>
                            <Input type="date" {...field} data-testid="input-last-dental" />
                          </FormControl>
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="dentalConcerns"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>What are your main dental concerns?</FormLabel>
                          <FormControl>
                            <Textarea placeholder="Describe your dental concerns or what brought you here today..." {...field} data-testid="input-concerns" />
                          </FormControl>
                        </FormItem>
                      )}
                    />
                    <div className="space-y-3">
                      <FormField
                        control={form.control}
                        name="missingTeeth"
                        render={({ field }) => (
                          <FormItem className="flex items-center space-x-2">
                            <FormControl>
                              <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                            <FormLabel className="font-normal">I have missing teeth</FormLabel>
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="currentDentures"
                        render={({ field }) => (
                          <FormItem className="flex items-center space-x-2">
                            <FormControl>
                              <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                            <FormLabel className="font-normal">I currently wear dentures</FormLabel>
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="implantInterest"
                        render={({ field }) => (
                          <FormItem className="flex items-center space-x-2">
                            <FormControl>
                              <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                            <FormLabel className="font-normal">I am interested in dental implants (All-on-4/All-on-6)</FormLabel>
                          </FormItem>
                        )}
                      />
                    </div>
                  </div>
                )}

                {/* Step 3: Insurance */}
                {currentStep === 3 && (
                  <div className="space-y-4">
                    <h2 className="text-xl font-semibold mb-4">Insurance Information</h2>
                    <p className="text-muted-foreground text-sm mb-4">
                      If you have dental or medical insurance, please provide the following information. Skip this section if you don't have insurance.
                    </p>
                    <FormField
                      control={form.control}
                      name="insuranceProvider"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Insurance Provider</FormLabel>
                          <FormControl>
                            <Input placeholder="e.g., Delta Dental, Aetna, BlueCross" {...field} data-testid="input-insurance-provider" />
                          </FormControl>
                        </FormItem>
                      )}
                    />
                    <div className="grid grid-cols-2 gap-4">
                      <FormField
                        control={form.control}
                        name="insuranceId"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Member ID</FormLabel>
                            <FormControl>
                              <Input {...field} data-testid="input-insurance-id" />
                            </FormControl>
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="groupNumber"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Group Number</FormLabel>
                            <FormControl>
                              <Input {...field} data-testid="input-group-number" />
                            </FormControl>
                          </FormItem>
                        )}
                      />
                    </div>
                  </div>
                )}

                {/* Step 4: Consent */}
                {currentStep === 4 && (
                  <div className="space-y-6">
                    <h2 className="text-xl font-semibold mb-4">Consent & Acknowledgments</h2>
                    <div className="space-y-4 border p-4 rounded-lg">
                      <div className="flex items-start gap-3">
                        <AlertCircle className="h-5 w-5 text-amber-500 mt-0.5" />
                        <div>
                          <h3 className="font-medium">HIPAA Privacy Notice</h3>
                          <p className="text-sm text-muted-foreground">
                            I acknowledge that I have received and reviewed the Notice of Privacy Practices which describes how my health information may be used and disclosed. I understand my rights regarding my protected health information (PHI).
                          </p>
                        </div>
                      </div>
                      <FormField
                        control={form.control}
                        name="hipaaConsent"
                        render={({ field }) => (
                          <FormItem className="flex items-center space-x-2">
                            <FormControl>
                              <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                            <FormLabel className="font-medium">I acknowledge receipt of the HIPAA Privacy Notice *</FormLabel>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                    <div className="space-y-4 border p-4 rounded-lg">
                      <div className="flex items-start gap-3">
                        <FileText className="h-5 w-5 text-blue-500 mt-0.5" />
                        <div>
                          <h3 className="font-medium">Consent for Treatment</h3>
                          <p className="text-sm text-muted-foreground">
                            I consent to dental examination and treatment as recommended by the dental team. I understand that treatment plans, alternatives, and costs will be explained to me before any procedures.
                          </p>
                        </div>
                      </div>
                      <FormField
                        control={form.control}
                        name="treatmentConsent"
                        render={({ field }) => (
                          <FormItem className="flex items-center space-x-2">
                            <FormControl>
                              <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                            <FormLabel className="font-medium">I consent to dental examination and treatment *</FormLabel>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Navigation Buttons */}
            <div className="flex justify-between mt-6">
              <Button
                type="button"
                variant="outline"
                onClick={prevStep}
                disabled={currentStep === 0}
                data-testid="button-prev"
              >
                <ArrowLeft className="h-4 w-4 mr-2" />
                Previous
              </Button>
              {currentStep < steps.length - 1 ? (
                <Button type="button" onClick={nextStep} data-testid="button-next">
                  Next
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              ) : (
                <Button type="submit" disabled={submitIntakeMutation.isPending} data-testid="button-submit">
                  {submitIntakeMutation.isPending ? "Submitting..." : "Submit Form"}
                  <Send className="h-4 w-4 ml-2" />
                </Button>
              )}
            </div>
          </form>
        </Form>
      </div>
    </div>
  );
}
