import { useEffect, useRef, useState } from "react";
import {
  DisconnectReason,
  MediaDeviceFailure,
  ParticipantKind,
  Room,
  RoomEvent,
  Track,
} from "livekit-client";
import {
  AudioLines,
  CalendarCheck2,
  Languages,
  Loader2,
  MessageSquareText,
  Mic,
  MicOff,
  PhoneOff,
  ShieldCheck,
  TriangleAlert,
  Volume2,
  VolumeX,
} from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { StatusOrb } from "@/components/live/status-orb";
import { TranscriptMessage } from "@/components/live/transcript-message";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  CONTROL_TOPIC,
  createInterruptPayload,
  disposeAllAudio,
  disposeAudio,
} from "@/lib/audio";
import { mergeTranscript } from "@/lib/transcripts";
import { describeVoiceError, voiceError } from "@/lib/voice-errors";
import { cn } from "@/lib/utils";
import { useRequestTokenMutation } from "@/store/api";

const AUDIO_CAPTURE_OPTIONS = {
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,
};

const TOKEN_TIMEOUT_MS = 20_000;
const CONNECTION_TIMEOUT_MS = 20_000;
const AGENT_JOIN_TIMEOUT_MS = 30_000;
const RECONNECT_TIMEOUT_MS = 30_000;

const ENDED_DISCONNECT_REASONS = new Set([
  DisconnectReason.CLIENT_INITIATED,
  DisconnectReason.PARTICIPANT_REMOVED,
  DisconnectReason.ROOM_DELETED,
  DisconnectReason.ROOM_CLOSED,
]);

function clearTimer(ref) {
  if (ref.current !== null) {
    window.clearTimeout(ref.current);
    ref.current = null;
  }
}

const CONNECTION_STATES = {
  connected: {
    label: "Connected",
    variant: "success",
    dot: "bg-success",
  },
  connecting: {
    label: "Connecting",
    variant: "warning",
    dot: "animate-pulse bg-warning",
  },
  waiting: {
    label: "Waiting for agent",
    variant: "warning",
    dot: "animate-pulse bg-warning",
  },
  reconnecting: {
    label: "Reconnecting",
    variant: "warning",
    dot: "animate-pulse bg-warning",
  },
  error: {
    label: "Disconnected",
    variant: "destructive",
    dot: "bg-destructive",
  },
  disconnected: {
    label: "Disconnected",
    variant: "outline",
    dot: "bg-muted-foreground",
  },
};

const MICROPHONE_STATES = {
  off: {
    label: "Microphone off",
    variant: "outline",
    icon: MicOff,
    spinning: false,
  },
  requesting: {
    label: "Requesting permission",
    variant: "warning",
    icon: Loader2,
    spinning: true,
  },
  starting: {
    label: "Starting microphone",
    variant: "warning",
    icon: Loader2,
    spinning: true,
  },
  active: {
    label: "Listening",
    variant: "success",
    icon: Mic,
    spinning: false,
  },
  muted: {
    label: "Microphone muted",
    variant: "warning",
    icon: MicOff,
    spinning: false,
  },
};

const transcriptDecoder = new TextDecoder();

function findAgent(room) {
  let fallback = null;
  let remoteCount = 0;

  for (const participant of room.remoteParticipants.values()) {
    if (participant.kind === ParticipantKind.AGENT) return participant;
    fallback = participant;
    remoteCount += 1;
  }

  return remoteCount === 1 ? fallback : null;
}

function hasAgent(room) {
  return Boolean(findAgent(room));
}

function isAgentParticipant(participant, room) {
  if (participant.kind === ParticipantKind.AGENT) return true;

  for (const remote of room.remoteParticipants.values()) {
    if (remote.identity !== participant.identity) return false;
  }

  return true;
}

const TIPS = [
  {
    icon: Languages,
    title: "Speak naturally",
    text: "Use Hindi, English, or Hinglish.",
  },
  {
    icon: CalendarCheck2,
    title: "Real appointments",
    text: "Availability and booking tools are live.",
  },
  {
    icon: ShieldCheck,
    title: "Safe to interrupt",
    text: "Speak over the AI or tap Stop AI voice.",
  },
];

