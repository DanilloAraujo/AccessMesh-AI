/**
 * useReducedMotion
 *
 * Returns `true` when the user's OS has `prefers-reduced-motion: reduce` set.
 * Components should conditionally disable or simplify animations when this is true.
 *
 * Works by reading the media-query once on mount and listening for changes
 * (e.g. user toggles the OS accessibility setting while the app is open).
 */
import { useEffect, useState } from 'react';

export function useReducedMotion(): boolean {
    const query = '(prefers-reduced-motion: reduce)';

    const [prefersReduced, setPrefersReduced] = useState<boolean>(
        () => typeof window !== 'undefined' && window.matchMedia(query).matches,
    );

    useEffect(() => {
        if (typeof window === 'undefined') return;
        const mql = window.matchMedia(query);
        const handler = (e: MediaQueryListEvent) => setPrefersReduced(e.matches);
        mql.addEventListener('change', handler);
        return () => mql.removeEventListener('change', handler);
    }, []);

    return prefersReduced;
}
