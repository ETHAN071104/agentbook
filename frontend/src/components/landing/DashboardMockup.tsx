// @ts-nocheck
import {
  MessageSquare,
  FileText,
  Brain,
  TrendingUp,
  Calendar,
  Layers,
  Lightbulb,
  Search,
  Bell,
  BookOpen,
  MoreHorizontal,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

function ProgressChart() {
  return (
    <svg viewBox="0 0 300 100" className="h-full w-full overflow-visible">
      <defs>
        <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#60a5fa" />
          <stop offset="100%" stopColor="#2563eb" />
        </linearGradient>
        <linearGradient id="areaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#2563eb" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#2563eb" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        d="M0,80 C30,75 60,55 90,50 C120,45 150,60 180,35 C210,10 240,25 270,15 C290,8 300,5 300,5"
        fill="none"
        stroke="url(#lineGradient)"
        strokeWidth="3"
        strokeLinecap="round"
        className="animate-chart-draw"
      />
      <path
        d="M0,80 C30,75 60,55 90,50 C120,45 150,60 180,35 C210,10 240,25 270,15 C290,8 300,5 300,5 L300,100 L0,100 Z"
        fill="url(#areaGradient)"
        opacity="0"
        style={{ animation: "fade-in-up 1s ease-out 1.5s forwards" }}
      />
      <circle cx="300" cy="5" r="5" fill="#2563eb" />
    </svg>
  );
}

function ChatWidget() {
  return (
    <div className="clay-panel col-span-2 p-4">
      <div className="mb-3 flex items-center gap-2 text-slate-700 dark:text-dark-muted">
        <MessageSquare className="h-4 w-4 text-royal" />
        <span className="text-sm font-semibold">AI Study Chat</span>
        <span className="ml-auto flex h-2 w-2 rounded-full bg-royal animate-pulse" />
      </div>
      <div className="rounded-xl bg-royal/5 p-3 text-sm text-slate-600 dark:text-dark-muted">
        <p className="mb-2 font-medium text-slate-900 dark:text-dark-text">&ldquo;Explain Fourier Transform like I&rsquo;m learning it for the first time.&rdquo;</p>
        <p className="text-xs leading-relaxed text-slate-500 dark:text-dark-muted">
          Think of the Fourier Transform as a prism for signals. Just like white light splits into colors, it breaks a complex signal into simple sine waves...
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="inline-flex items-center gap-1 rounded-full bg-royal/20 px-2 py-1 text-[10px] text-royal">
            <FileText className="h-3 w-3" /> Signals & Systems.pptx
          </span>
          <span className="inline-flex items-center gap-1 rounded-full bg-royal/20 px-2 py-1 text-[10px] text-royal">
            <FileText className="h-3 w-3" /> Lecture 7
          </span>
        </div>
      </div>
    </div>
  );
}

function DocumentsWidget() {
  const docs = [
    { name: "Operating Systems.pdf", size: "12 MB", color: "bg-royal" },
    { name: "Signals & Systems.pptx", size: "8 MB", color: "bg-sky-500" },
    { name: "Machine Learning Notes", size: "24 notes", color: "bg-blue-400" },
    { name: "Computer Networks", size: "18 notes", color: "bg-blue-400" },
  ];

  return (
    <div className="clay-panel p-4">
      <div className="mb-3 flex items-center gap-2 text-slate-700 dark:text-dark-muted">
        <FileText className="h-4 w-4 text-royal" />
        <span className="text-sm font-semibold">Uploaded Documents</span>
      </div>
      <div className="space-y-2">
        {docs.map((doc) => (
          <div
            key={doc.name}
            className="flex items-center gap-2 rounded-lg bg-royal/5 p-2 transition-colors hover:bg-royal/15"
          >
            <div className={`h-8 w-8 rounded-lg ${doc.color} flex items-center justify-center`}>
              <FileText className="h-4 w-4 text-white" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-slate-900 dark:text-dark-text">{doc.name}</p>
              <p className="text-[10px] text-slate-400 dark:text-dark-muted">{doc.size}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function QuizWidget() {
  const quizzes = [
    { title: "Boolean Algebra", score: "8/10", status: "✓", statusColor: "text-emerald-500" },
    { title: "Cache Coherence", score: "5/8", status: "⏳", statusColor: "text-amber-500" },
    { title: "Laplace Transform", score: "3/10", status: "⚠", statusColor: "text-rose-500" },
  ];

  return (
    <div className="clay-panel p-3">
      <div className="mb-2 flex items-center gap-2 text-slate-700 dark:text-dark-muted">
        <Brain className="h-3.5 w-3.5 text-royal" />
        <span className="text-xs font-semibold">Quiz Results</span>
      </div>
      <div className="space-y-1.5">
        {quizzes.map((q) => (
          <div
            key={q.title}
            className="flex items-center justify-between rounded-lg bg-royal/5 px-2.5 py-1.5"
          >
            <span className="text-[11px] font-medium text-slate-800 dark:text-dark-text">{q.title}</span>
            <span className="flex items-center gap-1">
              <span className="text-[11px] font-semibold text-slate-600 dark:text-dark-muted">{q.score}</span>
              <span className={`text-xs ${q.statusColor}`}>{q.status}</span>
            </span>
          </div>
        ))}
      </div>
      <button className="mt-2 w-full rounded-md bg-royal/10 py-1.5 text-[11px] font-medium text-royal transition-colors hover:bg-royal/20">
        Start New Quiz
      </button>
    </div>
  );
}

function ProgressWidget() {
  return (
    <div className="clay-panel col-span-2 p-4">
      <div className="mb-2 flex items-center justify-between text-slate-700 dark:text-dark-muted">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-royal" />
          <span className="text-sm font-semibold">Weekly Study Progress</span>
        </div>
        <span className="text-xs text-royal">+18%</span>
      </div>
      <div className="h-24 w-full">
        <ProgressChart />
      </div>
    </div>
  );
}

function InsightsWidget() {
  return (
    <div className="clay-panel p-3">
      <div className="mb-2 flex items-center gap-2 text-slate-700 dark:text-dark-muted">
        <Lightbulb className="h-3.5 w-3.5 text-royal" />
        <span className="text-xs font-semibold">AI Insights</span>
      </div>
      <p className="mb-1.5 text-[11px] text-slate-600 dark:text-dark-muted">You&rsquo;re struggling with Digital Logic.</p>
      <div className="rounded-lg bg-royal/10 p-2">
        <p className="text-[10px] text-slate-500 dark:text-dark-muted">Recommended review:</p>
        <p className="text-xs font-medium text-royal">Boolean Algebra (15 min)</p>
      </div>
    </div>
  );
}

function CalendarWidget() {
  const days = ["M", "T", "W", "T", "F", "S", "S"];

  return (
    <div className="clay-panel p-4">
      <div className="mb-3 flex items-center gap-2 text-slate-700 dark:text-dark-muted">
        <Calendar className="h-4 w-4 text-royal" />
        <span className="text-sm font-semibold">Upcoming</span>
      </div>
      <div className="mb-3 flex justify-between text-xs text-slate-500 dark:text-dark-muted">
        {days.map((d, i) => (
          <div
            key={i}
            className={`flex h-7 w-7 items-center justify-center rounded-lg ${
              i === 2 ? "bg-royal text-white" : "bg-royal/5"
            }`}
          >
            {d}
          </div>
        ))}
      </div>
      <div className="space-y-2">
        <div className="rounded-lg bg-royal/5 p-2">
          <p className="text-[10px] text-slate-400 dark:text-dark-muted">10:00 AM</p>
          <p className="text-xs text-slate-700 dark:text-dark-muted">OS Quiz</p>
        </div>
        <div className="rounded-lg bg-royal/5 p-2">
          <p className="text-[10px] text-slate-400 dark:text-dark-muted">2:00 PM</p>
          <p className="text-xs text-slate-700 dark:text-dark-muted">Assignment Due</p>
        </div>
      </div>
    </div>
  );
}

function FlashcardsWidget() {
  return (
    <div className="clay-panel p-4">
      <div className="mb-3 flex items-center gap-2 text-slate-700 dark:text-dark-muted">
        <Layers className="h-4 w-4 text-royal" />
        <span className="text-sm font-semibold">Flashcards</span>
      </div>
      <div className="rounded-xl bg-gradient-to-br from-royal/15 to-sky-glow/20 p-4 text-center">
        <p className="text-3xl font-bold text-slate-900 dark:text-dark-text">12</p>
        <p className="text-xs text-slate-500 dark:text-dark-muted">cards due today</p>
      </div>
      <button className="mt-3 w-full rounded-lg bg-royal/10 py-2 text-xs font-medium text-slate-900 dark:text-dark-text transition-colors hover:bg-royal/15">
        Start Review
      </button>
    </div>
  );
}







export function DashboardMockup() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [transform, setTransform] = useState("rotateY(-4deg) rotateX(2deg)");

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) return;

    const handleMouseMove = (e: MouseEvent) => {
      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;

      setTransform(`rotateY(${-4 + x * 4}deg) rotateX(${2 - y * 4}deg)`);
    };

    const handleMouseLeave = () => {
      setTransform("rotateY(-4deg) rotateX(2deg)");
    };

    const container = containerRef.current;
    container?.addEventListener("mousemove", handleMouseMove);
    container?.addEventListener("mouseleave", handleMouseLeave);

    return () => {
      container?.removeEventListener("mousemove", handleMouseMove);
      container?.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative w-full max-w-4xl animate-float"
      style={{ perspective: "1200px" }}
    >
      <div
        className="clay-card-shell relative overflow-hidden p-3 transition-transform duration-200 ease-out sm:p-4"
        style={{ transform: transform, transformStyle: "preserve-3d" }}
      >
        {/* Dashboard header */}
        <div className="mb-3 flex items-center justify-between border-b border-royal/10 pb-3">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-royal text-white">
              <BookOpen className="h-4 w-4" />
            </div>
            <span className="font-display text-sm font-semibold text-slate-900 dark:text-dark-text">Agentbook</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden items-center gap-1.5 rounded-full bg-royal/5 px-2.5 py-1 sm:flex">
              <Search className="h-3 w-3 text-slate-400 dark:text-dark-muted" />
              <span className="text-[10px] text-slate-400 dark:text-dark-muted">Search your knowledge...</span>
            </div>
            <button className="relative rounded-full bg-royal/10 p-1.5 text-slate-600 hover:bg-royal/15 dark:text-dark-muted">
              <Bell className="h-3.5 w-3.5" />
              <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-royal" />
            </button>
            <div className="h-7 w-7 rounded-full bg-gradient-to-br from-sky-glow to-royal" />
          </div>
        </div>

        {/* Sidebar + content layout */}
        <div className="flex gap-2">
          {/* Mini sidebar */}
          <div className="hidden flex-col gap-1.5 sm:flex">
            {[
              MessageSquare,
              FileText,
              Brain,
              TrendingUp,
              Calendar,
              Layers,
              MoreHorizontal,
            ].map((Icon, i) => (
              <div
                key={i}
                className={`flex h-8 w-8 items-center justify-center rounded-xl ${
                  i === 0 ? "bg-royal text-white" : "bg-royal/5 text-slate-500 hover:bg-royal/15 hover:text-slate-900 dark:text-dark-muted dark:hover:text-dark-text"
                } transition-colors`}
              >
                <Icon className="h-3.5 w-3.5" />
              </div>
            ))}
          </div>

          {/* Dashboard grid */}
          <div className="grid flex-1 grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            <ChatWidget />
            <DocumentsWidget />
            <QuizWidget />
            <ProgressWidget />
            <CalendarWidget />
            <FlashcardsWidget />
            <InsightsWidget />
          </div>
        </div>
      </div>
    </div>
  );
}
