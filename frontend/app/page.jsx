async function getApiStatus() {
  try {
    const response = await fetch("http://localhost:5000/api/health", {
      cache: "no-store",
    });
    if (!response.ok) return "Unavailable";
    const data = await response.json();
    return data.status ?? "Connected";
  } catch {
    return "Unavailable";
  }
}

export default async function Home() {
  const apiStatus = await getApiStatus();

  return (
    <main className="dashboard">
      <header className="topbar">
        <a className="brand" href="/">Project Dashboard</a>
        <span className="badge">Starter</span>
      </header>

      <section className="welcome">
        <p className="eyebrow">WORKSPACE</p>
        <h1>Build something useful.</h1>
        <p className="subtitle">
          A starting point for model training, API integrations, and interactive data.
        </p>
      </section>

      <section className="cards" aria-label="Project overview">
        <article className="card">
          <p className="card-label">BACKEND API</p>
          <p className="card-value">{apiStatus}</p>
          <p className="card-note">Flask health endpoint</p>
        </article>
        <article className="card">
          <p className="card-label">MODEL TRAINING</p>
          <p className="card-value">Ready to build</p>
          <p className="card-note">Add a training pipeline when needed</p>
        </article>
        <article className="card">
          <p className="card-label">DATA & APIS</p>
          <p className="card-value">Ready to connect</p>
          <p className="card-note">Configure integrations in the backend</p>
        </article>
      </section>
    </main>
  );
}
