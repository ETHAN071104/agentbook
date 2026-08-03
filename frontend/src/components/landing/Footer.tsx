// @ts-nocheck
import { GitBranch } from "lucide-react";

export function Footer() {
  return (
    <footer className="relative z-10 border-t border-royal/10 bg-transparent px-4 py-10 sm:px-6 lg:px-8 dark:border-dark-border dark:bg-transparent">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 sm:flex-row">
        <p className="text-sm text-slate-400 dark:text-dark-muted">
          &copy; 2026 Agentbook. Built for focused learning.
        </p>
        <a
          href="https://github.com/thamkaile/Agentbook"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-full border border-royal/15 bg-white px-5 py-2 text-sm font-semibold text-slate-700 shadow-clay-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-royal/30 hover:text-royal dark:border-dark-border dark:bg-dark-card dark:text-dark-text dark:hover:text-royal"
        >
          <GitBranch className="h-4 w-4" />
          View on GitHub
        </a>
      </div>
    </footer>
  );
}
