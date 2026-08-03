// @ts-nocheck
import { BookOpen, Sun, Moon } from "lucide-react";
import { useState, useEffect } from "react";

function ThemeToggle({
  dark,
  onToggle,
}: {
  dark: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition-colors hover:text-slate-900 dark:text-dark-muted dark:hover:text-dark-text"
    >
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}

const links = [
  { label: "Features", href: "#features" },
  { label: "How It Works", href: "#process" },
  { label: "Study Hub", href: "#study-hub" },
  { label: "Tech Stack", href: "#technology" },
];

export function Navbar() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = stored === "dark" || (!stored && prefersDark);
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-slate-200/60 bg-white/95 backdrop-blur-sm dark:border-dark-border dark:bg-dark-bg/95">
      <nav className="mx-auto flex h-20 max-w-7xl items-center justify-between gap-8 px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <a href="/" className="flex shrink-0 items-center gap-2 text-slate-900 dark:text-dark-text">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-royal text-white shadow-sm">
            <BookOpen className="h-5 w-5" />
          </div>
          <span className="font-display text-lg font-bold tracking-tight">Agentbook</span>
        </a>

        {/* Pill-style navigation links */}
        <div className="hidden items-center gap-1 sm:flex">
          {links.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="whitespace-nowrap rounded-full px-5 py-2.5 text-base font-semibold text-slate-600 transition-all duration-200 hover:bg-royal hover:text-white dark:text-dark-muted dark:hover:bg-royal dark:hover:text-white"
            >
              {link.label}
            </a>
          ))}
        </div>

        {/* Actions */}
        <div className="flex shrink-0 items-center gap-3">
          <ThemeToggle dark={dark} onToggle={toggle} />
          <a
            href="/app"
            className="rounded-full bg-royal px-5 py-2.5 text-base font-semibold text-white transition-all hover:bg-royal/90 active:scale-[0.97]"
          >
            Get Started Free
          </a>
        </div>
      </nav>
    </header>
  );
}
