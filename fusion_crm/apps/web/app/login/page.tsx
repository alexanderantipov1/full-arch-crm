"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useLogin } from "@/lib/api/hooks/useAuth";
import { ApiError } from "@/lib/api/client";

const DEMO_EMAIL = "demo@fusion-dental.local";
const DEMO_PASSWORD = "demo";

export default function LoginPage() {
  const router = useRouter();
  const login = useLogin();
  const [email, setEmail] = useState(DEMO_EMAIL);
  const [password, setPassword] = useState(DEMO_PASSWORD);

  async function submit(creds: { email: string; password: string }) {
    try {
      await login.mutateAsync(creds);
      router.push("/dashboard");
    } catch {
      // error rendered below from mutation state
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    await submit({ email, password });
  }

  async function onDemoClick() {
    setEmail(DEMO_EMAIL);
    setPassword(DEMO_PASSWORD);
    await submit({ email: DEMO_EMAIL, password: DEMO_PASSWORD });
  }

  const errorMsg =
    login.error instanceof ApiError
      ? login.error.code === "AUTH_INVALID"
        ? "Wrong email or password."
        : login.error.message
      : login.error
        ? "Login failed."
        : null;

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Fusion CRM</CardTitle>
          <CardDescription>Sign in with your staff credentials.</CardDescription>
        </CardHeader>
        <form onSubmit={onSubmit}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>
            {errorMsg && (
              <p className="text-sm text-destructive">{errorMsg}</p>
            )}
            <p className="text-xs text-muted-foreground">
              Mock login: any email + password{" "}
              <code className="rounded bg-muted px-1">demo</code>.
            </p>
          </CardContent>
          <CardFooter className="flex flex-col gap-2">
            <Button
              type="submit"
              className="w-full"
              disabled={login.isPending}
            >
              {login.isPending ? "Signing in…" : "Sign in"}
            </Button>
            <Button
              type="button"
              variant="outline"
              className="w-full"
              onClick={onDemoClick}
              disabled={login.isPending}
            >
              <Sparkles className="h-4 w-4" />
              Sign in as demo user
            </Button>
          </CardFooter>
        </form>
      </Card>
    </main>
  );
}
