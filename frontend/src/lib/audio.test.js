import assert from "node:assert/strict";
import test from "node:test";

import {
  CONTROL_TOPIC,
  createInterruptPayload,
  disposeAllAudio,
  disposeAudio,
} from "./audio.js";

function fakeEntry(trackSid) {
  let detached = false;
  let removed = false;
  const entry = {
    track: {
      sid: trackSid,
      detach(element) {
        assert.equal(element, entry.element);
        detached = true;
      },
    },
    element: {
      remove() {
        removed = true;
      },
    },
  };

  return {
    entry,
    wasDetached: () => detached,
    wasRemoved: () => removed,
  };
}

test("disposeAudio detaches and removes the audio element", () => {
  const { entry, wasDetached, wasRemoved } = fakeEntry("track-1");

  disposeAudio(entry);

  assert.equal(wasDetached(), true);
  assert.equal(wasRemoved(), true);
});

test("disposeAllAudio clears every entry", () => {
  const first = fakeEntry("track-1");
  const second = fakeEntry("track-2");
  const elements = new Map([
    ["track-1", first.entry],
    ["track-2", second.entry],
  ]);

  disposeAllAudio(elements);

  assert.equal(elements.size, 0);
  assert.equal(first.wasDetached(), true);
  assert.equal(second.wasDetached(), true);
  assert.equal(first.wasRemoved(), true);
  assert.equal(second.wasRemoved(), true);
});

test("disposeAudio removes the element even if detach throws", () => {
  const originalWarn = console.warn;
  const warnings = [];
  console.warn = (...args) => warnings.push(args);
  const entry = {
    track: {
      detach() {
        throw new Error("detach failed");
      },
    },
    element: {
      remove() {
        this.removed = true;
      },
    },
  };

  try {
    disposeAudio(entry);
  } finally {
    console.warn = originalWarn;
  }

  assert.equal(entry.element.removed, true);
  assert.equal(warnings.length, 1);
});

test("disposeAudio continues when removing the element throws", () => {
  const originalWarn = console.warn;
  const warnings = [];
  console.warn = (...args) => warnings.push(args);
  const entry = {
    track: {
      detach() {},
    },
    element: {
      remove() {
        throw new Error("remove failed");
      },
    },
  };

  try {
    disposeAudio(entry);
  } finally {
    console.warn = originalWarn;
  }

  assert.equal(warnings.length, 1);
});

test("interrupt payload matches the agent control protocol", () => {
  const payload = JSON.parse(new TextDecoder().decode(createInterruptPayload()));

  assert.equal(CONTROL_TOPIC, "control");
  assert.deepEqual(payload, { type: "interrupt" });
});
