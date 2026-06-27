"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  type AccessList,
  AccessListSchema,
  type LoginRequest,
  LoginResponseSchema,
  type StaffSession,
  StaffSessionSchema,
} from "@/lib/api/schemas";

const SESSION_KEY = ["auth", "session"] as const;
const STORAGE_KEY = "fusion.staff_session";

function readStoredSession(): StaffSession | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = StaffSessionSchema.parse(JSON.parse(raw));
    if (new Date(parsed.expires_at).getTime() <= Date.now()) {
      window.localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

function writeStoredSession(session: StaffSession): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

function clearStoredSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
}

export function useSession() {
  return useQuery({
    queryKey: SESSION_KEY,
    queryFn: async (): Promise<StaffSession> => {
      const stored = readStoredSession();
      if (stored) return stored;
      const raw = await api.get<unknown>("/auth/session");
      const session = StaffSessionSchema.parse(
        (raw as { session: unknown }).session,
      );
      writeStoredSession(session);
      return session;
    },
    staleTime: 60_000,
  });
}

export function useAccessList() {
  return useQuery({
    queryKey: ["auth", "access-list"] as const,
    queryFn: async (): Promise<AccessList> => {
      const raw = await api.get<unknown>("/auth/access-list");
      return AccessListSchema.parse(raw);
    },
    staleTime: 60_000,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: LoginRequest) => {
      const raw = await api.post<unknown>("/auth/login", input);
      return LoginResponseSchema.parse(raw).session;
    },
    onSuccess: (session) => {
      writeStoredSession(session);
      qc.setQueryData(SESSION_KEY, session);
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post("/auth/logout").catch(() => null),
    onSuccess: () => {
      clearStoredSession();
      qc.removeQueries({ queryKey: SESSION_KEY });
    },
  });
}
