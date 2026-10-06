const OPTIONS = [
  ["todas", "Todas"],
  ["pendente", "Pendentes"],
  ["concluida", "Concluídas"],
];

export default function StatusFilter({ value, onChange }) {
  return (
    <div className="filter" role="group" aria-label="Filtrar por status">
      {OPTIONS.map(([key, label]) => (
        <button
          key={key}
          type="button"
          aria-pressed={value === key}
          onClick={() => onChange(key)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
