// @ts-nocheck
import { motion, useReducedMotion } from "framer-motion";
import { Eye, Brain, Zap, CheckCircle2, Save, ArrowRight, ArrowDown, RotateCcw, Check } from "lucide-react";
import ScrollStack, { ScrollStackItem } from "@/components/reactbits/ScrollStack";
import { SectionHeader } from "./SectionHeader";

const steps = [
  {
    icon: Eye,
    title: "Observe",
    description:
      "Agentbook reads the current workspace's bounded learning evidence, including weak topics, recent mistakes, study materials, and the active plan, before it responds.",
    details: [
      "Only reads its own workspace, so nothing leaks across learners",
      "Ranks weak topics by recency and how often they are repeated",
      "Always aware of the current plan before deciding what to do",
    ],
    bg: "bg-sky-500",
  },
  {
    icon: Brain,
    title: "Reason",
    description:
      "Using the evidence it gathered, the agent picks up to four allow-listed tools and reasons through a concise answer or a proposed Study Task action.",
    details: [
      "Tool access is fixed and auditable, with no arbitrary commands",
      "Balances facts from your library with your learning history",
      "Produces concrete answers and next actions, not vague advice",
    ],
    bg: "bg-royal",
  },
  {
    icon: Zap,
    title: "Act",
    description:
      "The agent returns a proposal preview. Nothing is created until you see the exact action and choose to confirm it.",
    details: [
      "Every action is previewed before anything changes",
      "Proposals are single-use and expire before they go stale",
      "Nothing executes without your explicit go-ahead",
    ],
    bg: "bg-amber-500",
  },
  {
    icon: CheckCircle2,
    title: "Confirm",
    description:
      "Only after you confirm does the action run. Proposals are workspace-scoped, expiring, and single-use, so one click can't cause hidden side effects.",
    details: [
      "Confirmation is one tap, with no hidden side effects",
      "Workspace-scoped: your relational and vector data stay isolated",
      "Single-use tokens prevent accidental duplicate actions",
    ],
    bg: "bg-emerald-500",
  },
  {
    icon: Save,
    title: "Persist",
    description:
      "The confirmed task or learning outcome is saved, so later sessions start from a smarter baseline and adapt for next time.",
    details: [
      "Outcomes feed your persistent learner memory",
      "Study Tasks become part of the evidence for future plans",
      "The loop restarts from a smarter, more informed baseline",
    ],
    bg: "bg-purple-500",
  },
];

interface Step {
  icon: typeof Eye;
  title: string;
  description: string;
  details: string[];
  bg: string;
}

function StepCard({ step, index }: { step: Step; index: number }) {
  const Icon = step.icon;
  const reduceMotion = useReducedMotion();
  const nextStep = steps[index + 1];
  return (
    <div
      className={`${step.bg} relative flex flex-col overflow-hidden rounded-3xl p-8 sm:min-h-[24rem] sm:p-10`}
    >
      <span className="pointer-events-none absolute -right-4 -top-8 select-none font-display text-[9rem] font-extrabold leading-none text-white/10">
        {index + 1}
      </span>

      <div className="relative flex items-start justify-between gap-4">
        <div className="relative flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-white/20">
          <Icon className="h-7 w-7 text-white" />
        </div>
        {index === 4 ? (
          !reduceMotion ? (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
              className="shrink-0"
            >
              <RotateCcw className="h-7 w-7 text-white/60" />
            </motion.div>
          ) : (
            <RotateCcw className="h-7 w-7 shrink-0 text-white/60" />
          )
        ) : (
          <span className="rounded-full bg-white/15 px-3 py-1 text-xs font-bold uppercase tracking-widest text-white/80">
            Step 0{index + 1}
          </span>
        )}
      </div>

      <div className="relative mt-6 sm:mt-8">
        <h3 className="font-display text-2xl font-extrabold text-white sm:text-3xl">
          {step.title}
        </h3>
        <p className="mt-3 text-base leading-relaxed text-white/85 sm:text-lg">
          {step.description}
        </p>
        <ul className="mt-5 space-y-2.5">
          {step.details.map((detail) => (
            <li key={detail} className="flex items-start gap-2.5">
              <Check className="mt-1 h-4 w-4 shrink-0 text-white/70" />
              <span className="text-sm leading-relaxed text-white/80 sm:text-base">
                {detail}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="relative mt-auto flex items-center gap-2 pt-8 text-sm font-bold text-white/70">
        {nextStep ? (
          <>
            <ArrowDown className="h-4 w-4" />
            Next: {nextStep.title}
          </>
        ) : (
          <>
            <CheckCircle2 className="h-4 w-4" />
            The loop closes and adapts
          </>
        )}
      </div>
    </div>
  );
}

export function LearningLoop() {
  return (
    <section id="process" className="relative z-10 px-4 py-24 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <SectionHeader
          eyebrow="How it works"
          title="The Agentic Learning Loop"
          subtitle="Agentbook does more than chat. It observes, reasons, and persists, turning every session into a smarter study plan."
        />

        <div className="flex flex-col gap-6 lg:hidden">
          {steps.map((step, i) => (
            <motion.div
              key={step.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{
                duration: 0.5,
                delay: i * 0.1,
                ease: [0.16, 1, 0.3, 1],
              }}
            >
              <StepCard step={step} index={i} />
              {i < steps.length - 1 && (
                <div className="mt-6 flex justify-center">
                  <ArrowDown className="h-5 w-5 text-royal/30" />
                </div>
              )}
            </motion.div>
          ))}
        </div>

        <div className="hidden lg:block">
          <ScrollStack
            useWindowScroll
            itemDistance={0}
            itemStackDistance={44}
            stackPosition="15%"
            scaleEndPosition="6%"
            baseScale={0.85}
            itemScale={0.03}
          >
            {steps.map((step, i) => (
              <ScrollStackItem key={step.title}>
                <StepCard step={step} index={i} />
              </ScrollStackItem>
            ))}
          </ScrollStack>
        </div>
      </div>
    </section>
  );
}
