import { ArrowLeft, Loader2, LogIn, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { Brand } from "@/components/layout/brand";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/use-auth";
import { getApiErrorMessage } from "@/lib/api-error";

export default function Login() {
  const { user, loading, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (!loading && user) {
    return <Navigate to="/admin/live" replace />;
  }

  const requestedPath = location.state?.from;
  const destination =
    typeof requestedPath === "string" && requestedPath.startsWith("/admin")
      ? requestedPath
      : "/admin/live";

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      await login(email.trim(), password);
      navigate(destination, { replace: true });
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not sign in"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-4 py-10 sm:px-6">
      <div className="mb-8 flex justify-center">
        <Brand />
      </div>

      <Card className="overflow-hidden">
        <div className="bg-linear-to-br from-primary/10 via-card to-chart-2/10 px-6 pt-6 pb-4">
          <span className="grid size-11 place-items-center rounded-2xl bg-primary/10 text-primary">
            <ShieldCheck className="size-5" />
          </span>
          <CardHeader className="mt-3 px-0 pb-0">
            <CardTitle>Staff sign in</CardTitle>
            <CardDescription>
              Use your clinic admin account to open the call log,
              appointments, and clinic settings.
            </CardDescription>
          </CardHeader>
        </div>

        <CardContent className="pt-5">
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertTitle>Sign in failed</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>

            <Button
              type="submit"
              size="lg"
              className="w-full"
              disabled={submitting}
            >
              {submitting ? (
                <Loader2 className="animate-spin" />
              ) : (
                <LogIn />
              )}
              {submitting ? "Signing in..." : "Sign in"}
            </Button>
          </form>

          <Button asChild variant="ghost" size="sm" className="mt-4 w-full">
            <Link to="/">
              <ArrowLeft />
              Back to patient call page
            </Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
