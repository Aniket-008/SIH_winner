# 🏢 Corporate Majdoor — 9 to 5 Indian Office Radio

An ambient work-radio web app for every Indian engineer, designer, analyst and 9-to-5 hustler:
chill 2000s Bollywood music, a live public chat room, random "boss ki daant" escalations,
draggable meeting-note stickies you can scribble over, and a panic-mode fake-work IDE.

Inspired by the Corporate Majdoor radio concept — rebuilt from scratch as a complete,
runnable Node.js project (no page scraping, no copied assets).

```
npm install
npm start          # → http://localhost:4173
```

---

## ✨ Features

| Feature | What it does |
| --- | --- |
| 🎧 **Overtime Playlist** | 8 curated Bollywood tracks streamed from the rights-holders' official YouTube uploads via the IFrame Player API. Play/pause, prev/next, shuffle, draggable seek bar, volume, per-track credits. |
| 🎛️ **Offline lo-fi engine** | If YouTube is blocked by a corporate firewall, the player automatically falls back to a *generative* Web Audio lo-fi loop (chords + soft kick + vinyl hiss) so the radio never dies. |
| 🌧 **Cubicle ambience mixer** | Synthesised rain on the glass, AC hum and mechanical-keyboard bursts from the next desk — layered under the music. |
| 💬 **Live Chat** | Real-time public room over Socket.IO: presence count, typing indicator, join notices, name prompt before the first message, unread badge. Falls back to a local-only mode when the server isn't reachable. |
| 🤬 **Boss Ki Daant** | 15 escalation lines with a shaking modal, animated angry boss, randomised "Working on it Sir 🙏" replies and optional Hindi speech synthesis. Fires randomly every few minutes too. |
| 📝 **Meeting Notes** | Full-screen desk overlay: freehand canvas doodling in 5 ink colours, plus draggable/editable/removable sticky notes (Monthly Majdoor Math, Townhall, Resignation Draft…). Ink + stickies persist in `localStorage`. |
| 🚨 **Boss Aaya! (Fake Work)** | Instant full-screen VS-Code-style IDE: file explorer, Jira sprint board, self-typing `PaymentGatewayService.java` hotfix with syntax highlighting, and a rolling Gradle build log. Pauses the music and resumes it on `ESC`. It also flashes a red alert for everyone else in the chat room. |
| 🎨 **4 themes** | Corporate Majdoor, Deluxe Saloon, Midnight Overtime, Tapri Sunset — remembered per device. |
| ❤️ **Support modal** | Real, scannable UPI QR (generated into `public/img/qr.png`) + copyable UPI ID + download button. |
| 🔗 **Share sheet** | Copy link, WhatsApp / Telegram / X / LinkedIn / Reddit / email, and the native mobile share sheet. |
| ⌨️ **Shortcuts** | `Space` play·pause · `←`/`→` track · `M` mute · `C` chat · `B` boss · `N` notes · `F` fake work · `ESC` close. |
| 📱 **Responsive + a11y** | Mobile layout, `prefers-reduced-motion` support, keyboard-operable seek bar, ARIA labels. |

---

## 🗂 Project structure

```
corporate-majdoor/
├── server/
│   ├── index.js         # http + Socket.IO bootstrap, presence, alarms
│   ├── app.js           # express app: /api/health, /api/playlist, /api/chat/messages, /api/stats
│   ├── chat-store.js    # last-N message store persisted to data/messages.json
│   ├── moderation.js    # sanitising, profanity masking, token-bucket rate limiter
│   ├── playlist.js      # the Overtime Playlist (video id + title + credits)
│   └── config.js        # env-driven configuration
├── public/
│   ├── index.html       # single page: hero, player, about, FAQ, all overlays
│   ├── css/styles.css   # theme tokens + full UI
│   ├── js/
│   │   ├── main.js      # boot + wiring + shortcuts
│   │   ├── player.js    # YouTube engine with graceful fallback
│   │   ├── ambience.js  # Web Audio ambience mixer + generative lo-fi engine
│   │   ├── chat.js      # Socket.IO client, offline mode
│   │   ├── notes.js     # doodle canvas + sticky notes
│   │   ├── fakework.js  # panic-mode IDE
│   │   ├── boss.js      # escalation generator
│   │   ├── effects.js   # window rain, chai banter, alarm flash
│   │   ├── data.js      # all copy: daant lines, stickies, fake code, share links
│   │   └── ui.js        # DOM helpers, layer manager, storage, toasts
│   └── img/             # hero photo, UPI QR, favicon
└── tests/server.test.js # 9 node:test cases (API, store, moderation, rate limit)
```

## 🔌 API

| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/api/health` | uptime, listener count, current IST "shift" label |
| `GET` | `/api/playlist?mood=` | the rotation, optionally filtered (`deep-work`, `chai-break`, `late-night`) |
| `GET` | `/api/chat/messages?limit=` | recent chat transcript |
| `GET` | `/api/stats` | listeners, message count, server time |

Socket.IO events: `chat:join`, `chat:message`, `chat:typing`, `room:alarm` (client → server) and
`chat:history`, `chat:message`, `chat:typing`, `presence`, `room:alarm` (server → client).

## ⚙️ Configuration

All optional, via environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `4173` | HTTP port |
| `HOST` | `0.0.0.0` | bind address |
| `DATA_DIR` | `data` | where `messages.json` lives |
| `PERSIST_CHAT` | `true` | set `false` for an in-memory room |
| `CHAT_HISTORY_LIMIT` | `200` | messages kept in the room |
| `CHAT_MAX_MESSAGE_LENGTH` | `240` | per-message character cap |
| `CHAT_RATE_INTERVAL_MS` / `CHAT_RATE_BURST` | `1500` / `4` | anti-spam token bucket |

## 🧪 Tests

```
npm test
```

Covers the REST API, SPA/404 behaviour, static serving, chat-store trimming + persistence,
input sanitising/profanity masking and the rate limiter.

## 📦 Deploy notes

* Any Node host works (`npm ci && npm start`). Behind nginx, proxy `/socket.io/` with
  `Upgrade`/`Connection` headers so websockets survive.
* `public/` can also be hosted statically on its own — the playlist falls back to
  `public/js/fallback-playlist.js` and chat switches to local-only mode.
* To change the UPI target, regenerate the QR (any `upi://pay?pa=…` payload) and update
  `#upiId` in `public/index.html`.

## ⚖️ Credits & legal

Music is **not** hosted or re-encoded here. Each track is embedded from the rights-holder's own
YouTube upload through the official IFrame Player API and credited on screen (Sony Music India,
T-Series). Remove or replace entries in `server/playlist.js` to change the rotation.
The hero artwork is AI-generated for this project. Not affiliated with any employer — thankfully.
