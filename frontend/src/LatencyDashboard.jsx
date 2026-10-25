
import { useEffect, useState } from "react";

const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

const LABELS = {
  endpoint_latency_ms: "Endpoint decision",
  stt_latency_ms: "Speech → final transcript",
  llm_latency_ms: "LLM → first token",
  tts_latency_ms: "TTS → first audio",
  end_to_audio_ms: "Speech → response audio",
};

export default function LatencyDashboard() {
  const [report, setReport] = useState({});
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/api/analytics/latency`)
      .then((response) => {
        if (!response.ok) throw new Error("Could not load metrics");
        return response.json();
      })
      .then(setReport)
      .catch((err) => setError(err.message));
  }, []);

  const rows = Object.entries(LABELS).map(([key, label]) => ({
    key,
    label,
    ...(report[key] || {}),
  }));

  const slowest = rows
    .filter((row) => typeof row.p95_ms === "number")
    .sort((a, b) => b.p95_ms - a.p95_ms)[0];

  const maxValue = Math.max(
    1,
    ...rows.map((row) => row.p95_ms || 0)
  );

  return (
    <main className="latency-dashboard">
      <h1>Latency performance</h1>
      <p>Measurements from recorded conversation turns.</p>

      {error && <p role="alert">{error}</p>}

      {slowest && (
        <p>
          <strong>Largest p95 stage:</strong> {slowest.label} (
          {slowest.p95_ms} ms)
        </p>
      )}

      <div className="latency-table-wrap">
        <table className="latency-table">
          <thead>
            <tr>
              <th>Stage</th>
              <th>Samples</th>
              <th>p50 (ms)</th>
              <th>p95 (ms)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <td>{row.label}</td>
                <td>{row.count ?? 0}</td>
                <td>{row.p50_ms ?? "—"}</td>
                <td>{row.p95_ms ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>p95 comparison</h2>
      <div className="latency-bars">
        {rows.map((row) => (
          <div key={row.key} className="latency-bar-row">
            <span>{row.label}</span>
            <div className="latency-bar-track">
              <div
                className="latency-bar"
                style={{
                  width: `${((row.p95_ms || 0) / maxValue) * 100}%`,
                }}
              />
            </div>
            <strong>{row.p95_ms == null ? "—" : `${row.p95_ms} ms`}</strong>
          </div>
        ))}
      </div>
    </main>
  );
}
