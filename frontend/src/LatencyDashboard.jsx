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
  const [runs, setRuns] = useState([]);
  const [runId, setRunId] = useState("");
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    apiGet("/api/analytics/runs", { signal: controller.signal })
      .then((data) => setRuns(data.items ?? []))
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      });

    return () => controller.abort();
  }, [reloadKey]);

  useEffect(() => {
    const controller = new AbortController();
    const path = runId
      ? `/api/analytics/latency?run_id=${encodeURIComponent(runId)}`
      : "/api/analytics/latency";

    apiGet(path, { signal: controller.signal })
      .then((data) => {
        setReport(data);
        setError("");
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [reloadKey, runId]);

  function refresh() {
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  const metrics = report.metrics ?? {};

  const rows = Object.entries(LABELS).map(([key, label]) => ({
    key,
    label,
    ...(metrics[key] || {}),
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

        <div className="run-filter">
          <span>Benchmark run</span>
          <select
            value={runId}
            onChange={(event) => {
              setLoading(true);
              setRunId(event.target.value);
            }}
          >
            <option value="">All calls</option>
            {runs.map((run) => (
              <option key={run.run_id} value={run.run_id}>
                {run.run_id} ({run.call_count} calls)
              </option>
            ))}
          </select>
          <button type="button" onClick={refresh}>
            Refresh
          </button>
        </div>
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
            {report.calls_measured ?? 0} calls · {totalSamples} turns
            measured · {report.barge_in_count ?? 0} barge-ins
            {typeof report.booking_success_rate === "number" && (
              <>
                {" "}
                · booking success{" "}
                {Math.round(report.booking_success_rate * 100)}%
              </>
            )}
            {slowest ? (
              <>
                {" "}
                · <strong>Largest p95 stage:</strong> {slowest.label} (
                {slowest.p95_ms} ms)
              </>
            ) : (
              " · No samples yet."
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
