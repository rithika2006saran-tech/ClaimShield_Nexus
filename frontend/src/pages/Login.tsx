import { useState } from "react";
import { ShieldCheck, LogIn, Lock } from "lucide-react";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";

export default function Login({ onLogin }: { onLogin: () => void }) {
  const [email, setEmail] = useState("rithika.2006saran@gmail.com");
  const [password, setPassword] = useState("password123");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (error) throw error;
      onLogin();
    } catch (err: any) {
      setError(err.message || "Failed to sign in");
    } finally {
      setLoading(false);
    }
  };

  const handleSignUp = async (e: React.MouseEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const { error } = await supabase.auth.signUp({
        email,
        password,
      });
      if (error) throw error;
      setError("Sign up successful! If email confirmation is required, please check your email. Otherwise, you can now sign in.");
    } catch (err: any) {
      setError(err.message || "Failed to sign up");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background/50 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/10 via-background to-background p-4">
      <div className="w-full max-w-md space-y-8 rounded-xl border border-border/50 bg-card p-10 shadow-2xl backdrop-blur-sm">
        <div className="flex flex-col items-center justify-center space-y-2 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-inner">
            <ShieldCheck className="h-8 w-8" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground mt-4">ClaimShield <span className="text-primary">Nexus</span></h1>
          <p className="text-sm text-muted-foreground">FWA Investigation Intelligence Authentication</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-6 mt-8">
          {error && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive text-center">
              {error}
            </div>
          )}

          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full rounded-md border border-input bg-background/50 p-2.5 text-sm outline-none focus:ring-2 focus:ring-primary/50 transition-all"
                placeholder="lead@example.com"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Password</label>
              <div className="relative">
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full rounded-md border border-input bg-background/50 p-2.5 text-sm outline-none focus:ring-2 focus:ring-primary/50 transition-all"
                  placeholder="••••••••"
                />
                <Lock className="absolute right-3 top-2.5 h-4 w-4 text-muted-foreground/50" />
              </div>
            </div>
          </div>

          <div className="flex gap-2">
            <Button type="submit" className="w-full h-10 text-sm font-semibold" disabled={loading}>
              {loading ? "..." : <><LogIn className="mr-2 h-4 w-4" /> Sign In</>}
            </Button>
            <Button type="button" variant="outline" className="w-full h-10 text-sm font-semibold" disabled={loading} onClick={handleSignUp}>
              {loading ? "..." : "Create Account"}
            </Button>
          </div>

          <div className="text-center pt-4">
            <div className="text-xs text-muted-foreground space-y-1">
              <p>Demo Accounts:</p>
              <p><code>rithika.2006saran@gmail.com</code> (Lead)</p>
              <p><code>sarveshsivasankaran@gmail.com</code> (Reviewer)</p>
              <p><code>sabnish776@gmail.com</code> (Analyst)</p>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
