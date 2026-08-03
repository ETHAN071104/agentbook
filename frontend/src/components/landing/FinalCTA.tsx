// @ts-nocheck
import { ArrowRight } from "lucide-react";
import { motion } from "framer-motion";

export function FinalCTA() {
  return (
    <section className="relative z-10 overflow-hidden bg-gradient-to-b from-royal/5 to-transparent px-4 py-24 sm:px-6 lg:px-8 dark:from-royal/10 dark:to-transparent">
      <div className="mx-auto max-w-4xl text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          <h2 className="font-display text-3xl font-extrabold tracking-tight text-slate-900 sm:text-5xl dark:text-dark-text">
            Ready to learn smarter?
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-lg text-slate-500 dark:text-dark-muted">
            Stop passively reading. Start actively learning. Create your free account today and
            turn every study session into real progress.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
            <a href="/app" className="clay-btn gap-2 px-8 py-4 text-base">
              Get Started Free
              <ArrowRight className="h-4 w-4" />
            </a>
            <a href="#features" className="clay-btn-secondary gap-2 px-8 py-4 text-base">
              Learn More
            </a>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