export default function LiveCall({ admin = false }) {
  const [requestToken] = useRequestTokenMutation();
  const roomRef = useRef(null);
  const roomCleanupRef = useRef(null);
  const audioElementsRef = useRef(new Map());
  const startInFlightRef = useRef(false);
  const tokenRequestRef = useRef(null);
  const tokenTimeoutRef = useRef(null);
  const agentTimeoutRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const sessionIdRef = useRef(0);
  const intentionalStopRef = useRef(false);
  const reconnectingRef = useRef(false);
  const mountedRef = useRef(true);
  const transcriptViewportRef = useRef(null);
  const transcriptPinnedRef = useRef(true);

  const [phase, setPhase] = useState("idle");
  const [micState, setMicState] = useState("off");
  const [audioBlocked, setAudioBlocked] = useState(false);
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const [transcripts, setTranscripts] = useState([]);
  const [error, setError] = useState(null);
  const [runLabel, setRunLabel] = useState("");
  const [startedAt, setStartedAt] = useState(null);

  function attachAudio(track) {
    if (track.kind !== Track.Kind.Audio) return;

    const existing = audioElementsRef.current.get(track.sid);
    if (existing?.track === track) return;
    if (existing) {
      disposeAudio(existing);
      audioElementsRef.current.delete(track.sid);
    }

    const element = track.attach();
    element.autoplay = true;
    element.playsInline = true;
    element.style.display = "none";
    document.body.appendChild(element);
    audioElementsRef.current.set(track.sid, { track, element });
  }

  function detachAudio(track) {
    const entry = audioElementsRef.current.get(track.sid);
    if (!entry) return;

    disposeAudio(entry);
    audioElementsRef.current.delete(track.sid);
  }

  async function stopAgentSpeech() {
    const room = roomRef.current;
    if (!room) return;

    setAgentSpeaking(false);
    try {
      await room.localParticipant.publishData(createInterruptPayload(), {
        reliable: true,
        topic: CONTROL_TOPIC,
      });
    } catch (controlError) {
      if (roomRef.current === room) {
        setAgentSpeaking(true);
      }
      console.warn("Could not stop the receptionist's voice", controlError);
    }
  }

  function clearTokenTimeout() {
    clearTimer(tokenTimeoutRef);
  }

  function clearAgentTimeout() {
    clearTimer(agentTimeoutRef);
  }

  function clearReconnectTimeout() {
    clearTimer(reconnectTimeoutRef);
  }

  function clearTimers() {
    clearTimer(tokenTimeoutRef);
    clearTimer(agentTimeoutRef);
    clearTimer(reconnectTimeoutRef);
  }

  function sessionIsCurrent(sessionId) {
    return mountedRef.current && sessionIdRef.current === sessionId;
  }

  function markConnected(sessionId) {
    if (!sessionIsCurrent(sessionId)) return;

    clearAgentTimeout();
    clearReconnectTimeout();
    setPhase("connected");
  }

  function startAgentTimeout(sessionId) {
    clearAgentTimeout();

    agentTimeoutRef.current = window.setTimeout(() => {
      if (!sessionIsCurrent(sessionId)) return;

      void endSession(
        "error",
        describeVoiceError(voiceError("AGENT_TIMEOUT"), "agent")
      );
    }, AGENT_JOIN_TIMEOUT_MS);
  }

  function startReconnectTimeout(sessionId) {
    clearReconnectTimeout();

    reconnectTimeoutRef.current = window.setTimeout(() => {
      if (!sessionIsCurrent(sessionId)) return;

      void endSession(
        "error",
        describeVoiceError(
          { name: "ConnectionError", reasonName: "ServerUnreachable" },
          "connection"
        )
      );
    }, RECONNECT_TIMEOUT_MS);
  }

  async function endSession(finalPhase = "ended", sessionError = null) {
    intentionalStopRef.current = true;
    reconnectingRef.current = false;
    startInFlightRef.current = false;
    sessionIdRef.current += 1;
    clearTimers();

    tokenRequestRef.current?.abort();
    tokenRequestRef.current = null;

    const room = roomRef.current;
    const cleanupRoom = roomCleanupRef.current;
    roomRef.current = null;
    roomCleanupRef.current = null;

    setPhase(finalPhase);
    setMicState("off");
    setAudioBlocked(false);
    setAgentSpeaking(false);
    setStartedAt(null);
    setError(sessionError);

    cleanupRoom?.();
    disposeAllAudio(audioElementsRef.current);

    if (room) {
      try {
        await room.disconnect(true);
      } catch (disconnectError) {
        console.warn("Could not close the voice session cleanly", disconnectError);
      }
    }
  }

  function attachRoomHandlers(room, sessionId) {
    const cleanups = [];
    const on = (event, handler) => {
      room.on(event, handler);
      cleanups.push(() => {
        try {
          room.off(event, handler);
        } catch (removeError) {
          console.warn("Could not remove a voice event handler", removeError);
        }
      });
    };

    on(RoomEvent.TrackSubscribed, attachAudio);
    on(RoomEvent.TrackUnsubscribed, detachAudio);

    on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
      if (!sessionIsCurrent(sessionId)) return;

      const agent = findAgent(room);
      setAgentSpeaking(
        Boolean(
          agent &&
            speakers.some((speaker) => speaker.identity === agent.identity)
        )
      );
    });

    on(RoomEvent.DataReceived, (payload, _participant, _kind, topic) => {
      if (!sessionIsCurrent(sessionId) || topic !== "transcripts") return;

      try {
        const message = JSON.parse(transcriptDecoder.decode(payload));
        if (message.type !== "transcript" || !message.text) return;

        const normalized = {
          ...message,
          role: message.role === "assistant" ? "assistant" : "user",
          isFinal: Boolean(message.isFinal),
        };

        setTranscripts((previous) => mergeTranscript(previous, normalized));
      } catch (decodeError) {
        console.error("Invalid transcript message", decodeError);
      }
    });

    on(RoomEvent.AudioPlaybackStatusChanged, () => {
      if (!sessionIsCurrent(sessionId)) return;
      setAudioBlocked(!room.canPlaybackAudio);
    });

    on(RoomEvent.LocalTrackPublished, (publication) => {
      if (!sessionIsCurrent(sessionId)) return;
      if (publication.source === Track.Source.Microphone) {
        setMicState("active");
      }
    });

    on(RoomEvent.LocalTrackUnpublished, (publication) => {
      if (!sessionIsCurrent(sessionId)) return;
      if (publication.source === Track.Source.Microphone) {
        setMicState("off");
      }
    });

    on(RoomEvent.TrackMuted, (publication, participant) => {
      if (!sessionIsCurrent(sessionId)) return;
      if (
        participant.identity === room.localParticipant.identity &&
        publication.source === Track.Source.Microphone
      ) {
        setMicState("muted");
      }
    });

    on(RoomEvent.TrackUnmuted, (publication, participant) => {
      if (!sessionIsCurrent(sessionId)) return;
      if (
        participant.identity === room.localParticipant.identity &&
        publication.source === Track.Source.Microphone
      ) {
        setMicState("active");
      }
    });

    on(RoomEvent.ParticipantConnected, () => {
      if (
        !sessionIsCurrent(sessionId) ||
        intentionalStopRef.current ||
        reconnectingRef.current
      ) {
        return;
      }

      if (hasAgent(room)) markConnected(sessionId);
    });

    on(RoomEvent.ParticipantDisconnected, (participant) => {
      if (
        !sessionIsCurrent(sessionId) ||
        intentionalStopRef.current ||
        reconnectingRef.current
      ) {
        return;
      }

      if (isAgentParticipant(participant, room)) {
        void endSession("ended");
      }
    });

    on(RoomEvent.Reconnecting, () => {
      if (!sessionIsCurrent(sessionId) || intentionalStopRef.current) return;

      reconnectingRef.current = true;
      clearAgentTimeout();
      setPhase("reconnecting");
      startReconnectTimeout(sessionId);
    });

    on(RoomEvent.Reconnected, () => {
      if (!sessionIsCurrent(sessionId) || intentionalStopRef.current) return;

      reconnectingRef.current = false;
      clearReconnectTimeout();

      if (hasAgent(room)) {
        markConnected(sessionId);
      } else {
        setPhase("waiting_for_agent");
        startAgentTimeout(sessionId);
      }
    });

    on(RoomEvent.Disconnected, (reason) => {
      if (!sessionIsCurrent(sessionId) || intentionalStopRef.current) return;

      if (ENDED_DISCONNECT_REASONS.has(reason)) {
        void endSession("ended");
        return;
      }

      const reasonName =
        reason === DisconnectReason.JOIN_FAILURE ||
        reason === DisconnectReason.SIGNAL_CLOSE
          ? "WebSocket"
          : "ServerUnreachable";

      void endSession(
        "error",
        describeVoiceError(
          { name: "ConnectionError", reasonName },
          "connection"
        )
      );
    });

    on(RoomEvent.MediaDevicesError, (mediaError) => {
      if (!sessionIsCurrent(sessionId) || intentionalStopRef.current) return;

      const failure = MediaDeviceFailure.getFailure(mediaError);
      const mappedError = failure
        ? voiceError(failure, mediaError)
        : mediaError;

      void endSession(
        "error",
        describeVoiceError(mappedError, "microphone")
      );
    });

    return () => {
      cleanups.forEach((cleanup) => cleanup());
    };
  }

  async function ensureMicrophoneAccess() {
    if (!window.isSecureContext) {
      throw voiceError("INSECURE_CONTEXT");
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      throw voiceError("MEDIA_UNSUPPORTED");
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: AUDIO_CAPTURE_OPTIONS,
    });

    stream.getTracks().forEach((track) => track.stop());
  }

  async function startSession() {
    if (startInFlightRef.current || roomRef.current) return;

    startInFlightRef.current = true;
    const sessionId = sessionIdRef.current + 1;
    sessionIdRef.current = sessionId;
    intentionalStopRef.current = false;
    reconnectingRef.current = false;
    setAgentSpeaking(false);
    setStartedAt(null);
    transcriptPinnedRef.current = true;

    let tokenRequest = null;
    let tokenTimedOut = false;
    let stage = "permission";
    let room;

    try {
      setPhase("requesting_mic");
      setMicState("requesting");
      setAudioBlocked(false);
      setError(null);
      setTranscripts([]);

      await ensureMicrophoneAccess();
      if (!sessionIsCurrent(sessionId)) return;

      setMicState("starting");
      setPhase("connecting");
      stage = "token";

      const trimmedRun = runLabel.trim();

      tokenRequest = requestToken({
        runId: trimmedRun || undefined,
      });
      tokenRequestRef.current = tokenRequest;
      tokenTimeoutRef.current = window.setTimeout(() => {
        tokenTimedOut = true;
        tokenRequest.abort();
      }, TOKEN_TIMEOUT_MS);

      const { serverUrl, token } = await tokenRequest.unwrap();
      clearTokenTimeout();
      if (!sessionIsCurrent(sessionId)) return;

      stage = "connection";

      room = new Room({
        audioCaptureDefaults: AUDIO_CAPTURE_OPTIONS,
        disconnectOnPageLeave: true,
      });
      roomRef.current = room;
      roomCleanupRef.current = attachRoomHandlers(room, sessionId);

      await room.connect(serverUrl, token, {
        peerConnectionTimeout: CONNECTION_TIMEOUT_MS,
        websocketTimeout: CONNECTION_TIMEOUT_MS,
        maxRetries: 2,
      });

      if (!sessionIsCurrent(sessionId)) {
        await room.disconnect(true);
        return;
      }

      setStartedAt(Date.now());
      stage = "microphone";

      const publication = await room.localParticipant.setMicrophoneEnabled(
        true,
        AUDIO_CAPTURE_OPTIONS
      );

      if (!sessionIsCurrent(sessionId)) {
        await room.disconnect(true);
        return;
      }

      if (!publication) {
        throw voiceError("MIC_UNAVAILABLE");
      }

      setMicState("active");

      try {
        await room.startAudio();
        setAudioBlocked(false);
      } catch (audioError) {
        console.warn("Audio playback needs a user gesture", audioError);
        setAudioBlocked(true);
      }

      if (!sessionIsCurrent(sessionId)) {
        await room.disconnect(true);
        return;
      }

      if (hasAgent(room)) {
        markConnected(sessionId);
      } else {
        setPhase("waiting_for_agent");
        startAgentTimeout(sessionId);
      }
    } catch (startError) {
      if (!sessionIsCurrent(sessionId)) return;

      const failure = tokenTimedOut
        ? describeVoiceError(voiceError("TOKEN_TIMEOUT"), "token")
        : describeVoiceError(startError, stage);

      console.error("Could not start the voice session", startError);
      await endSession("error", failure);
    } finally {
      if (tokenRequest && tokenRequestRef.current === tokenRequest) {
        clearTokenTimeout();
        tokenRequestRef.current = null;
      }

      if (sessionIdRef.current === sessionId) {
        startInFlightRef.current = false;
      }
    }
  }

  async function enableAudio() {
    const room = roomRef.current;
    if (!room) return;

    try {
      await room.startAudio();
      setAudioBlocked(false);
    } catch (audioError) {
      console.error("Could not start audio playback", audioError);
    }
  }

  useEffect(() => {
    const audioElements = audioElementsRef.current;
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
      intentionalStopRef.current = true;
      reconnectingRef.current = false;
      startInFlightRef.current = false;
      sessionIdRef.current += 1;
      clearTimer(tokenTimeoutRef);
      clearTimer(agentTimeoutRef);
      clearTimer(reconnectTimeoutRef);
      tokenRequestRef.current?.abort();
      tokenRequestRef.current = null;

      const room = roomRef.current;
      const cleanupRoom = roomCleanupRef.current;
      roomRef.current = null;
      roomCleanupRef.current = null;

      cleanupRoom?.();
      disposeAllAudio(audioElements);

      if (room) {
        room.disconnect(true).catch((disconnectError) => {
          console.warn("Could not close the voice session cleanly", disconnectError);
        });
      }
    };
  }, []);

  useEffect(() => {
    const viewport = transcriptViewportRef.current;
    if (!viewport) return undefined;

    function handleScroll() {
      transcriptPinnedRef.current =
        viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 80;
    }

    viewport.addEventListener("scroll", handleScroll, { passive: true });
    return () => viewport.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    const viewport = transcriptViewportRef.current;
    if (!viewport || !transcriptPinnedRef.current) return;

    const behavior = window.matchMedia("(prefers-reduced-motion: reduce)")
      .matches
      ? "auto"
      : "smooth";

    viewport.scrollTo({ top: viewport.scrollHeight, behavior });
  }, [transcripts]);

  const isStarting = ["requesting_mic", "connecting"].includes(phase);
  const isWaiting = phase === "waiting_for_agent";
  const isConnected = phase === "connected";
  const isReconnecting = phase === "reconnecting";
  const canStop = isStarting || isWaiting || isConnected || isReconnecting;

  const connectionKind = isConnected
    ? "connected"
    : isReconnecting
      ? "reconnecting"
      : isWaiting
        ? "waiting"
        : isStarting
          ? "connecting"
          : phase === "error"
            ? "error"
            : "disconnected";
  const connection = CONNECTION_STATES[connectionKind];
  const microphone = MICROPHONE_STATES[micState] || MICROPHONE_STATES.off;
  const MicrophoneIcon = microphone.icon;

  const orbPhase = isConnected
    ? "live"
    : isReconnecting
      ? "reconnecting"
      : isWaiting
        ? "waiting"
        : isStarting
          ? "connecting"
          : phase === "error"
            ? "error"
            : phase === "ended"
              ? "ended"
              : "idle";

  let statusText = "Ready to start a voice session.";

  if (phase === "requesting_mic") {
    statusText = "Waiting for microphone permission...";
  } else if (phase === "connecting") {
    statusText = "Connecting to the voice service...";
  } else if (phase === "waiting_for_agent") {
    statusText = "Connected. Waiting for the receptionist to join...";
  } else if (isConnected) {
    statusText = agentSpeaking
      ? "Receptionist is speaking. Interrupt or stop the voice anytime."
      : "Connected. Speak naturally.";
  } else if (isReconnecting) {
    statusText = "Connection interrupted. Reconnecting...";
  } else if (phase === "ended") {
    statusText = "Call ended. You can start a new session.";
  } else if (phase === "error") {
    statusText = "The call is disconnected. Review the error and try again.";
  }

  const finalCount = transcripts.filter((item) => item.isFinal).length;

  return (
    <div className="space-y-6 animate-fade-up">
      <PageHeader
        icon={AudioLines}
        eyebrow="Live call"
        title="Your AI receptionist"
        description="Start a voice session and watch the conversation unfold in real time. The receptionist can check availability and book appointments while you speak."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={connection.variant} className="px-3 py-1">
              <span
                className={cn("size-1.5 rounded-full", connection.dot)}
              />
              {connection.label}
            </Badge>
            <Badge variant={microphone.variant} className="px-3 py-1">
              <MicrophoneIcon
                className={cn(microphone.spinning && "animate-spin")}
              />
              {microphone.label}
            </Badge>
          </div>
        }
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
        <div className="space-y-5">
          <Card className="overflow-hidden">
            <div className="bg-linear-to-br from-primary/10 via-card to-chart-2/10 px-5 pt-5 pb-5 sm:px-7">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[10px] font-bold tracking-[0.16em] text-primary uppercase">
                    Voice session
                  </p>
                  <h2 className="mt-1 text-lg font-extrabold tracking-tight">
                    Clinic receptionist
                  </h2>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <Badge variant="outline">Hindi</Badge>
                  <Badge variant="outline">English</Badge>
                  <Badge variant="outline">Hinglish</Badge>
                </div>
              </div>

              <StatusOrb
                phase={orbPhase}
                status={statusText}
                startedAt={startedAt}
              />

              {audioBlocked && (
                <Alert variant="warning" className="mb-3 text-left">
                  <Volume2 />
                  <AlertTitle>Audio playback is blocked</AlertTitle>
                  <AlertDescription>
                    <p>Your browser needs a tap before it can play the AI voice.</p>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={enableAudio}
                      className="mt-2 border-warning/30 bg-background/60"
                    >
                      Enable audio
                    </Button>
                  </AlertDescription>
                </Alert>
              )}

              {error && (
                <Alert variant="destructive" className="mb-3 text-left">
                  <TriangleAlert />
                  <AlertTitle>{error.title}</AlertTitle>
                  <AlertDescription>{error.message}</AlertDescription>
                </Alert>
              )}

              <div className="mt-2 space-y-2">
                {isConnected && (
                  <Button
                    type="button"
                    variant="outline"
                    size="xl"
                    onClick={() => {
                      void stopAgentSpeech();
                    }}
                    className="w-full"
                  >
                    <VolumeX />
                    Stop AI voice
                  </Button>
                )}
                {canStop ? (
                  <Button
                    type="button"
                    variant={
                      isConnected || isReconnecting ? "destructive" : "outline"
                    }
                    size="xl"
                    onClick={() => {
                      void endSession("ended");
                    }}
                    className="w-full"
                  >
                    {isConnected || isReconnecting ? (
                      <PhoneOff />
                    ) : (
                      <Loader2 className="animate-spin" />
                    )}
                    {isConnected || isReconnecting
                      ? "End call"
                      : "Cancel connection"}
                  </Button>
                ) : (
                  <Button
                    type="button"
                    size="xl"
                    onClick={startSession}
                    className="w-full shadow-lg shadow-primary/20"
                  >
                    <Mic />
                    Start voice call
                  </Button>
                )}
              </div>

              <p className="mt-3 text-center text-[11px] leading-relaxed text-muted-foreground">
                {statusText}
              </p>
            </div>
          </Card>

          {admin && (
            <Card>
              <CardHeader className="pb-0">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <CardTitle className="text-sm">Benchmark run</CardTitle>
                    <CardDescription className="mt-1">
                      Group this call with a 20-call test run.
                    </CardDescription>
                  </div>
                  <Badge variant="outline">Optional</Badge>
                </div>
              </CardHeader>
              <CardContent className="pt-3">
                <Label htmlFor="run-label" className="sr-only">
                  Test run label
                </Label>
                <Input
                  id="run-label"
                  type="text"
                  value={runLabel}
                  onChange={(event) => setRunLabel(event.target.value)}
                  placeholder="e.g. baseline-1"
                  maxLength={48}
                  disabled={canStop}
                  className="bg-background"
                />
                <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                  Use the same label for every call in a benchmark so latency is
                  reported together.
                </p>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="pb-0">
              <CardTitle className="text-sm">Before you start</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 pt-3">
              {TIPS.map((tip) => {
                const Icon = tip.icon;
                return (
                  <div key={tip.title} className="flex items-start gap-3">
                    <span className="grid size-8 shrink-0 place-items-center rounded-xl bg-primary/8 text-primary">
                      <Icon className="size-4" />
                    </span>
                    <div>
                      <p className="text-xs font-semibold">{tip.title}</p>
                      <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">
                        {tip.text}
                      </p>
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </div>

        <Card className="flex h-[560px] flex-col overflow-hidden xl:h-[calc(100vh-11.5rem)] xl:min-h-[620px]">
          <CardHeader className="border-b pb-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <MessageSquareText className="size-4 text-primary" />
                  Live transcript
                </CardTitle>
                <CardDescription className="mt-1">
                  Final words appear as the conversation progresses.
                </CardDescription>
              </div>

              <div className="flex items-center gap-2">
                <Badge variant="secondary">{transcripts.length} messages</Badge>
                {isConnected && agentSpeaking && (
                  <Badge variant="secondary">
                    <Volume2 className="size-3.5" />
                    Receptionist speaking
                  </Badge>
                )}
                {isConnected && micState === "active" && (
                  <Badge variant="success">
                    <span className="size-1.5 animate-pulse rounded-full bg-success" />
                    Listening
                  </Badge>
                )}
                {isReconnecting && (
                  <Badge variant="warning">
                    <span className="size-1.5 animate-pulse rounded-full bg-warning" />
                    Reconnecting
                  </Badge>
                )}
              </div>
            </div>
          </CardHeader>

          <CardContent className="min-h-0 flex-1 p-0">
            <ScrollArea className="h-full" viewportRef={transcriptViewportRef}>
              <div
                className="space-y-4 px-4 py-5 sm:px-5"
                role="log"
                aria-live="polite"
                aria-relevant="additions"
              >
                {transcripts.length === 0 ? (
                  <EmptyState
                    icon={AudioLines}
                    title="No words yet"
                    description="Start a call and speak naturally. The AI receptionist's replies and your words will appear here."
                    className="border-0 bg-transparent py-14"
                  />
                ) : (
                  transcripts.map((item, index) => (
                    <TranscriptMessage
                      key={`${item.role}-${item.receivedAt || index}-${index}`}
                      item={item}
                    />
                  ))
                )}
              </div>
            </ScrollArea>
          </CardContent>

          <div className="flex items-center justify-between border-t px-5 py-3 text-[11px] text-muted-foreground">
            <span className="flex items-center gap-1.5">
              {micState === "active" ? (
                <Mic className="size-3.5" />
              ) : (
                <MicOff className="size-3.5" />
              )}
              {microphone.label}
            </span>
            <span>{finalCount} final</span>
          </div>
        </Card>
      </div>
    </div>
  );
}
