// frontend/src/pages/super-admin/Tests.tsx
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import apiClient from '../../api/apiClient';

const DRAG_THRESHOLD_MS = 180;

interface TestChild {
  id: string;
  label: string;
  path: string;
  is_full_level?: boolean;
}

interface TestLevel {
  id: string;
  label: string;
  path: string;
  children: TestChild[];
}

interface TestsTree {
  levels: TestLevel[];
}

interface RunResultItem {
  target: string;
  success: boolean;
  exit_code: number;
  stdout: string;
  stderr: string;
}

export default function Tests() {
  const [tree, setTree] = useState<TestsTree | null>(null);
  const [loadingTree, setLoadingTree] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<RunResultItem[] | null>(null);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);
  const dragTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dragStartPathRef = useRef<string | null>(null);
  const dragSelectModeRef = useRef(false);
  const ignoreNextClickRef = useRef(false);
  const lastClickedPathRef = useRef<string | null>(null);

  const flattenedPaths = useMemo(() => {
    if (!tree) return [];
    return tree.levels.flatMap((level) => level.children.map((c) => c.path));
  }, [tree]);

  const loadTree = useCallback(async () => {
    try {
      const response = await apiClient.get('/api/super-admin/tests/tree');
      setTree(response.data);
      setExpanded(new Set((response.data?.levels ?? []).map((l: TestLevel) => l.id)));
    } catch (err) {
      console.error('Erreur chargement arbre tests:', err);
    } finally {
      setLoadingTree(false);
    }
  }, []);

  useEffect(() => {
    loadTree();
  }, [loadTree]);

  const toggleSelect = (path: string) => {
    if (ignoreNextClickRef.current) {
      ignoreNextClickRef.current = false;
      return;
    }
    lastClickedPathRef.current = path;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const addToSelection = useCallback((path: string) => {
    setSelected((prev) => new Set(prev).add(path));
  }, []);

  const toggleInSelection = useCallback((path: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const selectRange = useCallback((fromPath: string, toPath: string) => {
    const fromIdx = flattenedPaths.indexOf(fromPath);
    const toIdx = flattenedPaths.indexOf(toPath);
    if (fromIdx === -1 || toIdx === -1) return;
    const [lo, hi] = fromIdx <= toIdx ? [fromIdx, toIdx] : [toIdx, fromIdx];
    const pathsToAdd = flattenedPaths.slice(lo, hi + 1);
    setSelected((prev) => {
      const next = new Set(prev);
      pathsToAdd.forEach((p) => next.add(p));
      return next;
    });
  }, [flattenedPaths]);

  const clearDragTimer = useCallback(() => {
    if (dragTimerRef.current) {
      clearTimeout(dragTimerRef.current);
      dragTimerRef.current = null;
    }
  }, []);

  const handleRowPointerDown = useCallback((path: string) => {
    clearDragTimer();
    dragSelectModeRef.current = false;
    dragStartPathRef.current = path;
    dragTimerRef.current = setTimeout(() => {
      dragTimerRef.current = null;
      dragSelectModeRef.current = true;
      addToSelection(path);
    }, DRAG_THRESHOLD_MS);
  }, [addToSelection, clearDragTimer]);

  const handleRowPointerEnter = useCallback((path: string) => {
    if (!dragSelectModeRef.current && dragStartPathRef.current !== null && dragStartPathRef.current !== path) {
      clearDragTimer();
      dragSelectModeRef.current = true;
      addToSelection(dragStartPathRef.current);
      toggleInSelection(path);
      return;
    }
    if (dragSelectModeRef.current) toggleInSelection(path);
  }, [addToSelection, toggleInSelection, clearDragTimer]);

  const handlePointerUp = useCallback(() => {
    if (dragSelectModeRef.current) ignoreNextClickRef.current = true;
    dragSelectModeRef.current = false;
    dragStartPathRef.current = null;
    clearDragTimer();
  }, [clearDragTimer]);

  const toggleOne = useCallback((path: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const handleRowClickCapture = useCallback((path: string, e: React.MouseEvent) => {
    if (e.metaKey || e.ctrlKey) {
      e.preventDefault();
      e.stopPropagation();
      toggleOne(path);
      lastClickedPathRef.current = path;
      return;
    }
    if (e.shiftKey) {
      e.preventDefault();
      e.stopPropagation();
      const last = lastClickedPathRef.current;
      if (last != null) selectRange(last, path);
      else addToSelection(path);
      lastClickedPathRef.current = path;
    }
  }, [toggleOne, addToSelection, selectRange]);

  useEffect(() => {
    document.addEventListener('pointerup', handlePointerUp);
    document.addEventListener('pointercancel', handlePointerUp);
    return () => {
      document.removeEventListener('pointerup', handlePointerUp);
      document.removeEventListener('pointercancel', handlePointerUp);
      clearDragTimer();
    };
  }, [handlePointerUp, clearDragTimer]);

  const toggleLevel = (levelId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(levelId)) next.delete(levelId);
      else next.add(levelId);
      return next;
    });
  };

  const selectAll = () => {
    if (!tree) return;
    const all: string[] = [];
    tree.levels.forEach((level) => {
      level.children.forEach((c) => all.push(c.path));
    });
    setSelected(new Set(all));
  };

  const selectNone = () => setSelected(new Set());

  const selectLevel = (level: TestLevel) => {
    const paths = level.children.map((c) => c.path);
    setSelected((prev) => {
      const next = new Set(prev);
      paths.forEach((p) => next.add(p));
      return next;
    });
  };

  const runSelected = async () => {
    const targets = Array.from(selected);
    if (targets.length === 0) {
      setResults([
        { target: '', success: false, exit_code: -1, stdout: '', stderr: 'Aucune cible sélectionnée. Cochez au moins une cible.' },
      ]);
      setExpandedIndex(0);
      return;
    }
    setRunning(true);
    setResults(null);
    setExpandedIndex(null);
    try {
      const response = await apiClient.post('/api/super-admin/tests/run', { targets });
      setResults(response.data.results ?? []);
      setExpandedIndex(0);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: unknown }; message?: string };
      setResults([
        {
          target: '',
          success: false,
          exit_code: -1,
          stdout: '',
          stderr: axiosErr?.response?.data ? String(axiosErr.response.data) : (axiosErr?.message ?? 'Erreur réseau'),
        },
      ]);
      setExpandedIndex(0);
    } finally {
      setRunning(false);
    }
  };

  const copyOutput = useCallback((item: RunResultItem) => {
    const parts: string[] = [];
    if (item.target) parts.push(`Cible: ${item.target}`);
    parts.push(`Résultat: ${item.success ? 'Succès' : 'Échec'}`);
    if (item.stdout) parts.push('\n=== Sortie standard ===\n' + item.stdout);
    if (item.stderr) parts.push('\n=== Erreurs ===\n' + item.stderr);
    const text = parts.join('\n') || '';
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, []);

  const runAll = async () => {
    if (!tree) return;
    const all: string[] = [];
    tree.levels.forEach((level) => {
      level.children.forEach((c) => all.push(c.path));
    });
    setSelected(new Set(all));
    setRunning(true);
    setResults(null);
    setExpandedIndex(null);
    try {
      const response = await apiClient.post('/api/super-admin/tests/run', { targets: all });
      setResults(response.data.results ?? []);
      setExpandedIndex(0);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: unknown }; message?: string };
      setResults([
        {
          target: '',
          success: false,
          exit_code: -1,
          stdout: '',
          stderr: axiosErr?.response?.data ? String(axiosErr.response.data) : (axiosErr?.message ?? 'Erreur réseau'),
        },
      ]);
      setExpandedIndex(0);
    } finally {
      setRunning(false);
    }
  };

  if (loadingTree) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-indigo-600 mx-auto" />
          <p className="mt-4 text-gray-600">Chargement des cibles de test...</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Tests</h1>
        <p className="text-gray-600 mt-2">
          <strong>Pytest</strong> — dossier{' '}
          <code className="bg-gray-100 px-1 rounded">backend_api/tests</code> (unitaires, intégration, E2E API, migration, architecture).{' '}
          <strong>Playwright</strong> — dossier <code className="bg-gray-100 px-1 rounded">e2e/</code> à la racine du dépôt (navigateur, frontend + backend).
        </p>
        <p className="text-gray-500 text-sm mt-2">
          Playwright : exécuter <code className="bg-gray-100 px-1 rounded text-xs">npm install</code> dans{' '}
          <code className="bg-gray-100 px-1 rounded text-xs">e2e/</code>, installer les navigateurs si besoin (
          <code className="bg-gray-100 px-1 rounded text-xs">npx playwright install</code>
          ), démarrer le frontend et le backend, et définir <code className="bg-gray-100 px-1 rounded text-xs">TEST_USER_EMAIL</code> /{' '}
          <code className="bg-gray-100 px-1 rounded text-xs">TEST_USER_PASSWORD</code> dans l&apos;environnement du serveur API (ou fichier{' '}
          <code className="bg-gray-100 px-1 rounded text-xs">.env</code> chargé par uvicorn).
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Arbre des cibles */}
        <div className="bg-white rounded-lg shadow-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xl font-bold text-gray-900">Cibles</h2>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={selectAll}
                className="px-3 py-1.5 text-sm font-medium text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors"
              >
                Tout sélectionner
              </button>
              <button
                type="button"
                onClick={selectNone}
                className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
              >
                Tout désélectionner
              </button>
            </div>
          </div>
          <p className="text-xs text-gray-500 mb-3">
            Glisser pour sélectionner plusieurs · <kbd className="px-1 py-0.5 bg-gray-100 rounded">⌘</kbd> ou <kbd className="px-1 py-0.5 bg-gray-100 rounded">Ctrl</kbd>+clic pour ajouter/retirer · <kbd className="px-1 py-0.5 bg-gray-100 rounded">Maj</kbd>+clic pour une plage
          </p>

          <div className="space-y-2 max-h-[480px] overflow-y-auto">
            {tree?.levels?.map((level) => (
              <div key={level.id} className="border border-gray-200 rounded-lg overflow-hidden">
                <button
                  type="button"
                  onClick={() => toggleLevel(level.id)}
                  className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 text-left font-semibold text-gray-900"
                >
                  <span>{level.label}</span>
                  <span className="text-gray-500">{expanded.has(level.id) ? '▼' : '▶'}</span>
                </button>
                {expanded.has(level.id) && (
                  <div className="px-4 py-2 bg-white border-t border-gray-100">
                    <div className="flex flex-wrap gap-2 mb-2">
                      <button
                        type="button"
                        onClick={() => selectLevel(level)}
                        className="text-xs text-indigo-600 hover:underline"
                      >
                        Sélectionner tout le niveau
                      </button>
                    </div>
                    <ul className="space-y-1.5">
                      {level.children.map((child) => (
                        <li
                          key={child.id}
                          className="flex items-center gap-2 rounded px-1 -mx-1 py-0.5"
                          onPointerDown={() => handleRowPointerDown(child.path)}
                          onPointerEnter={() => handleRowPointerEnter(child.path)}
                          onClickCapture={(e) => handleRowClickCapture(child.path, e)}
                        >
                          <input
                            type="checkbox"
                            id={child.id}
                            checked={selected.has(child.path)}
                            onChange={() => toggleSelect(child.path)}
                            className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                          />
                          <label
                            htmlFor={child.id}
                            className="text-sm text-gray-700 cursor-pointer flex-1 truncate select-none"
                            title={child.path}
                          >
                            {child.label}
                          </label>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={runSelected}
              disabled={running || selected.size === 0}
              className="px-4 py-2 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {running ? 'Exécution…' : `Exécuter la sélection (${selected.size})`}
            </button>
            <button
              type="button"
              onClick={runAll}
              disabled={running}
              className="px-4 py-2 bg-gray-800 text-white font-medium rounded-lg hover:bg-gray-900 disabled:opacity-50 transition-colors"
            >
              Exécuter tout
            </button>
          </div>
        </div>

        {/* Résultats : liste par test + détail au clic */}
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Résultats</h2>
          {running && (
            <div className="flex items-center gap-3 text-indigo-600 mb-4">
              <div className="animate-spin rounded-full h-5 w-5 border-2 border-indigo-600 border-t-transparent" />
              <span>Exécution des tests en cours…</span>
            </div>
          )}
          {results && results.length > 0 && !running && (
            <>
              <ul className="space-y-1 mb-4 max-h-48 overflow-y-auto">
                {results.map((item, index) => (
                  <li key={item.target || index}>
                    <button
                      type="button"
                      onClick={() => setExpandedIndex(index)}
                      className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors ${
                        expandedIndex === index ? 'bg-indigo-50 ring-1 ring-indigo-200' : 'hover:bg-gray-50'
                      }`}
                    >
                      <span
                        className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold ${
                          item.success ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                        }`}
                        title={item.success ? 'Succès' : 'Échec'}
                      >
                        {item.success ? '✓' : '✗'}
                      </span>
                      <span className="flex-1 truncate text-sm font-medium text-gray-900" title={item.target}>
                        {item.target ? (
                          <>
                            {item.target.startsWith('pw:') ? (
                              <span className="mr-2 text-xs font-semibold text-violet-700 bg-violet-50 px-1.5 py-0.5 rounded">
                                Playwright
                              </span>
                            ) : (
                              <span className="mr-2 text-xs font-semibold text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">
                                pytest
                              </span>
                            )}
                            <span className="align-middle">{item.target}</span>
                          </>
                        ) : (
                          '(sans cible)'
                        )}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              {expandedIndex !== null && results[expandedIndex] && (
                <div className="border-t border-gray-200 pt-4">
                  {(() => {
                    const item = results[expandedIndex];
                    return (
                      <>
                        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                          <div>
                            <p className="text-sm font-semibold text-gray-900">
                              {item.target || 'Résultat'}
                            </p>
                            <div
                              className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-lg text-sm font-medium mt-1 ${
                                item.success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                              }`}
                            >
                              {item.success ? '✓ Succès' : '✗ Échec'}
                              {item.exit_code !== undefined && item.exit_code !== -1 && (
                                <span>(code {item.exit_code})</span>
                              )}
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={() => copyOutput(item)}
                            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors text-sm"
                          >
                            {copied ? '✓ Copié' : '📋 Copier la sortie'}
                          </button>
                        </div>
                        <div className="space-y-3">
                          {item.stdout ? (
                            <div>
                              <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Sortie standard</p>
                              <pre className="p-3 bg-gray-900 text-gray-100 text-xs rounded-lg overflow-x-auto max-h-64 overflow-y-auto whitespace-pre-wrap">
                                {item.stdout}
                              </pre>
                            </div>
                          ) : null}
                          {item.stderr ? (
                            <div>
                              <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Erreurs</p>
                              <pre className="p-3 bg-red-50 text-red-900 text-xs rounded-lg overflow-x-auto max-h-64 overflow-y-auto whitespace-pre-wrap border border-red-200">
                                {item.stderr}
                              </pre>
                            </div>
                          ) : null}
                          {!item.stdout && !item.stderr && (
                            <p className="text-gray-500 text-sm">Aucune sortie.</p>
                          )}
                        </div>
                      </>
                    );
                  })()}
                </div>
              )}
            </>
          )}
          {!results?.length && !running && (
            <p className="text-gray-500 text-sm">Sélectionnez des cibles et lancez une exécution pour afficher les résultats.</p>
          )}
        </div>
      </div>
    </div>
  );
}
