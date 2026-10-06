import { useState } from "react";

function fieldMessage(detalhes, campo) {
  return detalhes.find((detalhe) => detalhe.campo === campo)?.mensagem ?? null;
}

export default function TaskForm({ onSubmit }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [detalhes, setDetalhes] = useState([]);
  const [sending, setSending] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setSending(true);

    try {
      const result = await onSubmit({ title, description });
      if (result.ok) {
        setTitle("");
        setDescription("");
        setDetalhes([]);
      } else {
        setDetalhes(result.detalhes);
      }
    } finally {
      setSending(false);
    }
  }

  const titleError = fieldMessage(detalhes, "title");
  const descriptionError = fieldMessage(detalhes, "description");

  return (
    <form className="task-form" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor="task-title">Título</label>
        <input
          id="task-title"
          value={title}
          maxLength={100}
          onChange={(event) => setTitle(event.target.value)}
          aria-invalid={Boolean(titleError)}
          aria-describedby={titleError ? "task-title-error" : undefined}
        />
        {titleError && (
          <p id="task-title-error" className="field-error">
            {titleError}
          </p>
        )}
      </div>
      <div className="field">
        <label htmlFor="task-description">Descrição</label>
        <textarea
          id="task-description"
          value={description}
          maxLength={500}
          rows={3}
          onChange={(event) => setDescription(event.target.value)}
          aria-invalid={Boolean(descriptionError)}
          aria-describedby={descriptionError ? "task-description-error" : undefined}
        />
        {descriptionError && (
          <p id="task-description-error" className="field-error">
            {descriptionError}
          </p>
        )}
      </div>
      <button type="submit" disabled={sending}>
        Adicionar
      </button>
    </form>
  );
}
