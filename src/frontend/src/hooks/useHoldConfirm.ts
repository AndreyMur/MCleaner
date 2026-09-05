import { useEffect, useState } from "react";

/**
 * Safety hold: a destructive confirmation button stays locked for `seconds`
 * seconds after the dialog opens so the user has time to cancel. Returns
 * `held` = true once the delay elapsed and the action may proceed.
 */
export function useHoldConfirm(seconds = 5): { held: boolean; remaining: number } {
  const [remaining, setRemaining] = useState(seconds);

  useEffect(() => {
    setRemaining(seconds);
    if (seconds <= 0) return;
    const startedAt = Date.now();
    const interval = window.setInterval(() => {
      const left = seconds - Math.floor((Date.now() - startedAt) / 1000);
      setRemaining(Math.max(0, left));
      if (left <= 0) window.clearInterval(interval);
    }, 200);
    return () => window.clearInterval(interval);
  }, [seconds]);

  return { held: remaining <= 0, remaining };
}
