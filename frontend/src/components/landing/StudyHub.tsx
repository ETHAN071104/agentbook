// @ts-nocheck
import {
  CloudUpload,
  SquareCheckBig,
  Brain,
  Target,
  LayoutDashboard,
  CheckCircle2,
  FileText,
  Clock,
  Zap,
  HelpCircle,
  BarChart3,
} from "lucide-react";
import { motion } from "framer-motion";
import TiltedCard from "@/components/reactbits/TiltedCard";
import { SectionHeader } from "./SectionHeader";

const gradientUrl = (from: string, to: string) => {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="300">
    <defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="${from}"/>
      <stop offset="100%" stop-color="${to}"/>
    </linearGradient></defs>
    <rect width="800" height="300" fill="url(#g)"/>
  </svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
};

const cardGradients: Record<string, [string, string]> = {
  "clay-blue": ["#2563eb", "#60a5fa"],
  "clay-purple": ["#7c3aed", "#a78bfa"],
  "clay-dark": ["#1e293b", "#475569"],
  "clay-card": ["#f1f5f9", "#e2e8f0"],
  "clay-mint": ["#2dd4bf", "#5eead4"],
};

const items = [
  {
    icon: CloudUpload,
    title: "Upload Notes",
    description: "PDFs, slides, images, text. We'll handle the parsing and indexing.",
    className: "clay-blue",
    span: "lg:col-span-6",
    mockup: (
      <div className="mt-4 flex h-32 w-full flex-col gap-3 overflow-hidden rounded-xl border border-white/20 bg-white/15 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-5 w-5 items-center justify-center rounded-md bg-white/30">
              <FileText className="h-3 w-3 text-white" />
            </div>
            <span className="text-xs font-semibold text-white/90">Recent Files</span>
          </div>
          <span className="rounded-full bg-white/20 px-2 py-0.5 text-[10px] font-medium text-white/80">12 files</span>
        </div>
        <div className="flex flex-col gap-1.5">
          {[
            { name: "OS_Lecture_8.pdf", type: "PDF", color: "bg-red-400", date: "Today" },
            { name: "ML_Notes_Q4.docx", type: "DOC", color: "bg-blue-400", date: "Yesterday" },
            { name: "Signals_Review", type: "SLIDE", color: "bg-emerald-400", date: "2d ago" },
          ].map((file) => (
            <div key={file.name} className="flex items-center gap-2 rounded-lg bg-white/20 px-2.5 py-1.5">
              <div className={`flex h-5 w-5 items-center justify-center rounded ${file.color}`}>
                <FileText className="h-3 w-3 text-white" />
              </div>
              <span className="flex-1 truncate text-[10px] font-medium text-white/90">{file.name}</span>
              <span className="text-[9px] text-white/50">{file.date}</span>
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    icon: SquareCheckBig,
    title: "Generate Quiz",
    description: "AI creates quizzes instantly from your notes, targeting key concepts.",
    className: "clay-purple",
    span: "lg:col-span-6",
    mockup: (
      <div className="mt-4 flex h-32 w-full gap-4 overflow-hidden rounded-xl border border-white/20 bg-white/10 p-4">
        <div className="flex flex-1 flex-col gap-2">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <HelpCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-white/70" />
              <span className="text-[10px] font-medium text-white/70">Question 3 of 5</span>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <span className="flex items-center gap-0.5 rounded-md bg-amber-400/20 px-1.5 py-0.5 text-[9px] text-amber-300">
                <Zap className="h-2.5 w-2.5" />5
              </span>
              <span className="flex items-center gap-0.5 rounded-md bg-white/10 px-1.5 py-0.5 text-[9px] text-white/60">
                <Clock className="h-2.5 w-2.5" />2:34
              </span>
              <span className="rounded-md bg-emerald-400/20 px-1.5 py-0.5 text-[9px] font-medium text-emerald-300">8/10</span>
            </div>
          </div>
          <p className="text-[11px] font-medium leading-snug text-white/90">What is the time complexity of merge sort?</p>
          <div className="grid grid-cols-2 gap-1.5">
            {["O(n²)", "O(n log n)", "O(log n)", "O(n)"].map((opt, i) => (
              <div
                key={opt}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[10px] ${
                  i === 1
                    ? "bg-emerald-500/30 text-emerald-200 ring-1 ring-emerald-400/40"
                    : "bg-white/10 text-white/70"
                }`}
              >
                <div className={`flex h-3.5 w-3.5 items-center justify-center rounded-full text-[7px] font-bold ${
                  i === 1 ? "bg-emerald-400 text-white" : "bg-white/20 text-white/50"
                }`}>
                  {String.fromCharCode(65 + i)}
                </div>
                {opt}
              </div>
            ))}
          </div>
          <div className="mt-auto h-1 w-full rounded-full bg-white/10">
            <div className="h-1 w-3/5 rounded-full bg-white/40" />
          </div>
        </div>
      </div>
    ),
  },
  {
    icon: Brain,
    title: "Learner Memory",
    description: "Remembers what you've learned across all your study sessions.",
    className: "clay-dark",
    span: "lg:col-span-4",
    mockup: (
      <div className="mt-4 flex h-32 w-full flex-col gap-3 overflow-hidden rounded-xl border border-white/10 bg-white/5 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-5 w-5 items-center justify-center rounded-md bg-emerald-500/30">
              <CheckCircle2 className="h-3 w-3 text-emerald-400" />
            </div>
            <span className="text-xs font-semibold text-white/80">Retained Topics</span>
          </div>
          <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400">24</span>
        </div>
        <div className="flex flex-col gap-2">
          {[
            { topic: "Boolean Algebra", pct: 92, color: "bg-emerald-400" },
            { topic: "Cache Coherence", pct: 68, color: "bg-amber-400" },
            { topic: "Laplace Transform", pct: 35, color: "bg-rose-400" },
          ].map((item) => (
            <div key={item.topic} className="flex items-center gap-2.5">
              <span className="w-[88px] truncate text-[10px] font-medium text-white/70">{item.topic}</span>
              <div className="flex-1">
                <div className="h-1.5 w-full rounded-full bg-white/10">
                  <div className={`h-1.5 rounded-full ${item.color}`} style={{ width: `${item.pct}%` }} />
                </div>
              </div>
              <span className="w-6 text-right text-[9px] font-semibold text-white/50">{item.pct}%</span>
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    icon: Target,
    title: "Study Plan",
    description: "Set and track your learning goals over time.",
    className: "clay-card",
    span: "lg:col-span-4",
    mockup: (
      <div className="mt-4 flex h-32 w-full flex-col gap-3 overflow-hidden rounded-xl border border-white/20 bg-white/15 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-5 w-5 items-center justify-center rounded-md bg-royal text-white">
              <Target className="h-3 w-3" />
            </div>
            <span className="text-xs font-semibold text-slate-800 dark:text-dark-text">This Week</span>
          </div>
          <span className="rounded-full bg-royal/15 px-2 py-0.5 text-[10px] font-medium text-royal">3/5</span>
        </div>
        <div className="flex gap-2">
          {[
            { label: "Operating Systems", hrs: "4h", pct: 75, color: "bg-royal" },
            { label: "DSA", hrs: "3h", pct: 60, color: "bg-sky-500" },
            { label: "Machine Learning", hrs: "2h", pct: 40, color: "bg-emerald-500" },
          ].map((subj) => (
            <div key={subj.label} className="flex flex-1 flex-col gap-1 rounded-lg bg-white/40 p-2 dark:bg-white/5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-medium text-slate-700 dark:text-dark-text">{subj.label}</span>
                <span className="text-[9px] text-slate-400 dark:text-dark-muted">{subj.hrs}</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-slate-200/50 dark:bg-white/10">
                <div className={`h-1.5 rounded-full ${subj.color}`} style={{ width: `${subj.pct}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    icon: LayoutDashboard,
    title: "Progress Dashboard",
    description: "Track time, score, and retention all in one place.",
    className: "clay-mint",
    span: "lg:col-span-4",
    mockup: (
      <div className="mt-4 flex h-32 w-full flex-col gap-3 overflow-hidden rounded-xl border border-teal-900/20 bg-white/30 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-5 w-5 items-center justify-center rounded-md bg-teal-900/20">
              <BarChart3 className="h-3 w-3 text-teal-800" />
            </div>
            <span className="text-xs font-semibold text-teal-800">Weekly Stats</span>
          </div>
          <span className="rounded-full bg-teal-900/15 px-2 py-0.5 text-[10px] font-bold text-teal-700">+18%</span>
        </div>
        <div className="flex gap-2">
          {[
            { label: "Study Time", value: "12h", pct: 75, trend: "+2h" },
            { label: "Quizzes", value: "18", pct: 60, trend: "+5" },
            { label: "Retention", value: "82%", pct: 82, trend: "+4%" },
          ].map((stat) => (
            <div key={stat.label} className="flex flex-1 flex-col gap-1 rounded-lg bg-teal-900/10 p-2">
              <div className="flex items-center justify-between">
                <span className="text-[9px] font-medium text-teal-700">{stat.label}</span>
                <span className="text-[10px] font-bold text-teal-800">{stat.value}</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-teal-900/10">
                <div className="h-1.5 rounded-full bg-teal-600" style={{ width: `${stat.pct}%` }} />
              </div>
              <span className="text-[8px] text-teal-600/70">{stat.trend} vs last week</span>
            </div>
          ))}
        </div>
      </div>
    ),
  },
];

export function StudyHub() {
  return (
    <section id="study-hub" className="relative z-10 px-4 py-24 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <SectionHeader
          eyebrow="All-in-one workspace"
          title="Everything you need to study in one place"
          subtitle="Stop switching between Notion, Quizlet, and ChatGPT. Agentbook integrates the entire study loop into a single platform."
        />

        <motion.div
          className="grid grid-cols-1 gap-6 lg:grid-cols-12"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={{ visible: { transition: { staggerChildren: 0.1, delayChildren: 0.15 } }, hidden: {} }}
        >
          {items.map((item) => {
            const Icon = item.icon;
            const gradient = cardGradients[item.className] || ["#6366f1", "#818cf8"];
            const isLight = item.className === "clay-card";
            return (
              <motion.div
                key={item.title}
                variants={{ hidden: { opacity: 0, y: 24 }, visible: { opacity: 1, y: 0 } }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                className={item.span}
              >
                <TiltedCard
                  imageSrc={gradientUrl(gradient[0], gradient[1])}
                  containerHeight="320px"
                  containerWidth="100%"
                  imageHeight="320px"
                  imageWidth="100%"
                  rotateAmplitude={6}
                  scaleOnHover={1.03}
                  showMobileWarning={false}
                  showTooltip={false}
                  displayOverlayContent={true}
                  overlayContent={
                    <div className="flex h-full w-full flex-col p-5">
                      <div className="mb-3 flex items-center gap-3">
                        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${isLight ? "bg-royal/10" : "bg-white/25"}`}>
                          <Icon className={`h-5 w-5 ${isLight ? "text-royal" : "text-white"}`} />
                        </div>
                        <h3 className={`text-xl font-bold ${isLight ? "text-slate-900" : "text-white"}`}>{item.title}</h3>
                      </div>
                      <p className={`mb-3 flex-1 text-sm ${isLight ? "text-slate-600" : "text-white/80"}`}>
                        {item.description}
                      </p>
                      {item.mockup}
                    </div>
                  }
                />
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </section>
  );
}
