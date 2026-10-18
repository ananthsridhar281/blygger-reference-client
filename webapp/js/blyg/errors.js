// Publish-side hard error; read-side discrepancy record (mirrors core/errors.py).
export class PublishError extends Error {
  constructor(message) {
    super(message);
    this.name = "PublishError";
  }
}

export function discrepancy(type, origin, id, detail) {
  return { type, origin, id, detail };
}
