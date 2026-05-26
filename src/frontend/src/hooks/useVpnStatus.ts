/**
 * useVpnStatus — polls /api/vpn/status every 30 seconds.
 *
 * Returns null while loading for the first time, or the latest status object.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { withBasePath } from '../utils/basePath';

export interface VpnStatus {
  status: string; // 'running' | 'stopped' | 'unknown' | 'not_configured' | 'unauthorized'
  message: string;
  connected: boolean;
  public_ip: string | null;
  country: string | null;
  city: string | null;
}

const POLL_INTERVAL_MS = 30_000;

export function useVpnStatus(enabled = true) {
  const [data, setData] = useState<VpnStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const resp = await fetch(withBasePath('/api/vpn/status'), { credentials: 'include' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const result = (await resp.json()) as VpnStatus;
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    void fetchStatus();

    timerRef.current = setInterval(() => {
      void fetchStatus();
    }, POLL_INTERVAL_MS);

    return () => {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current);
      }
    };
  }, [enabled, fetchStatus]);

  return { data, loading, error, refresh: fetchStatus };
}
