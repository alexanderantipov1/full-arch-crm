"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { MockProvider } from "@/lib/msw/init";
import { VersionWatcher } from "@/components/system/VersionWatcher";
import { ToastProvider } from "@/components/ui/toast";

export function AppProviders({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            retry: false,
          },
        },
      }),
  );

  return (
    <MockProvider>
      <QueryClientProvider client={client}>
        <ToastProvider>
          <VersionWatcher />
          {children}
        </ToastProvider>
      </QueryClientProvider>
    </MockProvider>
  );
}
