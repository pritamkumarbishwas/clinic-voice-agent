import { useState } from "react";
import CallLog from "./CallLog";
import LatencyDashboard from "./LatencyDashboard";
import LiveCall from "./LiveCall";
import "./App.css";

const VIEWS = [
  { id: "live", label: "Live call" },
  { id: "calls", label: "Call log" },
  { id: "latency", label: "Latency" },
];

export default function App() {
  const [view, setView] = useState("live");

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">CLINIC VOICE AI</p>
          <strong>Receptionist console</strong>
        </div>

        <nav className="tabs" aria-label="Sections">
          {VIEWS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={view === item.id ? "tab active" : "tab"}
              aria-current={view === item.id ? "page" : undefined}
              onClick={() => setView(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      <div className="view">
        {view === "live" && <LiveCall />}
        {view === "calls" && <CallLog />}
        {view === "latency" && <LatencyDashboard />}
      </div>
    </div>
  );
}
