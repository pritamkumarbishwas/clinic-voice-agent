export const CONTROL_TOPIC = "control";

export function createInterruptPayload() {
  return new TextEncoder().encode(JSON.stringify({ type: "interrupt" }));
}

export function disposeAudio(entry) {
  try {
    entry.track.detach(entry.element);
  } catch (detachError) {
    console.warn("Could not detach an audio track", detachError);
  }

  try {
    entry.element.remove();
  } catch (removeError) {
    console.warn("Could not remove an audio element", removeError);
  }
}

export function disposeAllAudio(elements) {
  for (const entry of elements.values()) {
    disposeAudio(entry);
  }
  elements.clear();
}
