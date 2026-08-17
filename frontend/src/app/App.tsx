import { config } from "../lib/config";

export function App() {
  return (
    <main className="app-shell">
      <section className="welcome-card">
        <p className="eyebrow">
          GCMS Admin
        </p>

        <h1>
          Gaming Center Management System
        </h1>

        <p>
          Frontend administrativo preparado
          para conectarse al backend.
        </p>

        <p className="api-info">
          API: {config.apiBaseUrl}
        </p>
      </section>
    </main>
  );
}