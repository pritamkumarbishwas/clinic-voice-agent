
import { useEffect, useState } from "react";

const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

function formatDate(value) {
  if (!value) return "—";

  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleString();
}

function duration(call) {
  if (!call.started_at || !call.ended_at) return "In progress";

  const seconds = Math.max(
    0,
    Math.round(
      (new Date(call.ended_at) - new Date(call.started_at)) / 1000
    )
  );

  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

export default function CallLog() {
  const [calls, setCalls] = useState([]);
  const [selected, setSelected] = useState(null);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadCalls() {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/api/calls?page=${page}&page_size=20`
      );

      if (!response.ok) {
        throw new Error("Could not load call logs");
      }

      const data = await response.json();
      setCalls(data.items);
      setPages(data.pages);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function openCall(callId) {
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/api/calls/${encodeURIComponent(callId)}`
      );

      if (!response.ok) {
        throw new Error("Could not load call details");
      }

      setSelected(await response.json());
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadCalls();
  }, [page]);

  return (
    <main className="call-log">
      <header className="call-log-header">
        <div>
          <p className="eyebrow">CLINIC VOICE AI</p>
          <h1>Call analytics</h1>
          <p>Review conversations and booking outcomes.</p>
        </div>

        <button onClick={loadCalls}>Refresh</button>
      </header>

      {error && <p role="alert" className="error">{error}</p>}

      {loading ? (
        <p>Loading calls...</p>
      ) : calls.length === 0 ? (
        <p>No calls recorded yet. Complete a test call first.</p>
      ) : (
        <div className="call-list">
          {calls.map((call) => (
            <button
              className="call-card"
              key={call.call_id}
              onClick={() => openCall(call.call_id)}
            >
              <span>
                <strong>{call.call_id}</strong>
                <small>{formatDate(call.started_at)}</small>
              </span>

              <span>
                {call.booking_outcome || "unknown"}
                <small>{duration(call)}</small>
              </span>

              <span>
                {call.sentiment || "pending"}
                <small>
                  {call.analysis_status || "analysis pending"}
                </small>
              </span>
            </button>
          ))}
        </div>
      )}

      <nav className="pagination" aria-label="Call pages">
        <button
          disabled={page <= 1}
          onClick={() => setPage((p) => p - 1)}
        >
          Previous
        </button>
        <span>Page {page} of {Math.max(1, pages)}</span>
        <button
          disabled={page >= pages}
          onClick={() => setPage((p) => p + 1)}
        >
          Next
        </button>
      </nav>

      {selected && (
        <section className="call-detail">
          <button onClick={() => setSelected(null)}>
            Close details
          </button>

          <h2>Call details</h2>
          <p><strong>Call ID:</strong> {selected.call_id}</p>
          <p><strong>Duration:</strong> {duration(selected)}</p>
          <p><strong>Outcome:</strong> {selected.booking_outcome}</p>
          <p><strong>Sentiment:</strong> {selected.sentiment || "Pending"}</p>
          <p><strong>Summary:</strong> {selected.summary || "Not analyzed yet"}</p>

          <h3>Transcript</h3>

          {(selected.transcript || []).map((item, index) => (
            <article className="message" key={`${index}-${item.role}`}>
              <strong>{item.role === "assistant" ? "AI receptionist" : "Caller"}</strong>
              <p>{item.text}</p>
              <small>{formatDate(item.timestamp)}</small>
            </article>
          ))}

          <h3>Turn metrics</h3>
          {(selected.turn_metrics || []).map((turn, index) => (
            <pre key={index}>
              {JSON.stringify({
                endpoint_ms: turn.endpoint_latency_ms,
                stt_ms: turn.stt_latency_ms,
                llm_ms: turn.llm_latency_ms,
                tts_ms: turn.tts_latency_ms,
                end_to_audio_ms: turn.end_to_audio_ms,
              }, null, 2)}
            </pre>
          ))}
        </section>
      )}
    </main>
  );
}
