/**
 * UsersPage — full-route screen at /users for managing all users.
 *
 * Features:
 * - Full user list with create / edit / delete actions
 * - Force re-login per user (invalidates active sessions)
 * - User stats (downloads, last login) shown in edit panel
 * - Uses the same hooks/components as the Settings → Users tab
 */

import { useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

import {
  canCreateLocalUsersForAuthMode,
  UserListView,
  UserOverridesView,
  useUserForm,
  useUserMutations,
  useUsersFetch,
  useUsersPanelState,
} from '../components/settings/users';
import type { AdminUser } from '../services/api';

interface UsersPageProps {
  authMode: string;
  onShowToast?: (message: string, type: 'success' | 'error' | 'info') => void;
  onRefreshAuth?: () => void;
}

export function UsersPage({ authMode, onShowToast, onRefreshAuth }: UsersPageProps) {
  const navigate = useNavigate();
  const { route, openCreate, openEdit, openEditOverrides, backToList } = useUsersPanelState();
  const activeEditRequestIdRef = useRef(0);

  const { users, loading, loadError, fetchUsers, fetchUserEditContext } = useUsersFetch({
    onShowToast,
  });

  const {
    createForm,
    setCreateForm,
    resetCreateForm,
    editingUser,
    setEditingUser,
    editPassword,
    setEditPassword,
    editPasswordConfirm,
    setEditPasswordConfirm,
    downloadDefaults,
    deliveryPreferences,
    searchPreferences,
    notificationPreferences,
    isUserOverridable,
    userSettings,
    setUserSettings,
    hasUserSettingsChanges,
    beginEditing,
    applyUserEditContext,
    resetEditContext,
    clearEditState,
    userOverridableSettings,
  } = useUserForm();

  const {
    creating,
    saving,
    deletingUserId,
    syncingCwa,
    forcingLogoutUserId,
    createUser,
    saveEditedUser,
    deleteUser,
    syncCwaUsers,
    forceLogout,
  } = useUserMutations({
    onShowToast,
    fetchUsers,
    users,
    createForm,
    resetCreateForm,
    editingUser,
    editPassword,
    editPasswordConfirm,
    userSettings,
    userOverridableSettings,
    deliveryPreferences,
    searchPreferences,
    notificationPreferences,
    onEditSaveSuccess: clearEditState,
  });

  const invalidateEditContextRequest = useCallback(() => {
    activeEditRequestIdRef.current += 1;
  }, []);

  const startEditing = async (user: AdminUser) => {
    const requestId = activeEditRequestIdRef.current + 1;
    activeEditRequestIdRef.current = requestId;
    beginEditing(user);
    try {
      const context = await fetchUserEditContext(user.id);
      if (activeEditRequestIdRef.current !== requestId) return;
      applyUserEditContext(context);
    } catch {
      if (activeEditRequestIdRef.current !== requestId) return;
      resetEditContext();
    }
  };

  const canCreateLocalUsers = canCreateLocalUsersForAuthMode(authMode || 'none');
  const effectiveRouteKind =
    route.kind === 'create' && !canCreateLocalUsers ? 'list' : route.kind;
  const activeEditUserId = route.kind === 'edit' ? route.userId : null;
  const needsLocalAdmin = !users.some((u) => u.role === 'admin' && u.auth_source === 'builtin');

  const handleBackToList = () => {
    invalidateEditContextRequest();
    clearEditState();
    backToList();
  };

  const handleCancelCreate = () => {
    resetCreateForm();
    backToList();
  };

  const handleCreate = async () => {
    if (!canCreateLocalUsers) return;
    const ok = await createUser();
    if (ok) {
      void onRefreshAuth?.();
      backToList();
    }
  };

  const handleSaveUserEdit = useCallback(async () => {
    const ok = await saveEditedUser({ includeSettings: false });
    if (ok) backToList();
  }, [backToList, saveEditedUser]);

  const handleSaveUserOverrides = useCallback(async () => {
    await saveEditedUser({ includeProfile: false, includePassword: false, includeSettings: true });
    backToList();
  }, [backToList, saveEditedUser]);

  const handleOpenOverrides = () => {
    if (editingUser) openEditOverrides(editingUser.id);
  };

  const handleEdit = async (user: AdminUser) => {
    openEdit(user.id);
    await startEditing(user);
  };

  const handleSyncCwa = async () => {
    await syncCwaUsers();
  };

  const handleDeleteUser = useCallback(
    async (userId: number) => {
      const ok = await deleteUser(userId);
      if (ok) void onRefreshAuth?.();
      return ok;
    },
    [deleteUser, onRefreshAuth],
  );

  const handleBackToEdit = () => {
    if (editingUser) {
      openEdit(editingUser.id);
      return;
    }
    backToList();
  };

  if (effectiveRouteKind === 'edit-overrides') {
    if (!editingUser || (route.kind === 'edit-overrides' && editingUser.id !== route.userId)) {
      return (
        <div className="flex min-h-[60vh] items-center justify-center">
          <p className="text-sm opacity-60">Loading user details...</p>
        </div>
      );
    }
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <button
          type="button"
          onClick={handleBackToEdit}
          className="mb-6 flex items-center gap-1.5 text-sm text-sky-600 hover:underline dark:text-sky-400"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            className="h-4 w-4"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
          </svg>
          Back to user
        </button>
        <UserOverridesView
          embedded={false}
          hasChanges={hasUserSettingsChanges}
          onBack={handleBackToEdit}
          deliveryPreferences={deliveryPreferences}
          searchPreferences={searchPreferences}
          notificationPreferences={notificationPreferences}
          isUserOverridable={isUserOverridable}
          userSettings={userSettings}
          setUserSettings={setUserSettings}
          usersTab={undefined}
          globalUsersSettingsValues={{}}
          onTestNotificationRoutes={async () => ({ success: false, message: 'Not available here' })}
        />
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={handleBackToEdit}
            className="rounded-lg border border-(--border-muted) px-4 py-2 text-sm font-medium"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleSaveUserOverrides()}
            disabled={saving}
            className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-60"
          >
            {saving ? 'Saving…' : 'Save Preferences'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      {/* Page header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <button
            type="button"
            onClick={() => navigate('/')}
            className="mb-1 flex items-center gap-1 text-xs text-sky-600 hover:underline dark:text-sky-400"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="h-3.5 w-3.5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15.75 19.5 8.25 12l7.5-7.5"
              />
            </svg>
            Home
          </button>
          <h1 className="text-xl font-semibold">Users</h1>
          <p className="mt-0.5 text-sm opacity-60">
            Manage user accounts, roles, and authentication.
          </p>
        </div>
      </div>

      <UserListView
        authMode={authMode}
        users={users}
        loadingUsers={loading}
        loadError={loadError}
        onRetryLoadUsers={() => void fetchUsers({ force: true })}
        onCreate={() => {
          if (!canCreateLocalUsers) return;
          if (needsLocalAdmin) setCreateForm({ ...createForm, role: 'admin' });
          openCreate();
        }}
        needsLocalAdmin={needsLocalAdmin}
        showCreateForm={effectiveRouteKind === 'create'}
        createForm={createForm}
        onCreateFormChange={setCreateForm}
        creating={creating}
        isFirstUser={users.length === 0}
        onCreateSubmit={() => void handleCreate()}
        onCancelCreate={handleCancelCreate}
        showEditForm={effectiveRouteKind === 'edit'}
        activeEditUserId={activeEditUserId}
        editingUser={effectiveRouteKind === 'edit' ? editingUser : null}
        onEditingUserChange={setEditingUser}
        onEditSave={() => void handleSaveUserEdit()}
        saving={saving}
        onCancelEdit={handleBackToList}
        editPassword={editPassword}
        onEditPasswordChange={setEditPassword}
        editPasswordConfirm={editPasswordConfirm}
        onEditPasswordConfirmChange={setEditPasswordConfirm}
        downloadDefaults={downloadDefaults}
        onOpenOverrides={handleOpenOverrides}
        onEdit={(user) => void handleEdit(user)}
        onDelete={handleDeleteUser}
        deletingUserId={deletingUserId}
        onSyncCwa={handleSyncCwa}
        syncingCwa={syncingCwa}
        onForceLogout={forceLogout}
        forcingLogoutUserId={forcingLogoutUserId}
      />
    </div>
  );
}
