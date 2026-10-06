import { useState } from "react";

const SOURCE_LABELS = {
  jev: "Sugerida pela IA",
  fallback: "Estimativa automática",
  manual: "Definida por você",
};
const PRIORITY_LABELS = { baixa: "Baixa", media: "Média", alta: "Alta" };
const STATUS_LABELS = { pendente: "Pendente", concluida: "Concluída" };

export default function TaskItem({ task, busy, onComplete, onRemove, onChangePriority }) {
  const [confirming, setConfirming] = useState(false);

  return (
    <li className="task-item">
      <div className="task-main">
        <h3>{task.title}</h3>
        {task.description && <p>{task.description}</p>}
        <p className="task-meta">
          <span className="badge">{STATUS_LABELS[task.status]}</span>{" "}
          <span className="badge">Prioridade {PRIORITY_LABELS[task.priority]}</span>{" "}
          <span className="badge">{SOURCE_LABELS[task.priority_source]}</span>
        </p>
        {task.priority_notice && <p className="notice">{task.priority_notice}</p>}
      </div>
      <div className="task-actions">
        <select
          aria-label={`Alterar prioridade de ${task.title}`}
          value={task.priority}
          disabled={busy}
          onChange={(event) => onChangePriority(task.id, event.target.value)}
        >
          {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        {task.status !== "concluida" && (
          <button type="button" disabled={busy} onClick={() => onComplete(task.id)}>
            Concluir
          </button>
        )}
        {confirming ? (
          <>
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                setConfirming(false);
                onRemove(task.id);
              }}
            >
              Confirmar remoção
            </button>
            <button type="button" onClick={() => setConfirming(false)}>
              Cancelar
            </button>
          </>
        ) : (
          <button type="button" disabled={busy} onClick={() => setConfirming(true)}>
            Remover
          </button>
        )}
      </div>
    </li>
  );
}
