"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/client";
import {
  PeopleSearchOutSchema,
  type PeopleSearchInput,
  type PeopleSearchOut,
} from "@/lib/api/schemas/peopleSearch";

const DEBOUNCE_MS = 400;

/** Internal: debounce a value by `delay` ms. */
function useDebounced<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

/** Trim and drop empty fields so the queryKey stays stable. */
function normaliseInput(input: PeopleSearchInput): PeopleSearchInput {
  const out: PeopleSearchInput = {};
  const phone = input.phone?.trim();
  const email = input.email?.trim();
  if (phone) out.phone = phone;
  if (email) out.email = email;
  return out;
}

function buildSearchUrl(input: PeopleSearchInput): string {
  const params = new URLSearchParams();
  if (input.phone) params.set("phone", input.phone);
  if (input.email) params.set("email", input.email);
  const qs = params.toString();
  return qs ? `/people/search/live?${qs}` : "/people/search/live";
}

/**
 * Unified people search hook. Debounces inputs by 400ms and disables the
 * query if both `phone` and `email` are empty. Result is Zod-validated —
 * a contract drift will throw at parse time.
 */
export function usePeopleSearch(input: PeopleSearchInput) {
  const debounced = useDebounced(normaliseInput(input), DEBOUNCE_MS);
  const enabled = Boolean(debounced.phone || debounced.email);

  return useQuery<PeopleSearchOut>({
    enabled,
    queryKey: ["people-search", debounced.phone ?? "", debounced.email ?? ""],
    queryFn: async (): Promise<PeopleSearchOut> => {
      const res = await fetch(buildSearchUrl(debounced), {
        credentials: "include",
      });
      const text = await res.text();
      const raw: unknown = text ? JSON.parse(text) : null;
      if (!res.ok) {
        throw new ApiError(
          "UNKNOWN",
          `Request failed with status ${res.status}`,
          res.status,
        );
      }
      return PeopleSearchOutSchema.parse(raw);
    },
    staleTime: 30_000,
    gcTime: 5 * 60_000,
  });
}
