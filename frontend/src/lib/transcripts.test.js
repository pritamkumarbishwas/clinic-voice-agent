import assert from "node:assert/strict";
import test from "node:test";

import { mergeTranscript } from "./transcripts.js";

const user = (text, isFinal) => ({ role: "user", text, isFinal });
const assistant = (text, isFinal) => ({ role: "assistant", text, isFinal });

test("appends a transcript to an empty list", () => {
  const message = user("hello", true);
  assert.deepEqual(mergeTranscript([], message), [message]);
});

test("replaces an in-progress transcript with the next update", () => {
  const first = user("hel", false);
  const second = user("hello", false);
  const final = user("hello there", true);

  assert.deepEqual(mergeTranscript([first], second), [second]);
  assert.deepEqual(mergeTranscript([second], final), [final]);
});

test("keeps in-progress messages from different roles separate", () => {
  const question = assistant("How can", false);
  const answer = user("I need", false);

  assert.deepEqual(mergeTranscript([question], answer), [question, answer]);
});

test("keeps repeated final words as separate turns", () => {
  const first = user("yes", true);
  const second = user("yes", true);

  assert.deepEqual(mergeTranscript([first], second), [first, second]);
});

test("does not mutate the existing transcript", () => {
  const items = [user("hello", true)];
  const next = mergeTranscript(items, assistant("hi", true));

  assert.equal(items.length, 1);
  assert.equal(next.length, 2);
});
