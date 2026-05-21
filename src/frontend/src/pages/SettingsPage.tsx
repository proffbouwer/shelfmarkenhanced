/**
 * SettingsPage — full-route settings UI at /settings/:tab
 *
 * Reuses the same SettingsSidebar + SettingsContent + useSettings hook
 * that SettingsModal uses, but rendered as a proper page rather than an
 * overlay modal.  Tab selection is reflected in the URL so bookmarks and
 * back-navigation work correctly.
 */

import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { useSearchMode } from '../contexts/SearchModeContext';
import { useMediaQuery } from '../hooks/useMediaQuery';
import { useMountEffect } from '../hooks/useMountEffect';
import { useSettings } from '../hooks/useSettings';
import { getAdminSettingsOverridesSummary, getSettingsTab } from '../services/api';
import { SettingsContent } from '../components/settings/SettingsContent';
import { SettingsHeader } from '../components/settings/SettingsHeader';
import { SettingsSidebar } from '../components/settings/SettingsSidebar';

function getStringValue(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback;
}

function getStringArrayValue(value: unknown): string[] {
  return Array.isArray(value) && value.every((e) => typeof e === 'string') ? value : [];
}

function getBooleanValue(value: unknown): boolean {
  return typeof value === 'boolean' ? value : false;
}

interface SettingsPageProps {
  authMode: string;
  onShowToast?: (message: string, type: 'success' | 'error' | 'info') => void;
  onSettingsSaved?: () => void;
  onRefreshAuth?: () => Promise<void>;
}

