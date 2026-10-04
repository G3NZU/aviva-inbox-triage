import { useId, useRef } from "react";
import type { FocusEvent, MouseEvent, ReactNode, RefObject, ToggleEvent } from "react";
import Icon from "./Icon";

const HOVER_OPEN_MS = 300; // a short rest on the button opens it for mouse users
const HOVER_CLOSE_MS = 200; // grace time to move the pointer from the button onto the bubble

/**
 * Put the open bubble just below its button (above it near the bottom of the screen), kept 16 px inside the
 * window. It is positioned in page coordinates, so it scrolls with the page instead of floating.
 */
function place(button: HTMLElement, bubble: HTMLElement): void {
  const b = button.getBoundingClientRect();
  const left = Math.min(Math.max(16, b.left + b.width / 2 - bubble.offsetWidth / 2), innerWidth - bubble.offsetWidth - 16);
  const fitsBelow = b.bottom + 8 + bubble.offsetHeight <= innerHeight - 16;
  const top = fitsBelow ? b.bottom + 8 : b.top - 8 - bubble.offsetHeight;
  bubble.style.left = `${left + scrollX}px`;
  bubble.style.top = `${top + scrollY}px`;
}

/**
 * Mouse hover: open after a short rest, close shortly after the pointer leaves both the button and the bubble.
 * A click on a hover-opened bubble pins it open (it cancels the native toggle that would close it).
 */
function useHover(bubble: RefObject<HTMLSpanElement | null>) {
  const timer = useRef(0);
  const hoverOpened = useRef(false);
  const later = (ms: number, action: () => void) => { clearTimeout(timer.current); timer.current = setTimeout(action, ms); };
  const enter = (event: { pointerType: string }) => {
    if (event.pointerType !== "mouse") return;
    later(HOVER_OPEN_MS, () => {
      if (!bubble.current?.matches(":popover-open")) { bubble.current?.showPopover(); hoverOpened.current = true; }
    });
  };
  const leave = () => later(HOVER_CLOSE_MS, () => {
    if (hoverOpened.current) bubble.current?.hidePopover();
    hoverOpened.current = false;
  });
  const click = (event: MouseEvent) => {
    clearTimeout(timer.current);
    if (hoverOpened.current) { event.preventDefault(); hoverOpened.current = false; } // pin, do not toggle closed
  };
  return { enter, leave, click, stay: () => clearTimeout(timer.current) };
}

/**
 * The one help pattern: a small (i) button beside a label that opens a short definition. Click, tap, Enter or
 * Space toggle it; Esc or a click elsewhere closes it; a mouse can also open it by resting on it. Built on the
 * browser's popover, which keeps one bubble open at a time, draws it above everything (nothing clips it) and
 * tells screen readers whether it is open. The bubble is a <span>, so it may sit inside a paragraph or a label.
 * Keep it out of <summary> and headings (it would join their names). Props: the term and the definition text.
 */
export default function Explain({ term, children }: { term: string; children: ReactNode }) {
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const bubble = useRef<HTMLSpanElement>(null);
  const hover = useHover(bubble);
  const onToggle = (event: ToggleEvent<HTMLSpanElement>) => {
    if (event.newState === "open" && button.current && bubble.current) place(button.current, bubble.current);
  };
  const onBlur = (event: FocusEvent) => { // keyboard users: never leave a bubble covering the next control
    if (!bubble.current?.contains(event.relatedTarget as Node | null)) bubble.current?.hidePopover();
  };
  return (
    <>
      <button ref={button} type="button" popoverTarget={id} aria-label={`What "${term}" means`} onBlur={onBlur}
        onClick={hover.click} onPointerEnter={hover.enter} onPointerLeave={hover.leave}
        className="relative z-10 inline-grid size-6 shrink-0 place-items-center rounded-full text-ink-3 align-middle
          transition-colors duration-150 ease-standard hover:text-accent">
        <Icon name="info" className="size-4" />
      </button>
      <span ref={bubble} id={id} popover="auto" onToggle={onToggle} onPointerEnter={hover.stay} onPointerLeave={hover.leave}
        className="absolute inset-auto m-0 max-w-72 rounded-lg border-0 bg-ink p-3 text-left text-sm font-normal
          text-surface shadow-lg open:animate-tip-in motion-reduce:open:animate-fade-in">
        {children}
      </span>
    </>
  );
}
