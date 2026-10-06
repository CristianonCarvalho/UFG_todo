import ErrorBanner from "./components/ErrorBanner.jsx";
import StatusFilter from "./components/StatusFilter.jsx";
import TaskForm from "./components/TaskForm.jsx";
import TaskList from "./components/TaskList.jsx";
import { useTasks } from "./useTasks.js";

export default function App() {
  const {
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
  } = useTasks();

  return (
    <main className="app">
      <h1>Tarefas</h1>
      <ErrorBanner error={error} onDismiss={clearError} />
      <TaskForm onSubmit={create} />
      <StatusFilter value={filter} onChange={setFilter} />
      <TaskList
        tasks={tasks}
        loading={loading}
        busyIds={busyIds}
        onComplete={complete}
        onRemove={remove}
        onChangePriority={changePriority}
      />
    </main>
  );
}
