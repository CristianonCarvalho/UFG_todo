import TaskItem from "./TaskItem.jsx";

export default function TaskList({
  tasks,
  loading,
  busyIds,
  onComplete,
  onRemove,
  onChangePriority,
}) {
  if (loading && tasks.length === 0) {
    return <p role="status">Carregando tarefas…</p>;
  }
  if (tasks.length === 0) {
    return <p className="empty">Nenhuma tarefa por aqui ainda.</p>;
  }
  return (
    <ul className="task-list">
      {tasks.map((task) => (
        <TaskItem
          key={task.id}
          task={task}
          busy={busyIds.includes(task.id)}
          onComplete={onComplete}
          onRemove={onRemove}
          onChangePriority={onChangePriority}
        />
      ))}
    </ul>
  );
}
