import { useCallback, useEffect, useRef, useState } from "react";

import * as api from "./api.js";
import { ApiError } from "./api.js";

export function useTasks() {
  const [tasks, setTasks] = useState([]);
  const [filter, setFilter] = useState("todas");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyIds, setBusyIds] = useState([]);
  const latestRequest = useRef(0);
  const errorRef = useRef(null);
  const busyCounts = useRef(new Map());

  const updateError = useCallback((nextError) => {
    errorRef.current = nextError;
    setError(nextError);
  }, []);

  const load = useCallback(
    async (currentFilter, silent = false) => {
      const requestNumber = ++latestRequest.current;
      if (!silent) {
        setLoading(true);
      }
      try {
        const data = await api.listTasks(currentFilter);
        if (requestNumber === latestRequest.current) {
          setTasks(data);
        }
      } catch (caught) {
        if (requestNumber === latestRequest.current && (!silent || errorRef.current === null)) {
          updateError(caught);
        }
      } finally {
        if (requestNumber === latestRequest.current) {
          setLoading(false);
        }
      }
    },
    [updateError],
  );

  useEffect(() => {
    load(filter);
  }, [filter, load]);

  const create = useCallback(
    async (data) => {
      updateError(null);
      try {
        await api.createTask(data);
        await load(filter, true);
        return { ok: true, detalhes: [] };
      } catch (caught) {
        if (caught instanceof ApiError && caught.detalhes.length > 0) {
          return { ok: false, detalhes: caught.detalhes };
        }
        updateError(caught);
        return { ok: false, detalhes: [] };
      }
    },
    [filter, load, updateError],
  );

  const act = useCallback(
    async (id, action) => {
      updateError(null);
      const count = busyCounts.current.get(id) ?? 0;
      busyCounts.current.set(id, count + 1);
      if (count === 0) {
        setBusyIds((ids) => [...ids, id]);
      }
      try {
        await action();
        await load(filter, true);
      } catch (caught) {
        updateError(caught);
        await load(filter, true);
      } finally {
        const remaining = busyCounts.current.get(id) - 1;
        if (remaining === 0) {
          busyCounts.current.delete(id);
          setBusyIds((ids) => ids.filter((busyId) => busyId !== id));
        } else {
          busyCounts.current.set(id, remaining);
        }
      }
    },
    [filter, load, updateError],
  );

  const complete = useCallback((id) => act(id, () => api.completeTask(id)), [act]);
  const remove = useCallback((id) => act(id, () => api.deleteTask(id)), [act]);
  const changePriority = useCallback(
    (id, priority) => act(id, () => api.updateTask(id, { priority })),
    [act],
  );
  const clearError = useCallback(() => updateError(null), [updateError]);

  return {
    tasks,
    filter,
    setFilter,
    loading,
    error,
    clearError,
    busyIds,
    create,
    complete,
    remove,
    changePriority,
  };
}
