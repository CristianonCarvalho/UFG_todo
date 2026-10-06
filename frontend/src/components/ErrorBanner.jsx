export default function ErrorBanner({ error, onDismiss }) {
  if (!error) {
    return null;
  }

  return (
    <div className="banner" role="alert">
      <div>
        <p>{error.message}</p>
        {error.idRequisicao && (
          <p className="banner-id">Código da requisição: {error.idRequisicao}</p>
        )}
      </div>
      <button type="button" onClick={onDismiss}>
        Dispensar
      </button>
    </div>
  );
}
