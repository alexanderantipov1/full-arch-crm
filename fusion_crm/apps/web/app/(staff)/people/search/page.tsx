"use client";

import { useState } from "react";
import { PeopleSearchBar } from "@/components/people/PeopleSearchBar";
import { PeopleSearchResults } from "@/components/people/PeopleSearchResults";
import { usePeopleSearch } from "@/lib/api/hooks/usePeopleSearch";
import type { PeopleSearchInput } from "@/lib/api/schemas/peopleSearch";

/**
 * Reception desk lookup — given a phone or email, surface every person we
 * already know about across Salesforce, CareStack, and the local
 * `identity.person` registry. Read-only in Phase 1; the "Link" action is
 * disabled until backend ENG-120 ships the merge endpoint.
 */
export default function PeopleSearchPage() {
  const [input, setInput] = useState<PeopleSearchInput>({});
  const query = usePeopleSearch(input);
  const hasQuery = Boolean(input.phone || input.email);

  return (
    <div className="space-y-6 p-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          Find a person
        </h1>
        <p className="text-sm text-muted-foreground">
          Type the caller&apos;s phone or email — we&apos;ll check Salesforce,
          CareStack, and our existing CRM in parallel.
        </p>
      </header>

      <PeopleSearchBar value={input} onChange={setInput} autoFocus />

      <PeopleSearchResults
        data={query.data}
        isLoading={query.isFetching && hasQuery}
        isError={query.isError}
        error={query.error}
        hasQuery={hasQuery}
      />
    </div>
  );
}
