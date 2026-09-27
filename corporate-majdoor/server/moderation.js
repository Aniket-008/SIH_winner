/**
 * Input hygiene for the public chat room: strip control characters and markup,
 * collapse spam-y repetition, and mask a small list of slurs/abuses.
 * This is intentionally light - it keeps the room readable, it is not a
 * replacement for human moderation.
 */

const BLOCKED = [
  'madarchod',
  'behenchod',
  'bhenchod',
  'bhosdi',
  'chutiya',
  'gandu',
  'randi',
  'lavda',
  'fuck',
  'bitch',
  'cunt',
  'nigger',
];

const RESERVED_NAMES = ['system', 'admin', 'boss', 'moderator', 'corporate majdoor'];

export function stripUnsafe(value = '') {
  return String(value)
    // remove control chars
    .replace(/[\u0000-\u001F\u007F]/g, ' ')
    // no html/markup injection makes it into the DOM payload
    .replace(/[<>]/g, '')
    // collapse whitespace
    .replace(/\s+/g, ' ')
    .trim();
}

export function maskProfanity(text) {
  let output = text;
  for (const word of BLOCKED) {
    const pattern = new RegExp(word.split('').join('+\\s*'), 'gi');
    output = output.replace(pattern, (match) => '*'.repeat(Math.max(3, match.trim().length)));
  }
  return output;
}

function squashRepetition(text) {
  // "hiiiiiiiiiiii" -> "hiiii", "!!!!!!!!" -> "!!!!"
  return text.replace(/(.)\1{3,}/g, (_, char) => char.repeat(4));
}

export function cleanName(rawName, { maxLength = 24 } = {}) {
  let name = stripUnsafe(rawName).slice(0, maxLength);
  name = maskProfanity(name);
  if (!name) return { ok: false, reason: 'Naam to batao yaar.' };
  if (RESERVED_NAMES.includes(name.toLowerCase())) {
    return { ok: false, reason: 'That name is reserved. Try another one.' };
  }
  return { ok: true, value: name };
}

export function cleanMessage(rawText, { maxLength = 240 } = {}) {
  let text = stripUnsafe(rawText);
  if (!text) return { ok: false, reason: 'Message khaali hai.' };
  if (text.length > maxLength) text = text.slice(0, maxLength);
  text = maskProfanity(squashRepetition(text));
  return { ok: true, value: text };
}

/** Token-bucket limiter, one bucket per socket. */
export class RateLimiter {
  constructor({ intervalMs = 1500, burst = 4 } = {}) {
    this.intervalMs = intervalMs;
    this.burst = burst;
    this.buckets = new Map();
  }

  take(key, now = Date.now()) {
    const bucket = this.buckets.get(key) || { tokens: this.burst, last: now };
    const refill = ((now - bucket.last) / this.intervalMs) * 1;
    bucket.tokens = Math.min(this.burst, bucket.tokens + refill);
    bucket.last = now;

    if (bucket.tokens < 1) {
      this.buckets.set(key, bucket);
      const waitMs = Math.ceil((1 - bucket.tokens) * this.intervalMs);
      return { allowed: false, waitMs };
    }

    bucket.tokens -= 1;
    this.buckets.set(key, bucket);
    return { allowed: true, waitMs: 0 };
  }

  forget(key) {
    this.buckets.delete(key);
  }
}
