import { createRoot } from 'react-dom/client';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister';
import App from './App.tsx';
import './index.css';
import { installChunkLoadRecovery } from './lib/chunkLoadRecovery';
import { installConsoleShim } from './lib/logger';

installConsoleShim();
installChunkLoadRecovery();
import {
  createAppQueryClient,
  QUERY_CACHE_BUSTER,
  QUERY_CACHE_KEY,
} from './lib/queryClient';

const queryClient = createAppQueryClient();

const persister = createSyncStoragePersister({
  storage: window.localStorage,
  key: QUERY_CACHE_KEY,
});

createRoot(document.getElementById('root')!).render(
  <PersistQueryClientProvider
    client={queryClient}
    persistOptions={{
      persister,
      maxAge: 24 * 60 * 60 * 1000,
      buster: QUERY_CACHE_BUSTER,
      dehydrateOptions: {
        shouldDehydrateQuery: (query) => {
          const key = query.queryKey;
          if (Array.isArray(key) && key.some((k) => k === 'sensitive')) {
            return false;
          }
          return query.state.status === 'success';
        },
      },
    }}
  >
    <App />
  </PersistQueryClientProvider>,
);
