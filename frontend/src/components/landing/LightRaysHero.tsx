// @ts-nocheck
import { useEffect, useState } from "react";
import LightRays from "@/components/reactbits/LightRays";

export function LightRaysHero() {
  const [reducedMotion, setReducedMotion] = useState(false);
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener("change", onChange);

    const observer = new MutationObserver(() => {
      setDark(document.documentElement.classList.contains("dark"));
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

    return () => {
      mq.removeEventListener("change", onChange);
      observer.disconnect();
    };
  }, []);

  if (reducedMotion) return null;

  return (
    <div className="pointer-events-none absolute inset-0 z-0 opacity-80" aria-hidden="true">
      <LightRays
        raysOrigin="top-center"
        raysColor={dark ? "#60a5fa" : "#2563eb"}
        raysSpeed={1.2}
        lightSpread={0.6}
        rayLength={1.4}
        pulsating
        fadeDistance={0.9}
        saturation={0.8}
        followMouse
        mouseInfluence={0.08}
        noiseAmount={0.08}
        distortion={0.03}
      />
    </div>
  );
}
