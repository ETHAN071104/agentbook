// @ts-nocheck
import {
  FileText,
  ClipboardList,
  Target,
  Brain,
  Bot,
  CheckCircle2,
  Lock,
  Database,
} from "lucide-react";
import { motion } from "framer-motion";
import { SectionHeader } from "./SectionHeader";

const features = [
  {
    icon: FileText,
    title: "Grounded Learning Library",
    description: "Upload, organize and retrieve learning material with source citations.",
    color: "text-royal",
    bg: "bg-royal/10",
  },
  {
    icon: ClipboardList,
    title: "Adaptive Quizzes",
    description: "Generate quizzes from uploaded content and store question-level outcomes.",
    color: "text-royal",
    bg: "bg-sky-glow/15",
  },
  {
    icon: Target,
    title: "Weakness Detection",
    description: "Rank recent and repeated mistakes to identify what the learner should review.",
    color: "text-royal",
    bg: "bg-royal/10",
  },
  {
    icon: Brain,
    title: "Persistent Learner Memory",
    description: "Preserve relevant learning history and retrieve it semantically.",
    color: "text-royal",
    bg: "bg-royal/10",
  },
  {
    icon: Bot,
    title: "Controlled Learning Agent",
    description: "Use fixed tools to inspect weaknesses, mistakes, materials and plans.",
    color: "text-royal",
    bg: "bg-royal/10",
  },
  {
    icon: CheckCircle2,
    title: "Confirmed Agent Actions",
    description: "Convert recommendations into persistent Study Tasks only after explicit confirmation.",
    color: "text-royal",
    bg: "bg-royal/10",
  },
  {
    icon: Lock,
    title: "Private Guest Study Spaces",
    description: "Isolate relational and vector data for every learner.",
    color: "text-royal",
    bg: "bg-sky-glow/15",
  },
  {
    icon: Database,
    title: "CockroachDB Vector Search",
    description: "Store operational data and vector embeddings in the same distributed database.",
    color: "text-royal",
    bg: "bg-royal/10",
  },
];

export function FeatureGrid() {
  return (
    <section id="features" className="relative z-10 px-4 py-24 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <SectionHeader
          eyebrow="Why Agentbook"
          title="Core Features"
          subtitle="A complete learning system that organizes your knowledge, tests your memory, and keeps you on track."
        />

        <motion.div
          className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4 auto-rows-fr"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={{ visible: { transition: { staggerChildren: 0.1, delayChildren: 0.2 } }, hidden: {} }}
        >
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <motion.div
                key={feature.title}
                variants={{ hidden: { opacity: 0, y: 20 }, visible: { opacity: 1, y: 0 } }}
                transition={{ type: "spring", stiffness: 80, damping: 20, mass: 0.8 }}
                whileHover={{ y: -4, scale: 1.02 }}
              >
                <div className="clay-card-soft h-full p-6">
                  <div
                    className={`mb-4 flex h-12 w-12 items-center justify-center rounded-2xl ${feature.bg}`}
                  >
                    <Icon className={`h-6 w-6 ${feature.color}`} />
                  </div>
                  <h3 className="font-display text-lg font-semibold text-foreground dark:text-dark-text">
                    {feature.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground dark:text-dark-muted line-clamp-2">
                    {feature.description}
                  </p>
                </div>
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </section>
  );
}
