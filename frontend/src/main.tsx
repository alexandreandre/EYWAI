import { createRoot } from 'react-dom/client';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import App from './App.tsx';
import './index.css';
import { installChunkLoadRecovery } from './lib/chunkLoadRecovery';
import { installConsoleShim } from './lib/logger';

installConsoleShim();
installChunkLoadRecovery();
import { createAppQueryClient } from './lib/queryClient';
import {
  appDehydrateOptions,
  createAppQueryPersister,
  readQueryCacheBuster,
} from './lib/queryCachePersistence';

const queryClient = createAppQueryClient();

const persister = createAppQueryPersister();
// Utilisateur et société active lus au démarrage : un cache persisté pour un
// autre couple est jeté au lieu d'être restauré (constat C3 de l'audit du 25/09).
const buster = readQueryCacheBuster();

createRoot(document.getElementById('root')!).render(
  <PersistQueryClientProvider
    client={queryClient}
    persistOptions={{
      persister,
      maxAge: 24 * 60 * 60 * 1000,
      buster,
      dehydrateOptions: appDehydrateOptions,
    }}
  >
    <App />
  </PersistQueryClientProvider>,
);
