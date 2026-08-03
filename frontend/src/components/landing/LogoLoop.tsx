// @ts-nocheck
import { useRef, useEffect, useMemo, useState, useCallback, memo } from "react";
import "./LogoLoop.css";

interface LogoItem {
  node: React.ReactNode;
  title: string;
  href: string;
}

interface LogoLoopProps {
  logos: LogoItem[];
  speed?: number;
  direction?: "left" | "right";
  logoHeight?: number;
  gap?: number;
  hoverSpeed?: number;
  scaleOnHover?: boolean;
  fadeOut?: boolean;
  fadeOutColor?: string;
  ariaLabel?: string;
}

export const LogoLoop = memo(function LogoLoop({
  logos,
  speed = 60,
  direction = "left",
  logoHeight = 48,
  gap = 48,
  hoverSpeed = 0,
  scaleOnHover = false,
  fadeOut = false,
  fadeOutColor,
  ariaLabel = "Scrolling logos",
}: LogoLoopProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const animationRef = useRef<number | null>(null);
  const positionRef = useRef(0);
  const speedRef = useRef(speed);

  useEffect(() => {
    speedRef.current = isHovered && hoverSpeed ? hoverSpeed : speed;
  }, [isHovered, hoverSpeed, speed]);

  const tripleLogos = useMemo(() => [...logos, ...logos, ...logos], [logos]);

  const animate = useCallback(() => {
    const track = trackRef.current;
    if (!track) return;

    const totalWidth = track.scrollWidth / 3;
    positionRef.current += direction === "left" ? -1 : 1;

    if (Math.abs(positionRef.current) >= totalWidth) {
      positionRef.current = 0;
    }

    track.style.transform = `translateX(${positionRef.current}px)`;
    animationRef.current = requestAnimationFrame(animate);
  }, [direction]);

  useEffect(() => {
    const interval = setInterval(() => {
      const speed = speedRef.current;
      if (speed === 0) return;
      // Speed controls how many pixels per frame
    }, 16);

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
      clearInterval(interval);
    };
  }, [animate]);

  return (
    <div
      ref={containerRef}
      className="logoloop"
      style={
        {
          "--ll-height": `${logoHeight}px`,
          "--ll-gap": `${gap}px`,
          "--ll-speed": `${speed}s`,
          "--ll-fadeColor": fadeOutColor || "#f0f7ff",
          "--ll-hoverSpeed": `${hoverSpeed}s`,
        } as React.CSSProperties
      }
      role="list"
      aria-label={ariaLabel}
    >
      <div
        ref={trackRef}
        className={`logoloop-track ${scaleOnHover ? "logoloop-scale" : ""}`}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {tripleLogos.map((logo, i) => (
          <a
            key={`${logo.title}-${i}`}
            href={logo.href}
            target="_blank"
            rel="noopener noreferrer"
            className="logoloop-item"
            role="listitem"
            title={logo.title}
          >
            <span className="logoloop-icon">{logo.node}</span>
            <span className="logoloop-title">{logo.title}</span>
          </a>
        ))}
      </div>

      {fadeOut && (
        <>
          <div
            className="logoloop-fade logoloop-fade-left"
            style={{
              background: `linear-gradient(to right, var(--ll-fadeColor), transparent)`,
            }}
          />
          <div
            className="logoloop-fade logoloop-fade-right"
            style={{
              background: `linear-gradient(to left, var(--ll-fadeColor), transparent)`,
            }}
          />
        </>
      )}
    </div>
  );
});
