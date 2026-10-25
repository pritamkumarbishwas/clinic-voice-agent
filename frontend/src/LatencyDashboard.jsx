import { useEffect, useState } from "react";
import { apiGet } from "./lib/api";

const LABELS = {
  endpoint_latency_ms: "Endpoint decision",
  stt_latency_ms: "Speech to final transcript",
  llm_latency_ms: "LLM first token",
  tts_latency_ms: "TTS first audio",
  end_to_audio_ms: "Speech to response audio",
};

export default function LatencyDashboard() {
  const [report, setReport] = useState({});
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    apiGet("/api/analytics/latency", { signal: controller.signal })
      .then((data) => {
        setReport(data.metrics ?? {});
        setError("");
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [reloadKey]);

  function refresh() {
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  const rows = Object.entries(LABELS).map(([key, label]) => ({
    key,
    label,
    ...(report[key] || {}),
  }));

  const slowest = rows
    .filter((row) => typeof row.p95_ms === "number")
    .sort((a, b) => b.p95_ms - a.p95_ms)[0];

  const totalSamples = Math.max(0, ...rows.map((row) => row.count || 0));

  const maxValue = Math.max(1, ...rows.map((row) => row.p95_ms || 0));

  return (
    <main className="latency-dashboard">
      <header className="call-log-header">
        <div>
          <p className="eyebrow">CLINIC VOICE AI</p>
          <h1>Latency performance</h1>
          <p>Measurements from recorded conversation turns.</p>
        </div>

        <button type="button" onClick={refresh}>
          Refresh
        </button>
      </header>

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      {loading ? (
        <p>Loading metrics...</p>
      ) : (
        <>
          <p className="muted">
            {totalSamples} turns measured ·{" "}
            {slowest ? (
              <>
                <strong>Largest p95 stage:</strong> {slowest.label} (
                {slowest.p95_ms} ms)
              </>
            ) : (
              "No samples yet."
            )}
          </p>

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
                <strong>
                  {row.p95_ms == null ? "—" : `${row.p95_ms} ms`}
                </strong>
              </div>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
