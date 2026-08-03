// @ts-nocheck
import { LogoLoop } from "./LogoLoop";
import { SiReact, SiFastapi, SiCockroachlabs, SiPython, SiTypescript } from "react-icons/si";
import { RiBubbleChartFill } from "react-icons/ri";
import { motion } from "framer-motion";
import { SectionHeader } from "./SectionHeader";

const techLogos = [
  { node: <SiReact />, title: "React 19", href: "https://react.dev" },
  { node: <SiFastapi />, title: "FastAPI", href: "https://fastapi.tiangolo.com" },
  { node: <SiCockroachlabs />, title: "CockroachDB", href: "https://www.cockroachlabs.com" },
  { node: <RiBubbleChartFill />, title: "Vector Search", href: "#" },
  { node: <SiPython />, title: "Python", href: "https://www.python.org" },
  { node: <SiTypescript />, title: "TypeScript", href: "https://www.typescriptlang.org" },
];

export function TechStack() {
  return (
    <section id="technology" className="relative z-10 px-4 py-24 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl text-center">
        <SectionHeader
          className="mb-16"
          eyebrow="Built with"
          title="The stack behind the platform"
          subtitle="Frontend, orchestration, persistence, vector retrieval, and AI work together in one unified system."
        />

        <motion.div
          className="mx-auto max-w-5xl"
          style={{ height: "120px", position: "relative", overflow: "hidden" }}
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
        >
          <LogoLoop
            logos={techLogos}
            speed={80}
            direction="left"
            logoHeight={56}
            gap={64}
            hoverSpeed={0}
            scaleOnHover
            ariaLabel="Agentbook technology stack"
          />
        </motion.div>
      </div>
    </section>
  );
}
