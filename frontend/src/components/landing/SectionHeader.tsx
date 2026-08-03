// @ts-nocheck
import { motion } from "framer-motion";
import type { ReactNode } from "react";

interface SectionHeaderProps {
  eyebrow: string;
  title: ReactNode;
  subtitle?: string;
  className?: string;
}

export function SectionHeader({
  eyebrow,
  title,
  subtitle,
  className = "",
}: SectionHeaderProps) {
  return (
    <motion.div
      className={`mb-14 text-center ${className}`}
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
    >
      <p className="mb-3 text-xs font-bold uppercase tracking-widest text-royal">
        {eyebrow}
      </p>
      <h2 className="font-display text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl dark:text-dark-text">
        {title}
      </h2>
      {subtitle && (
        <p className="mx-auto mt-4 max-w-2xl text-slate-500 dark:text-dark-muted">
          {subtitle}
        </p>
      )}
    </motion.div>
  );
}
