import { useEffect, useMemo, useRef, useState } from 'react';

type CountUpProps = {
  to: number;
  durationMs?: number;
  suffix?: string;
  prefix?: string;
  /** Intersection threshold for triggering (0..1). Default 0.35 */
  threshold?: number;
  /** Start value. Default 0 */
  from?: number;
};

function easeOutCubic(t: number) {
  return 1 - Math.pow(1 - t, 3);
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!mq) return;
    const onChange = () => setReduced(Boolean(mq.matches));
    onChange();
    mq.addEventListener?.('change', onChange);
    return () => mq.removeEventListener?.('change', onChange);
  }, []);

  return reduced;
}

/**
 * Count-up animation that starts once when the element enters viewport.
 * No external deps: IntersectionObserver + requestAnimationFrame.
 */
export function CountUp({
  to,
  durationMs = 1100,
  suffix = '',
  prefix = '',
  threshold = 0.35,
  from = 0,
}: CountUpProps) {
  const prefersReducedMotion = usePrefersReducedMotion();
  const ref = useRef<HTMLSpanElement | null>(null);
  const [started, setStarted] = useState(false);
  const [value, setValue] = useState(from);

  const clampedDuration = useMemo(() => Math.max(200, durationMs), [durationMs]);

  useEffect(() => {
    if (started) return;
    const el = ref.current;
    if (!el) return;

    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setStarted(true);
          obs.disconnect();
        }
      },
      { threshold },
    );

    obs.observe(el);
    return () => obs.disconnect();
  }, [started, threshold]);

  useEffect(() => {
    if (!started) return;
    if (prefersReducedMotion) {
      setValue(to);
      return;
    }

    const start = performance.now();
    const delta = to - from;

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / clampedDuration);
      const eased = easeOutCubic(t);
      setValue(Math.round(from + delta * eased));
      if (t < 1) requestAnimationFrame(tick);
    };

    requestAnimationFrame(tick);
  }, [started, prefersReducedMotion, to, from, clampedDuration]);

  return (
    <span ref={ref} className="tabular-nums">
      {prefix}
      {value}
      {suffix}
    </span>
  );
}

