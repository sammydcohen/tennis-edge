"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Moon, Sun } from "lucide-react";
import { cn } from "cn";

import { Button } from "@/components/ui/button";

const NAV = [
  { href: "/", label: "Findings" },
  { href: "/live/", label: "Live matches" },
  { href: "/rankings/", label: "Rankings" },
];

function ThemeToggle() {
  const toggle = () => {
    const dark = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem("theme", dark ? "dark" : "light");
    } catch {}
  };
  return (
    <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle light and dark theme">
      <Sun className="hidden dark:block" />
      <Moon className="dark:hidden" />
    </Button>
  );
}

function Logo() {
  // A tennis ball: a circle with the two seam curves.
  return (
    <svg viewBox="0 0 24 24" className="size-6" aria-hidden>
      <circle cx="12" cy="12" r="10" className="fill-[#d4e157] dark:fill-[#c0ca33]" />
      <path d="M4.2 6.5c3.2 2 3.2 9 0 11M19.8 6.5c-3.2 2-3.2 9 0 11" fill="none" stroke="white" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 h-14 flex items-center gap-3 sm:gap-6">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight whitespace-nowrap" aria-label="Tennis Edge home">
          <Logo />
          <span className="hidden sm:inline">Tennis Edge</span>
        </Link>
        <nav className="flex items-center gap-0.5 sm:gap-1 text-sm whitespace-nowrap">
          {NAV.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-md px-2 sm:px-3 py-1.5 transition-colors hover:text-foreground",
                  active ? "bg-muted text-foreground" : "text-muted-foreground",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
