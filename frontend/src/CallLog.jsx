import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "./lib/api";

function formatDate(value) {
  if (!value) return "—";

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

function duration(call) {
  if (!call.started_at || !call.ended_at) return "In progress";

  const seconds = Math.max(
    0,
    Math.round((new Date(call.ended_at) - new Date(call.started_at)) / 1000)
  );

  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function formatMs(value) {
  return typeof value === "number" ? `${value.toFixed(0)} ms` : "—";
}

export default function CallLog() {
  const [calls, setCalls] = useState([]);
  const [selected, setSelected] = useState(null);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [error, setError] = useState("");
  const [runFilter, setRunFilter] = useState("");
  const [appliedRun, setAppliedRun] = useState("");
  const [analysisRetrying, setAnalysisRetrying] = useState(false);
  const detailAbortRef = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({
      page: String(page),
      page_size: "20",
    });
    if (appliedRun) params.set("run_id", appliedRun);

    apiGet(`/api/calls?${params.toString()}`, {
      signal: controller.signal,
    })
      .then((data) => {
        setCalls(data.items ?? []);
        setPages(Math.max(1, data.total_pages ?? 1));
        setError("");
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [page, reloadKey, appliedRun]);

  useEffect(() => {
    return () => detailAbortRef.current?.abort();
  }, []);

  function refresh() {
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  async function openCall(callId) {
    detailAbortRef.current?.abort();
    const controller = new AbortController();
    detailAbortRef.current = controller;

    setSelected(null);
    setDetailLoading(true);
    setError("");

    try {
      const data = await apiGet(
        `/api/calls/${encodeURIComponent(callId)}`,
        { signal: controller.signal }
      );

      if (!controller.signal.aborted) setSelected(data);
    } catch (err) {
      if (err.name !== "AbortError") setError(err.message);
    } finally {
      if (detailAbortRef.current === controller) {
        detailAbortRef.current = null;
        setDetailLoading(false);
      }
    }
  }

  function goToPage(nextPage) {
    setSelected(null);
    setLoading(true);
    setPage(nextPage);
  }

  function applyRunFilter(event) {
    event.preventDefault();
    setSelected(null);
    setLoading(true);
    setPage(1);
    setAppliedRun(runFilter.trim());
  }

  function clearRunFilter() {
    setSelected(null);
    setLoading(true);
    setPage(1);
    setRunFilter("");
    setAppliedRun("");
  }

  async function retryAnalysis(callId) {
    setAnalysisRetrying(true);
    setError("");

    try {
      await apiPost(`/api/calls/${encodeURIComponent(callId)}/analyze`);
      setSelected((previous) =>
        previous
          ? {
              ...previous,
              call: {
                ...previous.call,
                analysis_status: "pending",
                analysis_error: null,
              },
            }
          : previous
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalysisRetrying(false);
    }
  }

  const call = selected?.call;
  const appointment = selected?.appointment;
  const turns = selected?.turn_metrics ?? [];

  return (
    <main className="call-log">
      <header className="call-log-header">
        <div>
          <p className="eyebrow">CLINIC VOICE AI</p>
          <h1>Call analytics</h1>
          <p>Review conversations, latency, and booking outcomes.</p>
        </div>

        <button type="button" onClick={refresh}>
          Refresh
        </button>
      </header>

      <form className="run-filter" onSubmit={applyRunFilter}>
        <span>Filter by test run</span>
        <input
          type="text"
          value={runFilter}
          onChange={(event) => setRunFilter(event.target.value)}
          placeholder="e.g. baseline-1"
          maxLength={48}
        />
        <button type="submit">Apply</button>
        {appliedRun && (
          <button type="button" className="secondary" onClick={clearRunFilter}>
            Clear
          </button>
        )}
      </form>

      {appliedRun && (
        <p className="muted">
          Showing calls tagged <strong>{appliedRun}</strong>
        </p>
      )}

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      {loading ? (
        <p>Loading calls...</p>
      ) : calls.length === 0 ? (
        <p>No calls recorded yet. Complete a test call first.</p>
      ) : (
        <div className="call-list">
          {calls.map((item) => (
            <button
              type="button"
              className="call-card"
              key={item.call_id}
              onClick={() => openCall(item.call_id)}
            >
              <span>
                <strong>{item.call_id}</strong>
                <small>{formatDate(item.started_at)}</small>
              </span>

              <span>
                {item.booking_outcome || "unknown"}
                <small>{duration(item)}</small>
              </span>

              <span>
                {item.sentiment || "pending"}
                <small>{item.analysis_status || "analysis pending"}</small>
              </span>
            </button>
          ))}
        </div>
      )}

      <nav className="pagination" aria-label="Call pages">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => goToPage(page - 1)}
        >
          Previous
        </button>
        <span>
          Page {page} of {pages}
        </span>
        <button
          type="button"
          disabled={page >= pages}
          onClick={() => goToPage(page + 1)}
        >
          Next
        </button>
      </nav>

      {detailLoading && <p>Loading call details...</p>}

      {call && (
        <section className="call-detail">
          <button type="button" onClick={() => setSelected(null)}>
            Close details
          </button>

          <h2>Call details</h2>

          <dl className="detail-grid">
            <div>
              <dt>Call ID</dt>
              <dd>{call.call_id}</dd>
            </div>
            <div>
              <dt>Duration</dt>
              <dd>{duration(call)}</dd>
            </div>
            <div>
              <dt>Outcome</dt>
              <dd>{call.booking_outcome || "unknown"}</dd>
            </div>
            <div>
              <dt>Sentiment</dt>
              <dd>{call.sentiment || "Pending"}</dd>
            </div>
            <div>
              <dt>Intent</dt>
              <dd>{call.intent || "—"}</dd>
            </div>
            <div>
              <dt>Barge-ins</dt>
              <dd>{call.barge_in_count ?? 0}</dd>
            </div>
            <div>
              <dt>Speech turns</dt>
              <dd>{call.speech_count ?? 0}</dd>
            </div>
            <div>
              <dt>Analysis</dt>
              <dd>{call.analysis_status || "pending"}</dd>
            </div>
            <div>
              <dt>Appointment</dt>
              <dd>{call.appointment_id || "Not booked"}</dd>
            </div>
            <div>
              <dt>Started</dt>
              <dd>{formatDate(call.started_at)}</dd>
            </div>
          </dl>

          <p className="summary">
            <strong>Summary:</strong>{" "}
            {call.summary ||
              (call.analysis_status === "completed"
                ? "No summary recorded."
                : "Analysis pending.")}
          </p>

          {call.follow_up && (
            <p className="summary">
              <strong>Follow-up:</strong> {call.follow_up}
            </p>
          )}

          {call.analysis_error && (
            <p className="error">
              <strong>Analysis error:</strong> {call.analysis_error}
            </p>
          )}

          {call.analysis_status !== "completed" && (
            <button
              type="button"
              className="secondary"
              onClick={() => retryAnalysis(call.call_id)}
              disabled={analysisRetrying}
            >
              {analysisRetrying ? "Requeueing..." : "Retry analysis"}
            </button>
          )}

          {appointment && (
            <div className="appointment-card">
              <h3>Appointment</h3>
              <p>
                <strong>{appointment.name}</strong> · {appointment.phone}
              </p>
              <p>
                {appointment.doctor_name || "Doctor"} ·{" "}
                {formatDate(appointment.start_at)}
              </p>
              <p className="muted">Status: {appointment.status}</p>
            </div>
          )}

          <h3>Tool calls</h3>

          {(call.tool_calls || []).length === 0 ? (
            <p className="muted">No tool calls recorded.</p>
          ) : (
            <div className="tool-calls">
              {(call.tool_calls || []).map((tool, index) => (
                <article
                  className="tool-call"
                  key={`${tool.call_id}-${index}`}
                >
                  <strong>{tool.name || "tool"}</strong>
                  <small>{formatDate(tool.timestamp)}</small>
                  {tool.arguments && (
                    <pre>Arguments: {tool.arguments}</pre>
                  )}
                  {tool.output && <pre>Result: {tool.output}</pre>}
                  {tool.is_error && (
                    <span className="error">Tool reported an error</span>
                  )}
                </article>
              ))}
            </div>
          )}

          <h3>Transcript</h3>

          {(call.transcript || []).length === 0 ? (
            <p className="muted">No transcript recorded.</p>
          ) : (
            (call.transcript || []).map((item, index) => (
              <article
                className={`message ${item.role}`}
                key={`${item.role}-${index}`}
              >
                <strong>
                  {item.role === "assistant"
                    ? "AI receptionist"
                    : "Caller"}
                </strong>
                <p>{item.text}</p>
                <small>{formatDate(item.timestamp)}</small>
              </article>
            ))
          )}

          <h3>Turn metrics</h3>

          {turns.length === 0 ? (
            <p className="muted">No latency samples for this call.</p>
          ) : (
            <div className="turn-metrics">
              {turns.map((turn, index) => (
                <div className="turn-metric" key={turn.turn_id || index}>
                  <span className="turn-role">
                    {turn.role === "assistant" ? "AI" : "Caller"}
                  </span>

                  {turn.role === "assistant" ? (
                    <>
                      <span>LLM {formatMs(turn.llm_latency_ms)}</span>
                      <span>TTS {formatMs(turn.tts_latency_ms)}</span>
                      <span>E2E {formatMs(turn.end_to_audio_ms)}</span>
                      <span>
                        Playback {formatMs(turn.playback_latency_ms)}
                      </span>
                    </>
                  ) : (
                    <>
                      <span>
                        Endpoint {formatMs(turn.endpoint_latency_ms)}
                      </span>
                      <span>STT {formatMs(turn.stt_latency_ms)}</span>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
