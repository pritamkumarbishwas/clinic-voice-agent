import { useEffect, useRef, useState } from "react";
import { Room, RoomEvent, Track } from "livekit-client";
import {
  AudioLines,
  CalendarCheck2,
  Languages,
  Loader2,
  MessageSquareText,
  Mic,
  PhoneOff,
  ShieldCheck,
  TriangleAlert,
  Volume2,
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
import { apiGet } from "@/lib/api";
import { cn } from "@/lib/utils";

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
    text: "Barge in whenever you need to clarify.",
  },
];

export default function LiveCall() {
  const roomRef = useRef(null);
  const audioElementsRef = useRef(new Map());
  const isStartingRef = useRef(false);
  const startAbortRef = useRef(null);
  const transcriptViewportRef = useRef(null);
  const transcriptPinnedRef = useRef(true);

  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [audioBlocked, setAudioBlocked] = useState(false);
  const [status, setStatus] = useState("Disconnected");
  const [transcripts, setTranscripts] = useState([]);
  const [error, setError] = useState("");
  const [runLabel, setRunLabel] = useState("");
  const [elapsed, setElapsed] = useState(0);

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
    setElapsed(0);
    transcriptPinnedRef.current = true;

    const controller = new AbortController();
    startAbortRef.current = controller;

    let room;

    try {
      setError("");
      setStatus("Requesting token...");

      const trimmedRun = runLabel.trim();
      const tokenPath = trimmedRun
        ? `/api/generate-token?run_id=${encodeURIComponent(trimmedRun)}`
        : "/api/generate-token";

      const { serverUrl, token, roomName } = await apiGet(tokenPath, {
        signal: controller.signal,
      });

      if (controller.signal.aborted) return;

      room = new Room();
      roomRef.current = room;

      room.on(RoomEvent.TrackSubscribed, attachAudio);
      room.on(RoomEvent.TrackUnsubscribed, detachAudio);

      room.on(RoomEvent.DataReceived, (payload, _participant, _kind, topic) => {
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
          stopSession("Call ended").catch((err) => {
            console.error("Could not end the call cleanly", err);
          });
        }
      });

      room.on(RoomEvent.Disconnected, (reason) => {
        console.warn("LiveKit disconnected:", reason);

        if (roomRef.current === room) {
          roomRef.current = null;
          detachAllAudio();
          setIsConnected(false);
          setAudioBlocked(false);
          setElapsed(0);
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
    setElapsed(0);

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

  useEffect(() => {
    if (!isConnected) return undefined;

    const startedAt = Date.now();
    const interval = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);

    return () => window.clearInterval(interval);
  }, [isConnected]);

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

  const phase = error
    ? "error"
    : isConnected
      ? "live"
      : isConnecting
        ? "connecting"
        : status === "Call ended"
          ? "ended"
          : "idle";

  const finalCount = transcripts.filter((item) => item.isFinal).length;
  const canStop = isConnecting || isConnected;

  return (
    <main className="space-y-6 animate-fade-up">
      <PageHeader
        icon={AudioLines}
        eyebrow="Live call"
        title="Your AI receptionist"
        description="Start a voice session and watch the conversation unfold in real time. The receptionist can check availability and book appointments while you speak."
        actions={
          <Badge
            variant={
              isConnected
                ? "success"
                : isConnecting
                  ? "warning"
                  : error
                    ? "destructive"
                    : phase === "ended"
                      ? "secondary"
                      : "outline"
            }
            className="px-3 py-1"
          >
            <span
              className={cn(
                "size-1.5 rounded-full",
                isConnected
                  ? "bg-success"
                  : isConnecting
                    ? "animate-pulse bg-warning"
                    : error
                      ? "bg-destructive"
                      : "bg-muted-foreground"
              )}
            />
            {isConnected
              ? "Live now"
              : isConnecting
                ? "Connecting"
                : error
                  ? "Needs attention"
                  : phase === "ended"
                    ? "Ended"
                    : "Ready"}
          </Badge>
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

              <StatusOrb phase={phase} status={status} elapsed={elapsed} />

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
                  <AlertTitle>Could not start the call</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <div className="mt-2">
                {canStop ? (
                  <Button
                    type="button"
                    variant={isConnecting ? "outline" : "destructive"}
                    size="xl"
                    onClick={() =>
                      stopSession(isConnecting ? "Disconnected" : "Call ended")
                    }
                    className="w-full"
                  >
                    {isConnecting ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <PhoneOff />
                    )}
                    {isConnecting ? "Cancel connection" : "End call"}
                  </Button>
                ) : (
                  <Button
                    type="button"
                    size="xl"
                    onClick={startSession}
                    className="w-full shadow-lg shadow-primary/20"
                  >
                    <Mic />
                    Start microphone
                  </Button>
                )}
              </div>

              <p className="mt-3 text-center text-[11px] leading-relaxed text-muted-foreground">
                {isConnected
                  ? "Connected to the LiveKit room. Speak normally."
                  : "Your browser will ask for microphone permission."}
              </p>
            </div>
          </Card>

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
                disabled={isConnecting || isConnected}
                className="bg-background"
              />
              <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                Use the same label for every call in a benchmark so latency is
                reported together.
              </p>
            </CardContent>
          </Card>

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
                {isConnected && (
                  <Badge variant="success">
                    <span className="size-1.5 animate-pulse rounded-full bg-success" />
                    Listening
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
              <Mic className="size-3.5" />
              Microphone {isConnected ? "active" : "idle"}
            </span>
            <span>{finalCount} final</span>
          </div>
        </Card>
      </div>
    </main>
  );
}
