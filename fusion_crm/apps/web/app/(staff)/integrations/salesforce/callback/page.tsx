"use client";

import { useEffect } from "react";
import { Loader2 } from "lucide-react";

export default function SalesforceCallbackPage() {
  useEffect(() => {
    window.location.replace(
      `/api/integrations/salesforce/callback${window.location.search}`,
    );
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center">
      <div className="flex items-center gap-3 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Finishing Salesforce sign-in...
      </div>
    </main>
  );
}
