import { useEffect, useRef, useState } from "react";
import { Room, RoomEvent, Track } from "livekit-client";
import { apiGet } from "./lib/api";

function mergeTranscript(items, message) {
  const next = [...items];
  const last = next[next.length - 1];

  if (!message.isFinal && last && !last.isFinal && last.role === message.role) {
    next[next.length - 1] = message;
    return next;
  }

  if (message.isFinal && last && !last.isFinal && last.role === message.role) {
    next[next.length - 1] = message;
    return next;
  }

  if (
    message.isFinal &&
    last &&
    last.isFinal &&
    last.role === message.role &&
    last.text === message.text
  ) {
    return items;
  }

  next.push(message);
  return next;
}

export default function LiveCall() {
  const roomRef = useRef(null);
  const audioElementsRef = useRef(new Map());
  const isStartingRef = useRef(false);
  const startAbortRef = useRef(null);

  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [audioBlocked, setAudioBlocked] = useState(false);
  const [status, setStatus] = useState("Disconnected");
  const [transcripts, setTranscripts] = useState([]);
  const [error, setError] = useState("");

  function attachAudio(track) {
    if (track.kind !== Track.Kind.Audio) return;

    const existing = audioElementsRef.current.get(track.sid);
    if (existing) return;

    const element = track.attach();
    element.autoplay = true;
    element.style.display = "none";
    document.body.appendChild(element);
    audioElementsRef.current.set(track.sid, element);
  }

  function detachAudio(track) {
    const element = audioElementsRef.current.get(track.sid);
    if (!element) return;

    track.detach(element);
    element.remove();
    audioElementsRef.current.delete(track.sid);
  }

  function detachAllAudio() {
    for (const element of audioElementsRef.current.values()) {
      element.remove();
    }
    audioElementsRef.current.clear();
  }

  async function startSession() {
    if (isStartingRef.current || roomRef.current) return;

    isStartingRef.current = true;
    setIsConnecting(true);
    setTranscripts([]);

    const controller = new AbortController();
    startAbortRef.current = controller;

    let room;

    try {
      setError("");
      setStatus("Requesting token...");

      const { serverUrl, token, roomName } = await apiGet(
        "/api/generate-token",
        { signal: controller.signal }
      );

      if (controller.signal.aborted) return;

      room = new Room();
      roomRef.current = room;

      room.on(RoomEvent.TrackSubscribed, attachAudio);
      room.on(RoomEvent.TrackUnsubscribed, detachAudio);

      room.on(RoomEvent.DataReceived, (payload, ...eventArgs) => {
        const topic = eventArgs[2];
        if (topic !== "transcripts") return;

        try {
          const message = JSON.parse(new TextDecoder().decode(payload));
          if (message.type !== "transcript" || !message.text) return;

          const normalized = {
            ...message,
            role: message.role === "assistant" ? "assistant" : "user",
            isFinal: Boolean(message.isFinal),
          };

          setTranscripts((previous) =>
            mergeTranscript(previous, normalized)
          );
        } catch (err) {
          console.error("Invalid transcript message", err);
        }
      });

      room.on(RoomEvent.AudioPlaybackStatusChanged, () => {
        setAudioBlocked(!room.canPlaybackAudio);
      });

      room.on(RoomEvent.ParticipantDisconnected, (participant) => {
        const remaining = [...room.remoteParticipants.values()].filter(
          (remote) => remote.identity !== participant.identity
        );

        if (remaining.length === 0) {
          stopSession("Call ended");
        }
      });

      room.on(RoomEvent.Disconnected, (reason) => {
        console.warn("LiveKit disconnected:", reason);

        if (roomRef.current === room) {
          roomRef.current = null;
          detachAllAudio();
          setIsConnected(false);
          setAudioBlocked(false);
          setStatus("Disconnected");
        }
      });

      setStatus("Connecting...");
      await room.connect(serverUrl, token);

      if (controller.signal.aborted) {
        await room.disconnect();
        return;
      }

      await room.localParticipant.setMicrophoneEnabled(true);

      try {
        await room.startAudio();
        setAudioBlocked(false);
      } catch (audioError) {
        console.warn("Audio playback needs a user gesture", audioError);
        setAudioBlocked(true);
      }

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

      detachAllAudio();

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

  async function enableAudio() {
    const room = roomRef.current;
    if (!room) return;

    try {
      await room.startAudio();
      setAudioBlocked(false);
    } catch (err) {
      console.error("Could not start audio playback", err);
    }
  }

  async function stopSession(finalStatus = "Disconnected") {
    startAbortRef.current?.abort();
    startAbortRef.current = null;

    const room = roomRef.current;
    roomRef.current = null;

    setIsConnected(false);
    setAudioBlocked(false);

    if (room) {
      detachAllAudio();
      await room.disconnect();
    }

    setStatus(finalStatus);
  }

  useEffect(() => {
    return () => {
      startAbortRef.current?.abort();
      detachAllAudio();
      roomRef.current?.disconnect();
      roomRef.current = null;
    };
  }, []);

  return (
    <main className="live-call">
      <section className="panel">
        <p className="eyebrow">CLINIC VOICE AI</p>
        <h1>Voice receptionist</h1>
        <p className="subtitle">
          Speak naturally in Hindi, English, or Hinglish. The AI receptionist
          can check availability and book an appointment.
        </p>

        <div className="status">
          <span className={isConnected ? "dot online" : "dot"} />
          {status}
        </div>

        {audioBlocked && (
          <div className="audio-banner" role="status">
            <span>Your browser blocked the receptionist audio.</span>
            <button type="button" onClick={enableAudio}>
              Enable audio
            </button>
          </div>
        )}

        <div className="actions">
          <button
            type="button"
            onClick={startSession}
            disabled={isConnecting || isConnected}
          >
            {isConnecting ? "Connecting..." : "Start microphone"}
          </button>

          <button
            type="button"
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
              <article
                className={`transcript-item ${item.role}`}
                key={`${item.role}-${index}`}
              >
                <strong className="speaker">
                  {item.role === "assistant" ? "AI receptionist" : "Caller"}
                </strong>
                <p>{item.text}</p>
                <small>{item.isFinal ? "Final" : "Listening..."}</small>
              </article>
            ))
          )}
        </section>
      </section>
    </main>
  );
}
