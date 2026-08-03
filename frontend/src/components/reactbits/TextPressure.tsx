// @ts-nocheck
"use client";

import { useEffect, useRef, useMemo, type ElementType, type CSSProperties } from "react";

interface Point {
  x: number;
  y: number;
}

const dist = (a: Point, b: Point) => {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  return Math.sqrt(dx * dx + dy * dy);
};

const getAttr = (distance: number, maxDist: number, minVal: number, maxVal: number) => {
  const val = maxVal - Math.abs((maxVal * distance) / maxDist);
  return Math.max(minVal, val + minVal);
};

interface TextPressureProps {
  text?: string;
  fontFamily?: string;
  fontUrl?: string;
  width?: boolean;
  weight?: boolean;
  italic?: boolean;
  alpha?: boolean;
  flex?: boolean;
  stroke?: boolean;
  textColor?: string;
  strokeColor?: string;
  className?: string;
  style?: CSSProperties;
  fontSize?: number | string;
  as?: ElementType;
}

export function TextPressure({
  text = "Compressa",
  fontFamily = "Roboto Flex",
  fontUrl = "",
  width = true,
  weight = true,
  italic = true,
  alpha = false,
  flex = true,
  stroke = false,
  textColor = "#FFFFFF",
  strokeColor = "#FF0000",
  className = "",
  style,
  fontSize = 48,
  as: Tag = "h1",
}: TextPressureProps) {
  const titleRef = useRef<HTMLElement>(null);
  const spansRef = useRef<(HTMLSpanElement | null)[]>([]);

  const mouseRef = useRef({ x: 0, y: 0 });
  const cursorRef = useRef({ x: 0, y: 0 });

  const lines = text.split("\n");

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      cursorRef.current.x = e.clientX;
      cursorRef.current.y = e.clientY;
    };
    const handleTouchMove = (e: TouchEvent) => {
      const t = e.touches[0];
      cursorRef.current.x = t.clientX;
      cursorRef.current.y = t.clientY;
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("touchmove", handleTouchMove, { passive: true });

    if (titleRef.current) {
      const titleRect = titleRef.current.getBoundingClientRect();
      mouseRef.current.x = titleRect.left + titleRect.width / 2;
      mouseRef.current.y = titleRect.top + titleRect.height / 2;
      cursorRef.current.x = mouseRef.current.x;
      cursorRef.current.y = mouseRef.current.y;
    }

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("touchmove", handleTouchMove);
    };
  }, []);

  useEffect(() => {
    let rafId: number;
    const animate = () => {
      mouseRef.current.x += (cursorRef.current.x - mouseRef.current.x) / 15;
      mouseRef.current.y += (cursorRef.current.y - mouseRef.current.y) / 15;

      if (titleRef.current) {
        const titleRect = titleRef.current.getBoundingClientRect();
        const maxDist = titleRect.width / 2;

        spansRef.current.forEach((span) => {
          if (!span) return;

          const rect = span.getBoundingClientRect();
          const charCenter = {
            x: rect.x + rect.width / 2,
            y: rect.y + rect.height / 2,
          };

          const d = dist(mouseRef.current, charCenter);

          const wdth = width ? Math.floor(getAttr(d, maxDist, 25, 151)) : 100;
          const wght = weight ? Math.floor(getAttr(d, maxDist, 100, 900)) : 400;
          const italVal = italic ? getAttr(d, maxDist, 0, 1).toFixed(2) : "0";
          const alphaVal = alpha ? getAttr(d, maxDist, 0, 1).toFixed(2) : "1";

          const newVal = `"wght" ${wght}, "wdth" ${wdth}, "ital" ${italVal}`;

          if (span.style.fontVariationSettings !== newVal) {
            span.style.fontVariationSettings = newVal;
          }
          if (alpha && span.style.opacity !== alphaVal) {
            span.style.opacity = alphaVal;
          }
        });
      }

      rafId = requestAnimationFrame(animate);
    };

    animate();
    return () => cancelAnimationFrame(rafId);
  }, [width, weight, italic, alpha]);

  const styleElement = useMemo(() => {
    return (
      <style>{`
        ${fontUrl ? `@import url('${fontUrl}');` : ""}
        .tp-flex { display: inline-flex; gap: 0.05em; }
        .tp-stroke span { position: relative; color: ${textColor}; }
        .tp-stroke span::after {
          content: attr(data-char);
          position: absolute; left: 0; top: 0;
          color: transparent; z-index: -1;
          -webkit-text-stroke: 3px ${strokeColor};
        }
        .tp-title { color: ${textColor}; display: inline; }
      `}</style>
    );
  }, [fontUrl, textColor, strokeColor]);

  const dynamicClassName = [
    className,
    flex ? "tp-flex" : "",
    stroke ? "tp-stroke" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <>
      {styleElement}
      <Tag
        ref={titleRef as any}
        className={`tp-title ${dynamicClassName}`}
        style={
          {
          fontFamily,
          lineHeight: 1,
            margin: 0,
            userSelect: "none",
            ...style,
          } as CSSProperties
        }
      >
        {(() => {
          let spanIdx = 0;
          return lines.flatMap((line, lineIdx) => {
            const spans = line.split("").map((char, charIdx) => (
              <span
                key={`${lineIdx}-${charIdx}`}
                ref={(el) => {
                  spansRef.current[spanIdx] = el;
                  spanIdx++;
                }}
                data-char={char}
                style={{
                  display: "inline",
                  color: stroke ? undefined : textColor,
                  width: char === " " ? "0.3em" : undefined,
                }}
              >
                {char === " " ? "\u00A0" : char}
              </span>
            ));
            if (lineIdx < lines.length - 1) {
              spans.push(<br key={`br-${lineIdx}`} />);
            }
            return spans;
          });
        })()}
      </Tag>
    </>
  );
}
