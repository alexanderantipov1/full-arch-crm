"use client";

import * as React from "react";
import * as ToastPrimitive from "@radix-ui/react-toast";
import { X, CheckCircle2, AlertTriangle, Info } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Minimal toast system used by the outreach + multi-mailbox flows.
 *
 * Provider + viewport mount once at the root. `useToast()` exposes a stable
 * `toast({...})` function components call to emit a message. Each toast lives
 * for ~4s unless dismissed.
 */

type ToastVariant = "default" | "success" | "destructive";

interface ToastOptions {
  title: string;
  description?: string;
  variant?: ToastVariant;
  /** Override the default 4s dismissal. */
  durationMs?: number;
}

interface ToastInternal extends ToastOptions {
  id: string;
}

interface ToastContextValue {
  toast: (opts: ToastOptions) => void;
}

const ToastContext = React.createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = React.useState<ToastInternal[]>([]);

  const toast = React.useCallback((opts: ToastOptions) => {
    const id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `t-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setItems((prev) => [...prev, { ...opts, id }]);
  }, []);

  const dismiss = React.useCallback((id: string) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const ctx = React.useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={ctx}>
      <ToastPrimitive.Provider swipeDirection="right">
        {children}
        {items.map((t) => (
          <ToastPrimitive.Root
            key={t.id}
            duration={t.durationMs ?? 4000}
            onOpenChange={(open) => {
              if (!open) dismiss(t.id);
            }}
            className={cn(
              "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-80 data-[state=closed]:slide-out-to-right-full data-[state=open]:slide-in-from-top-full data-[state=open]:sm:slide-in-from-bottom-full",
              "pointer-events-auto relative flex w-full items-start gap-3 overflow-hidden rounded-md border p-4 pr-8 shadow-lg",
              t.variant === "destructive"
                ? "border-destructive bg-destructive text-destructive-foreground"
                : t.variant === "success"
                  ? "border-emerald-500 bg-background text-emerald-700 dark:text-emerald-300"
                  : "border bg-background text-foreground",
            )}
          >
            <div className="mt-0.5 shrink-0">
              {t.variant === "success" ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : t.variant === "destructive" ? (
                <AlertTriangle className="h-4 w-4" />
              ) : (
                <Info className="h-4 w-4" />
              )}
            </div>
            <div className="min-w-0 flex-1 space-y-1">
              <ToastPrimitive.Title className="text-sm font-semibold">
                {t.title}
              </ToastPrimitive.Title>
              {t.description ? (
                <ToastPrimitive.Description className="text-sm opacity-90">
                  {t.description}
                </ToastPrimitive.Description>
              ) : null}
            </div>
            <ToastPrimitive.Close
              className="absolute right-2 top-2 rounded-md p-1 text-current opacity-60 transition-opacity hover:opacity-100"
              aria-label="Dismiss"
            >
              <X className="h-3.5 w-3.5" />
            </ToastPrimitive.Close>
          </ToastPrimitive.Root>
        ))}
        <ToastPrimitive.Viewport className="fixed bottom-0 right-0 z-[100] flex max-h-screen w-full max-w-sm flex-col gap-2 p-4 outline-none" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = React.useContext(ToastContext);
  if (!ctx) {
    // Fall back to a noop so a missing provider doesn't crash the page —
    // it's better to silently drop a toast than to throw mid-render. Still
    // helpful in tests where ToastProvider isn't mounted.
    return {
      toast: () => {
        /* noop */
      },
    };
  }
  return ctx;
}
