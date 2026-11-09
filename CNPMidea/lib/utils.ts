import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Standard Aceternity UI & Magic UI class merging utility.
 * Combines conditional classes via `clsx` and resolves Tailwind conflicts via `tailwind-merge`.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

