// @ts-nocheck
import { BookOpenCheck, ArrowRight, Sparkles } from "lucide-react";
import { DashboardMockup } from "./DashboardMockup";
import { TextType } from "../reactbits/TextType";
import { TextPressure } from "../reactbits/TextPressure";
import { LightRaysHero } from "./LightRaysHero";
export function Hero() {
  return (
    <section className="relative overflow-hidden pt-24 pb-0 sm:pt-28 lg:pt-10">
      <LightRaysHero />
      <div className="relative z-10 mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-16">
          {/* Left: headline block */}
          <div className="text-center lg:text-left">
            <span className="clay-chip mb-6 inline-flex items-center gap-2 px-4 py-1.5 text-xs font-bold uppercase tracking-wider text-royal">
              <Sparkles className="h-3.5 w-3.5" />
              Powered by CockroachDB + Multi-Agent AI
            </span>

            <h1 className="font-display text-5xl font-extrabold leading-[1.08] tracking-tight text-slate-900 sm:text-6xl lg:text-7xl dark:text-dark-text">
              Your AI Study Companion That{" "}
              <TextPressure
                text="Actually
Remembers"
                as="span"
                fontSize="inherit"
                fontFamily="'Outfit', sans-serif"
                fontUrl=""
                textColor="#2563eb"
                width={false}
                weight={true}
                italic={false}
                flex={false}
              />
            </h1>

            <TextType
              as="p"
              className="mt-8 text-lg leading-relaxed text-slate-600 sm:text-xl dark:text-dark-muted"
              text={[
                "Upload slides. Remember more. Study smarter.",
                "Everything you need to study smarter.",
                "Your AI-powered study companion.",
              ]}
              typingSpeed={60}
              deletingSpeed={25}
              pauseDuration={2500}
              loop
              cursorCharacter="|"
              cursorBlinkDuration={0.4}
            />

            <div className="mt-8 flex flex-wrap items-center gap-4">
              <a href="/app" className="clay-btn gap-2 px-8 py-4 text-base">
                Start Learning Free
                <ArrowRight className="h-4 w-4" />
              </a>
              <a
                href="#study-hub"
                className="clay-btn-secondary gap-2 px-8 py-4 text-base"
              >
                <BookOpenCheck className="h-4 w-4" />
                Explore Study Hub
              </a>
            </div>
          </div>

          {/* Right: dashboard */}
          <div className="relative lg:mt-16">
            <DashboardMockup />
          </div>
        </div>
      </div>
    </section>
  );
}
