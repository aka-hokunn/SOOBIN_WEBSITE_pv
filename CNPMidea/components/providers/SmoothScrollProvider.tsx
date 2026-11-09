"use client";

import React, { useEffect, useRef } from "react";
import { ReactLenis, useLenis } from "lenis/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import SplitType from "split-type";

gsap.registerPlugin(ScrollTrigger, useGSAP);

interface SmoothScrollProviderProps {
  children: React.ReactNode;
}

/**
 * SmoothScrollProvider (Rule #1 & #2 of antigravityrules.md)
 * - Wraps the application with Lenis (`lenis/react`)
 * - Synchronizes directly with `gsap.ticker` and `ScrollTrigger.update`
 * - Uses `useGSAP` + `SplitType` for character/word reveals and pinned runway sections
 */
export function SmoothScrollProvider({ children }: SmoothScrollProviderProps) {
  const lenisRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function update(time: number) {
      lenisRef.current?.lenis?.raf(time * 1000);
    }
    gsap.ticker.add(update);
    gsap.ticker.lagSmoothing(0);

    return () => {
      gsap.ticker.remove(update);
    };
  }, []);

  useLenis(() => {
    ScrollTrigger.update();
  });

  useGSAP(
    () => {
      const headings = gsap.utils.toArray<HTMLElement>("[data-split-text]");
      headings.forEach((heading) => {
        const split = new SplitType(heading, { types: "words,chars" });
        gsap.fromTo(
          split.chars,
          { opacity: 0, y: 28, rotateX: -75 },
          {
            opacity: 1,
            y: 0,
            rotateX: 0,
            stagger: 0.018,
            duration: 0.75,
            ease: "power3.out",
            scrollTrigger: {
              trigger: heading,
              start: "top 88%",
              toggleActions: "play none none reverse",
            },
          }
        );
      });
    },
    { scope: containerRef }
  );

  return (
    <ReactLenis
      ref={lenisRef}
      root
      options={{
        autoRaf: false,
        lerp: 0.085,
        duration: 1.2,
        smoothWheel: true,
      }}
    >
      <div ref={containerRef}>{children}</div>
    </ReactLenis>
  );
}

