"use client";

import React from "react";
import { motion } from "motion/react";
import { cn } from "../../lib/utils";

/**
 * Aceternity UI — BentoGrid & BentoGridItem
 * Uses `motion/react` for hover micro-interactions and `layoutId` shared layout morphing.
 */
export const BentoGrid = ({
  className,
  children,
}: {
  className?: string;
  children?: React.ReactNode;
}) => {
  return (
    <div
      className={cn(
        "grid md:auto-rows-[19rem] grid-cols-1 md:grid-cols-3 gap-4 max-w-7xl mx-auto",
        className
      )}
    >
      {children}
    </div>
  );
};

export const BentoGridItem = ({
  className,
  title,
  description,
  header,
  icon,
  layoutId,
}: {
  className?: string;
  title?: string | React.ReactNode;
  description?: string | React.ReactNode;
  header?: React.ReactNode;
  icon?: React.ReactNode;
  layoutId?: string;
}) => {
  return (
    <motion.div
      layoutId={layoutId}
      whileHover={{ y: -6, scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
      transition={{ type: "spring", stiffness: 320, damping: 26 }}
      className={cn(
        "row-span-1 rounded-3xl group/bento hover:shadow-2xl transition duration-300 shadow-input p-5 bg-slate-900/80 border border-white/10 justify-between flex flex-col space-y-4 relative overflow-hidden backdrop-blur-xl",
        className
      )}
    >
      {header}
      <div className="group-hover/bento:translate-x-1.5 transition duration-200">
        {icon}
        <div className="font-extrabold text-white mb-1 mt-2 text-base">
          {title}
        </div>
        <div className="font-normal text-slate-300 text-xs leading-relaxed">
          {description}
        </div>
      </div>
    </motion.div>
  );
};

