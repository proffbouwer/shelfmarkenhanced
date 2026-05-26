/**
 * VpnStatusWidget — shows live VPN connection status in the VPN settings tab.
 * Polls /api/vpn/status and renders a compact status card.
 */

import { useVpnStatus } from '../../../hooks/useVpnStatus';
import type { CustomSettingsFieldRendererProps } from './types';

export function VpnStatusWidget(_props: CustomSettingsFieldRendererProps) {
  const { data, loading, refresh } = useVpnStatus(true);

  if (loading && !data) {
    return (
      <div className="flex items-center gap-2 text-sm opacity-60">
        <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-gray-400" />
        Checking VPN status…
      </div>
    );
  }

  if (!data) {
    return (
      <p className="text-sm opacity-60">
        Unable to reach VPN status endpoint.
      </p>
    );
  }

  const { connected, status, public_ip, country, city, message } = data;

  const isNotConfigured = status === 'not_configured';
  const isUnauthorized = status === 'unauthorized';

  const dotColor = isNotConfigured || isUnauthorized
    ? 'bg-gray-400'
    : connected
      ? 'bg-emerald-500'
      : 'bg-red-500';

  const labelColor = isNotConfigured || isUnauthorized
    ? 'text-gray-500 dark:text-gray-400'
    : connected
      ? 'text-emerald-600 dark:text-emerald-400'
      : 'text-red-500 dark:text-red-400';

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className={`inline-block h-2.5 w-2.5 rounded-full ${dotColor} ${connected ? 'animate-pulse' : ''}`} />
        <span className={`text-sm font-medium ${labelColor}`}>
          {isNotConfigured
            ? 'Not configured'
            : isUnauthorized
              ? 'API auth required'
              : connected
                ? 'Connected'
                : 'Disconnected'}
        </span>
        <button
          type="button"
          onClick={() => void refresh()}
          className="ml-auto text-xs opacity-50 hover:opacity-80"
          aria-label="Refresh VPN status"
        >
          ↻ Refresh
        </button>
      </div>

      {message && !connected && !isNotConfigured && (
        <p className="text-xs opacity-60">{message}</p>
      )}

      {connected && (public_ip || country) && (
        <div className="rounded-lg border border-(--border-muted) bg-(--bg-soft) px-3 py-2 text-xs space-y-0.5">
          {public_ip && (
            <p><span className="opacity-60">Public IP: </span><span className="font-mono">{public_ip}</span></p>
          )}
          {(country || city) && (
            <p><span className="opacity-60">Location: </span>{[city, country].filter(Boolean).join(', ')}</p>
          )}
        </div>
      )}
    </div>
  );
}
