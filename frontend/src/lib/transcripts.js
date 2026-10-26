export function mergeTranscript(items, message) {
  const last = items[items.length - 1];

  if (last && !last.isFinal && last.role === message.role) {
    return [...items.slice(0, -1), message];
  }

  return [...items, message];
}