export const SettingsPage = ({
  authMode,
  onShowToast,
  onSettingsSaved,
  onRefreshAuth,
}: SettingsPageProps) => {
  const navigate = useNavigate();
  const { tab: urlTab } = useParams<{ tab: string }>();
  const isMobile = useMediaQuery('(max-width: 767px)');
  const [showMobileDetail, setShowMobileDetail] = useState(false);
  const [securityAccessError, setSecurityAccessError] = useState<string | null>(null);
  const [tabOverrideSummaries, setTabOverrideSummaries] = useState<
    Record<
      string,
      Record<string, { count: number; users: Array<{ userId: number; username: string; value: unknown }> }>
    >
  >({});
  const overrideSummaryRequestIdRef = useRef(0);

  const {
    tabs,
    groups,
    isLoading,
    error,
    selectedTab,
    setSelectedTab,
    values,
    updateValue,
    hasChanges,
    saveTab,
    executeAction,
    isSaving,
  } = useSettings();

  const { isUniversalMode } = useSearchMode();

  // Sync URL param → selectedTab on mount and when URL changes
  useEffect(() => {
    if (urlTab && urlTab !== selectedTab) {
      setSelectedTab(urlTab);
    } else if (!urlTab && tabs.length > 0 && !selectedTab) {
      const firstTab = tabs[0].name;
      navigate(`/settings/${firstTab}`, { replace: true });
    }
  }, [urlTab, tabs, selectedTab, setSelectedTab, navigate]);

  const refreshOverrideSummaryForTab = useCallback(async (tabName: string) => {
    const requestId = ++overrideSummaryRequestIdRef.current;
    try {
      const data = await getAdminSettingsOverridesSummary(tabName);
      if (overrideSummaryRequestIdRef.current !== requestId) return;
      setTabOverrideSummaries((prev) => ({ ...prev, [tabName]: data.keys || {} }));
    } catch {
      if (overrideSummaryRequestIdRef.current !== requestId) return;
      setTabOverrideSummaries((prev) => ({ ...prev, [tabName]: {} }));
    }
  }, []);

  // Refresh overrides + security access check whenever tab changes
  useMountEffect(() => {
    if (!selectedTab) return;
    let cancelled = false;
    void refreshOverrideSummaryForTab(selectedTab);

    if (selectedTab !== 'security') {
      setSecurityAccessError(null);
    } else {
      void getSettingsTab('security')
        .then(() => { if (!cancelled) setSecurityAccessError(null); })
        .catch((err) => {
          if (cancelled) return;
          const msg = err instanceof Error ? err.message : 'Failed to load security settings';
          setSecurityAccessError(msg.toLowerCase().includes('admin access required') ? msg : null);
        });
    }
    return () => { cancelled = true; };
  });

  const handleSelectTab = useCallback(
    (tabName: string) => {
      setSelectedTab(tabName);
      navigate(`/settings/${tabName}`);
      if (isMobile) setShowMobileDetail(true);
    },
    [isMobile, navigate, setSelectedTab],
  );

  const handleBack = useCallback(() => setShowMobileDetail(false), []);

  const handleClose = useCallback(() => navigate('/'), [navigate]);

  const handleRefreshCurrentTabOverrideSummary = useCallback(() => {
    if (selectedTab) void refreshOverrideSummaryForTab(selectedTab);
  }, [selectedTab, refreshOverrideSummaryForTab]);

  const handleSave = useCallback(async () => {
    if (!selectedTab) return;
    const result = await saveTab(selectedTab);
    if (result.success) {
      void refreshOverrideSummaryForTab(selectedTab);
      onShowToast?.(result.message, 'success');
      onSettingsSaved?.();
      if (result.requiresRestart) {
        setTimeout(() => onShowToast?.('Some settings require a container restart to take effect', 'info'), 500);
      }
    } else {
      onShowToast?.(result.message, 'error');
    }
  }, [selectedTab, saveTab, onShowToast, onSettingsSaved, refreshOverrideSummaryForTab]);

  const handleAction = useCallback(
    async (actionKey: string) => {
      if (!selectedTab) return { success: false, message: 'No tab selected' };

      if (selectedTab === 'security' && actionKey === 'open_users_tab') {
        handleSelectTab('users');
        return { success: true, message: 'Opening Users tab...' };
      }

      const result = await executeAction(selectedTab, actionKey);
      if (result.success) void refreshOverrideSummaryForTab(selectedTab);
      return result;
    },
    [selectedTab, executeAction, handleSelectTab, refreshOverrideSummaryForTab],
  );

  const handleFieldChange = useCallback(
    (key: string, value: unknown) => {
      if (!selectedTab) return;
      updateValue(selectedTab, key, value);

      if (selectedTab === 'security') {
        const tabValues = values[selectedTab] || {};
        const currentScopes = getStringArrayValue(tabValues['OIDC_SCOPES']);

        if (key === 'OIDC_USE_ADMIN_GROUP') {
          const groupClaim = getStringValue(tabValues['OIDC_GROUP_CLAIM'], 'groups');
          if (value === true && !currentScopes.includes(groupClaim)) {
            updateValue(selectedTab, 'OIDC_SCOPES', [...currentScopes, groupClaim]);
          } else if (value === false) {
            updateValue(selectedTab, 'OIDC_SCOPES', currentScopes.filter((s) => s !== groupClaim));
          }
        }

        if (key === 'OIDC_GROUP_CLAIM' && typeof value === 'string') {
          if (getBooleanValue(tabValues['OIDC_USE_ADMIN_GROUP'])) {
            const oldClaim = getStringValue(tabValues['OIDC_GROUP_CLAIM'], 'groups');
            const newScopes = currentScopes.filter((s) => s !== oldClaim);
            if (value && !newScopes.includes(value)) newScopes.push(value);
            updateValue(selectedTab, 'OIDC_SCOPES', newScopes);
          }
        }
      }
    },
    [selectedTab, updateValue, values],
  );

  const currentTabHasChanges = useMemo(
    () => (selectedTab ? hasChanges(selectedTab) : false),
    [selectedTab, hasChanges],
  );

  const currentTab = tabs.find((t) => t.name === selectedTab);
  const currentTabDisplayName = currentTab?.displayName || 'Settings';
  const selectedAuthMethod = values.security?.AUTH_METHOD;
  const usersAuthMode = typeof selectedAuthMethod === 'string' ? selectedAuthMethod : authMode;

  // ── Loading state ──────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center" style={{ background: 'var(--bg)' }}>
        <div className="flex items-center gap-3">
          <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span>Loading settings...</span>
        </div>
      </div>
    );
  }

  // ── Error state ────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4" style={{ background: 'var(--bg)' }}>
        <p className="text-sm text-red-500">{error}</p>
        <button
          type="button"
          onClick={handleClose}
          className="rounded-lg border border-(--border-muted) bg-(--bg-soft) px-4 py-2 text-sm font-medium transition-colors hover:bg-(--hover-surface)"
        >
          Go back
        </button>
      </div>
    );
  }

  const currentTabContent = currentTab ? (
    selectedTab === 'security' && securityAccessError ? (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8">
        <p className="text-sm opacity-60">{securityAccessError}</p>
      </div>
    ) : (
      <SettingsContent
        tab={currentTab}
        values={values[currentTab.name] || {}}
        onChange={handleFieldChange}
        onSave={handleSave}
        onAction={handleAction}
        isSaving={isSaving}
        hasChanges={currentTabHasChanges}
        isUniversalMode={isUniversalMode}
        overrideSummary={tabOverrideSummaries[currentTab.name]}
        customFieldContext={{
          authMode: usersAuthMode,
          onShowToast,
          onRefreshOverrideSummary: handleRefreshCurrentTabOverrideSummary,
          onRefreshAuth,
          onSettingsSaved,
        }}
      />
    )
  ) : null;

  // ── Mobile layout ──────────────────────────────────────────────────────────
  if (isMobile) {
    return (
      <div className="flex h-screen flex-col" style={{ background: 'var(--bg)' }}>
        {!showMobileDetail ? (
          <>
            <SettingsHeader title="Settings" onClose={handleClose} />
            <SettingsSidebar
              tabs={tabs}
              groups={groups}
              selectedTab={selectedTab}
              onSelectTab={handleSelectTab}
              mode="list"
            />
          </>
        ) : (
          <>
            <SettingsHeader
              title={currentTabDisplayName}
              showBack
              onBack={handleBack}
              onClose={handleClose}
            />
            {currentTabContent}
          </>
        )}
      </div>
    );
  }

  // ── Desktop layout ─────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen flex-col" style={{ background: 'var(--bg)' }}>
      <SettingsHeader title="Settings" onClose={handleClose} />
      <div className="flex min-h-0 flex-1">
        <SettingsSidebar
          tabs={tabs}
          groups={groups}
          selectedTab={selectedTab}
          onSelectTab={handleSelectTab}
          mode="sidebar"
        />
        {currentTabContent ?? (
          <div className="flex flex-1 items-center justify-center text-sm opacity-60">
            Select a category to configure
          </div>
        )}
      </div>
    </div>
  );
};
