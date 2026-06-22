"use client";

import { useEffect, useState } from "react";

// Counts whole seconds elapsed while `active` is true. The timer resets to 0
// whenever `active` flips to true again, or whenever `resetKey` changes (e.g. a
// new groupId / new retry attempt). Used to drive elapsed-time labels and the
// "taking longer than usual" slow-loading warning — never tied to real backend
// record counts (stage-based UI only).
export function useElapsedSeconds(active: boolean, resetKey?: unknown): number {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!active) {
      setSeconds(0);
      return;
    }
    setSeconds(0);
    const startedAt = Date.now();
    const interval = setInterval(() => {
      setSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [active, resetKey]);

  return seconds;
}
