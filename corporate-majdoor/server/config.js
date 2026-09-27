/**
 * Central runtime configuration. Everything is overridable with env vars so the
 * same build can run locally, in a container, or behind a reverse proxy.
 */
export const config = {
  port: Number(process.env.PORT || 4173),
  host: process.env.HOST || '0.0.0.0',

  // Live chat tuning
  chat: {
    historyLimit: Number(process.env.CHAT_HISTORY_LIMIT || 200),
    maxMessageLength: Number(process.env.CHAT_MAX_MESSAGE_LENGTH || 240),
    maxNameLength: Number(process.env.CHAT_MAX_NAME_LENGTH || 24),
    // A user may send `burst` messages quickly, then 1 message per `intervalMs`.
    rateLimit: {
      intervalMs: Number(process.env.CHAT_RATE_INTERVAL_MS || 1500),
      burst: Number(process.env.CHAT_RATE_BURST || 4),
    },
  },

  // Where the chat transcript is persisted between restarts
  dataDir: process.env.DATA_DIR || 'data',
  persistChat: process.env.PERSIST_CHAT !== 'false',
};

export default config;
