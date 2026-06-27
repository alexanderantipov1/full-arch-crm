"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import { useSession } from "@/lib/api/hooks/useAuth";
import { AppShell } from "@/components/layout/AppShell";
import { Skeleton } from "@/components/ui/skeleton";

export default function StaffLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const session = useSession();

  useEffect(() => {
    if (
      session.error instanceof ApiError &&
      session.error.code === "UNAUTHENTICATED"
    ) {
      router.replace("/login");
    }
  }, [session.error, router]);

  if (session.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Skeleton className="h-8 w-48" />
      </div>
    );
  }

  if (!session.data) return null;

  return <AppShell>{children}</AppShell>;
}
