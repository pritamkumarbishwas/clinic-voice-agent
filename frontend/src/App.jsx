import { useEffect, useRef, useState } from "react";
import { Room, RoomEvent } from "livekit-client";
import "./App.css";

const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
  const roomRef = useRef(null);
  const isStartingRef = useRef(false);
  const startAbortRef = useRef(null);

  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [status, setStatus] = useState("Disconnected");
  const [transcripts, setTranscripts] = useState([]);
  const [error, setError] = useState("");

  async function startSession() {
    if (isStartingRef.current || roomRef.current) return;

    isStartingRef.current = true;
    setIsConnecting(true);

    const controller = new AbortController();
    startAbortRef.current = controller;

    let room;

    try {
      setError("");
      setStatus("Connecting...");

      const response = await fetch(`${API_URL}/api/generate-token`, {
        signal: controller.signal,
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(
          `Token request failed (${response.status}): ${detail}`
        );
      }

      const { serverUrl, token, roomName } = await response.json();

      if (controller.signal.aborted) return;

      room = new Room();
      roomRef.current = room;

      room.on(
        RoomEvent.DataReceived,
        (payload, ...eventArgs) => {
          const topic = eventArgs[2];
          if (topic !== "transcripts") return;

          try {
            const message = JSON.parse(new TextDecoder().decode(payload));
            if (message.type !== "transcript") return;

            setTranscripts((previous) => {
              const next = [...previous];

              if (
                !message.isFinal &&
                next.length > 0 &&
                !next[next.length - 1].isFinal
              ) {
                next[next.length - 1] = message;
              } else {
                next.push(message);
              }

              return next;
            });
          } catch (err) {
            console.error("Invalid transcript message", err);
          }
        }
      );

      room.on(RoomEvent.Disconnected, (reason) => {
        console.warn("LiveKit disconnected:", reason);

        if (roomRef.current === room) {
          roomRef.current = null;
          setIsConnected(false);
          setStatus("Disconnected");
        }
      });

      await room.connect(serverUrl, token);

      if (controller.signal.aborted) {
        await room.disconnect();
        return;
      }

      await room.localParticipant.setMicrophoneEnabled(true);

      if (controller.signal.aborted) {
        await room.disconnect();
        return;
      }

      setIsConnected(true);
      setStatus(`Connected · ${roomName}`);
    } catch (err) {
      if (controller.signal.aborted) {
        setStatus("Disconnected");
        return;
      }

      console.error("Could not start LiveKit session:", err);
      setError(err.message || "Connection failed");
      setStatus("Connection failed");
      setIsConnected(false);

      if (roomRef.current === room) {
        roomRef.current = null;
      }

      if (room) {
        await room.disconnect();
      }
    } finally {
      if (startAbortRef.current === controller) {
        startAbortRef.current = null;
      }

      isStartingRef.current = false;
      setIsConnecting(false);
    }
  }

  async function stopSession() {
    startAbortRef.current?.abort();
    startAbortRef.current = null;

    const room = roomRef.current;
    roomRef.current = null;

    setIsConnected(false);

    if (room) {
      await room.disconnect();
    }

    setStatus("Disconnected");
  }

  useEffect(() => {
    return () => {
      startAbortRef.current?.abort();
      roomRef.current?.disconnect();
      roomRef.current = null;
    };
  }, []);

  return (
    <main className="app">
      <section className="panel">
        <p className="eyebrow">CLINIC VOICE AI · PHASE 1</p>
        <h1>Hindi Voice Transcription</h1>
        <p className="subtitle">
          Speak naturally in Hindi, English, or Hinglish.
        </p>

        <div className="status">
          <span className="dot" />
          {status}
        </div>

        <div className="actions">
          <button
            onClick={startSession}
            disabled={isConnecting || isConnected}
          >
            {isConnecting ? "Connecting..." : "Start microphone"}
          </button>

          <button
            className="secondary"
            onClick={stopSession}
            disabled={!isConnecting && !isConnected}
          >
            Stop
          </button>
        </div>

        {error && <p className="error">{error}</p>}

        <section className="transcript">
          <h2>Live transcript</h2>

          {transcripts.length === 0 ? (
            <p className="placeholder">
              Your spoken words will appear here...
            </p>
          ) : (
            transcripts.map((item, index) => (
              <article className="transcript-item" key={index}>
                <p>{item.text}</p>
                <small>
                  {item.isFinal ? "Final transcript" : "Listening..."}
                  {item.language ? ` · ${item.language}` : ""}
                </small>
              </article>
            ))
          )}
        </section>
      </section>
    </main>
  );
}