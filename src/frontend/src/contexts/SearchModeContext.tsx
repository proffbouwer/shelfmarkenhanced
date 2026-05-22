import type { ReactNode } from 'react';
import { createContext, useContext, useMemo } from 'react';

import { SEARCH_MODE } from '../types';
import type { SearchMode } from '../types';

interface SearchModeContextValue {
  searchMode: SearchMode;
  isUniversalMode: boolean;
}

const SearchModeContext = createContext<SearchModeContextValue | null>(null);

const DEFAULT_SEARCH_MODE: SearchModeContextValue = {
  searchMode: SEARCH_MODE.DIRECT,
  isUniversalMode: false,
};

export function useSearchMode(): SearchModeContextValue {
  return useContext(SearchModeContext) ?? DEFAULT_SEARCH_MODE;
}

interface SearchModeProviderProps {
  searchMode: SearchMode;
  children: ReactNode;
}

export function SearchModeProvider({ searchMode, children }: SearchModeProviderProps) {
  const value = useMemo(
    () => ({ searchMode, isUniversalMode: searchMode === 'universal' }),
    [searchMode],
  );

  return <SearchModeContext.Provider value={value}>{children}</SearchModeContext.Provider>;
}
