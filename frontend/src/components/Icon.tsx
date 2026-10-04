/*
 * Icon shapes adapted from Lucide (https://lucide.dev), copied in as inline SVG instead of adding a package.
 * ISC License. Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part of Feather (MIT).
 * All other copyright (c) for Lucide are held by Lucide Contributors 2022.
 * Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is
 * hereby granted, provided that the above copyright notice and this permission notice appear in all copies.
 */
import type { ReactNode } from "react";

export type IconName =
  | "alert" | "clock" | "help" | "equal" | "info" | "minus" | "dashed" | "check"
  | "chevronRight" | "chevronLeft" | "chevronDown" | "paperclip" | "arrowRight" | "error" | "moon";

const SHAPES: Record<IconName, ReactNode> = {
  // P1's triangle is the only filled shape in the app, so P1 differs from P2 without relying on colour.
  alert: (<>
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" fill="currentColor" />
    <path d="M12 9v4M12 17h.01" stroke="white" />
  </>),
  clock: <><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></>,
  help: <><circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3M12 17h.01" /></>,
  equal: <path d="M5 9h14M5 15h14" />,
  info: <><circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" /></>,
  minus: <><circle cx="12" cy="12" r="10" /><path d="M8 12h8" /></>,
  dashed: <circle cx="12" cy="12" r="10" strokeDasharray="4 3" />,
  check: <path d="M20 6 9 17l-5-5" />,
  chevronRight: <path d="m9 18 6-6-6-6" />,
  chevronLeft: <path d="m15 18-6-6 6-6" />,
  chevronDown: <path d="m6 9 6 6 6-6" />,
  paperclip: <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />,
  arrowRight: <path d="M5 12h14m-7-7 7 7-7 7" />,
  error: <><circle cx="12" cy="12" r="10" /><path d="M12 8v4M12 16h.01" /></>,
  moon: <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />,
};

/**
 * A small line icon. Decorative: hidden from screen readers, because the text beside it always says
 * the same thing. Size and colour come from the className (e.g. "size-4 text-p1-mark").
 */
export default function Icon({ name, className = "size-4" }: { name: IconName; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true" focusable="false" className={`shrink-0 ${className}`}>
      {SHAPES[name]}
    </svg>
  );
}
