// @ts-nocheck
import { useEffect, useState } from "react";
import Ribbons from "@/components/reactbits/Ribbons";

function useIsDark() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const update = () =>
      setDark(document.documentElement.classList.contains("dark"));
    update();
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  return dark;
}

export function RibbonsBackground() {
  const dark = useIsDark();
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduceMotion(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReduceMotion(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  if (reduceMotion) return null;

  return (
    <div className="pointer-events-none fixed inset-0 z-0 opacity-60" aria-hidden="true">
      <Ribbons
        colors={dark ? ["#60a5fa", "#a78bfa", "#34d399"] : ["#2563eb", "#7c3aed", "#0d9488"]}
        baseSpring={0.035}
        baseFriction={0.9}
        baseThickness={22}
        offsetFactor={0.06}
        maxAge={400}
        pointCount={50}
        speedMultiplier={0.6}
        enableFade
        enableShaderEffect
        effectAmplitude={2}
        backgroundColor={[0, 0, 0, 0]}
      />
    </div>
  );
}
