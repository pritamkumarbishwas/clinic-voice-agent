const MICROPHONE_TITLE = "Microphone unavailable";
const CONNECTION_TITLE = "Voice connection failed";
const SERVICE_TITLE = "Voice service unavailable";

function build(title, message) {
  return { title, message };
}

export function voiceError(code, cause) {
  const error = new Error(code);
  error.code = code;
  if (cause !== undefined) error.cause = cause;
  return error;
}

export function describeVoiceError(error, stage = "connection") {
  const code = error?.code;
  const name = error?.name;
  const status = error?.status;
  const reason = error?.reasonName;
  const offline =
    typeof navigator !== "undefined" && navigator.onLine === false;

  if (code === "INSECURE_CONTEXT" || name === "SecurityError") {
    return build(
      MICROPHONE_TITLE,
      "Microphone access requires HTTPS or localhost. Open the app over a secure connection and try again."
    );
  }

  if (code === "MEDIA_UNSUPPORTED") {
    return build(
      MICROPHONE_TITLE,
      "This browser does not support microphone access. Try a recent version of Chrome, Edge, Firefox, or Safari."
    );
  }

  if (code === "MIC_UNAVAILABLE") {
    return build(
      MICROPHONE_TITLE,
      "The microphone could not be started. Check your device permissions and try again."
    );
  }

  if (code === "TOKEN_TIMEOUT") {
    return build(
      SERVICE_TITLE,
      "The voice service did not respond in time. Check your connection and try again."
    );
  }

  if (code === "AGENT_TIMEOUT") {
    return build(
      "Receptionist unavailable",
      "The receptionist did not join the call. Check that the voice agent worker and database are running, then try again."
    );
  }

  if (
    code === "PermissionDenied" ||
    name === "NotAllowedError" ||
    name === "PermissionDeniedError"
  ) {
    return build(
      "Microphone access denied",
      "Allow microphone access for this site in your browser settings, then try again."
    );
  }

  if (
    code === "NotFound" ||
    name === "NotFoundError" ||
    name === "DevicesNotFoundError"
  ) {
    return build(
      "No microphone found",
      "Connect a microphone and make sure it is selected as the default input device."
    );
  }

  if (
    code === "DeviceInUse" ||
    name === "NotReadableError" ||
    name === "TrackStartError"
  ) {
    return build(
      "Microphone is busy",
      "Another app may be using your microphone. Close it and try again."
    );
  }

  if (code === "OverconstrainedError" || name === "OverconstrainedError") {
    return build(
      MICROPHONE_TITLE,
      "Your microphone does not support the required audio settings. Try another microphone."
    );
  }

  if (status === 401 || status === 403) {
    return build(
      "Session not authorized",
      "Sign in again or remove the benchmark run label before starting the call."
    );
  }

  if (status === 429) {
    return build(
      "Too many call attempts",
      "Wait a minute, then try starting the call again."
    );
  }

  if (typeof status === "number" && status >= 500) {
    return build(
      SERVICE_TITLE,
      "The clinic voice service is temporarily unavailable. Try again in a moment."
    );
  }

  if (name === "ConnectionError" || code === "ConnectionError") {
    if (reason === "NotAllowed") {
      return build(
        "Voice session rejected",
        "Refresh the page and try starting the call again."
      );
    }

    if (reason === "ServiceNotFound") {
      return build(
        SERVICE_TITLE,
        "The LiveKit voice service is not configured correctly. Check the deployment settings."
      );
    }

    if (
      reason === "Timeout" ||
      reason === "ServerUnreachable" ||
      reason === "WebSocket"
    ) {
      return build(
        CONNECTION_TITLE,
        "The voice server could not be reached. Check your internet connection and try again."
      );
    }
  }

  if (offline) {
    return build(
      CONNECTION_TITLE,
      "You appear to be offline. Reconnect to the internet and try again."
    );
  }

  if (name === "TypeError" || name === "AbortError") {
    return build(
      SERVICE_TITLE,
      "The voice service could not be reached. Check your connection and try again."
    );
  }

  if (stage === "permission" || stage === "microphone") {
    return build(
      MICROPHONE_TITLE,
      "The microphone could not be started. Check your browser permissions and device settings."
    );
  }

  if (stage === "token") {
    return build(
      SERVICE_TITLE,
      "The call could not be started. Check your connection and try again."
    );
  }

  if (stage === "agent") {
    return build(
      "Receptionist unavailable",
      "The receptionist is not available right now. Try again in a moment."
    );
  }

  return build(
    CONNECTION_TITLE,
    "The voice call was interrupted. Check your network and start a new call."
  );
}
