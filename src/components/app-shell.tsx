import { useEffect, useState, type ReactNode } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import {
  Gauge,
  ListChecks,
  FileStack,
  History,
  Radar,
  ShieldAlert,
  Moon,
  Sun,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Dashboard", icon: Gauge },
  { to: "/queue", label: "Review Queue", icon: ListChecks },
  { to: "/evidence", label: "Evidence Center", icon: FileStack },
  { to: "/audit", label: "Audit History", icon: History },
] as const;

function ThemeToggle() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const saved =
      window.localStorage.getItem("claimsense-theme") === "light"
        ? "light"
        : "dark";

    document.documentElement.classList.remove("dark", "light");
    document.documentElement.classList.add(saved);
    document.documentElement.style.colorScheme = saved;
    setTheme(saved);
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";

    document.documentElement.classList.remove("dark", "light");
    document.documentElement.classList.add(nextTheme);
    document.documentElement.style.colorScheme = nextTheme;
    window.localStorage.setItem("claimsense-theme", nextTheme);
    setTheme(nextTheme);
  };

  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="focus-ring tactile-control inline-flex items-center gap-2 rounded-sm border border-shell-border px-2.5 py-2 text-shell-muted hover:bg-shell-elevated hover:text-shell-foreground"
      aria-label={`Switch to ${isDark ? "light" : "dark"} theme`}
      title={`Switch to ${isDark ? "light" : "dark"} theme`}
    >
      {isDark ? (
        <Sun className="size-3.5" aria-hidden />
      ) : (
        <Moon className="size-3.5" aria-hidden />
      )}

      <span className="hidden text-xs sm:inline">
        {isDark ? "Light" : "Dark"}
      </span>
    </button>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = useRouterState({
    select: (s) => s.location.pathname,
  });

  return (
    <div className="flex min-h-screen bg-background selection:bg-steel/20">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-shell-border bg-shell text-shell-foreground md:flex">
        <div className="grid-backdrop border-b border-shell-border px-5 py-5">
          <div className="flex items-center gap-2">
            <span className="flex size-8 items-center justify-center rounded-md border border-steel/30 bg-steel/10 text-steel">
              <Radar className="size-4" aria-hidden />
            </span>

            <div>
              <span className="block text-[15px] font-semibold tracking-tight">
                ClaimSense
              </span>
              <span className="tech-label text-shell-muted">
                Operations desk
              </span>
            </div>
          </div>
        </div>

        <nav
          className="flex flex-1 flex-col gap-1 p-3"
          aria-label="Main"
        >
          {NAV.map(({ to, label, icon: Icon }) => {
            const active =
              to === "/" ? pathname === "/" : pathname.startsWith(to);

            return (
              <Link
                key={to}
                to={to}
                className={cn(
                  "focus-ring tactile-control flex items-center gap-3 rounded-sm px-3 py-2 text-sm",
                  active
                    ? "bg-shell-elevated text-shell-foreground shadow-[inset_2px_0_0_0_var(--steel),0_8px_20px_-18px_rgb(0_0_0_/_80%)]"
                    : "text-shell-muted hover:bg-shell-elevated/70 hover:text-shell-foreground",
                )}
              >
                <Icon className="size-4" aria-hidden />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="m-3 rounded-sm border border-shell-border bg-shell-elevated/60 p-3">
          <p className="tech-label flex items-center gap-1.5 text-moderate">
            <ShieldAlert className="size-3" aria-hidden />
            Decision support only
          </p>

          <p className="mt-1.5 text-xs leading-relaxed text-shell-muted">
            ClaimSense reports detected damage and provisional severity. Every
            assessment requires a qualified human reviewer.
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-shell-border bg-shell/95 px-4 py-3 text-shell-foreground shadow-[0_10px_30px_-26px_rgb(0_0_0_/_90%)] backdrop-blur-sm md:px-8">
          <div className="flex items-center gap-2 md:hidden">
            <Radar className="size-5 text-steel" aria-hidden />
            <span className="font-semibold">ClaimSense</span>
          </div>

          <nav
            className="hidden items-center gap-1 md:flex"
            aria-label="Breadcrumb"
          >
            <span className="tech-label text-shell-muted">
              Assessment workspace
            </span>
          </nav>

          <div className="flex items-center gap-2">
            <ThemeToggle />
          </div>
        </header>

        <nav
          className="flex gap-1 overflow-x-auto border-b border-shell-border bg-shell px-2 pb-2 md:hidden"
          aria-label="Main mobile"
        >
          {NAV.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className="focus-ring tactile-control flex shrink-0 items-center gap-2 rounded-sm px-3 py-2 text-xs text-shell-muted [&.active]:bg-shell-elevated [&.active]:text-shell-foreground"
              activeProps={{ className: "active" }}
              activeOptions={{ exact: to === "/" }}
            >
              <Icon className="size-4" aria-hidden />
              {label}
            </Link>
          ))}
        </nav>

        <main className="flex-1 px-4 py-6 md:px-8 md:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}