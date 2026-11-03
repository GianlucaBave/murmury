<p align="center">
  <img src="docs/assets/banner.png" alt="Murmury: a small elf for big calls. Live answers from your own documents, hidden from screen sharing." width="100%">
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-1fa463" alt="License: GPL-3.0"></a>
  <img src="https://img.shields.io/badge/macOS-Apple%20Silicon-0e2a1d" alt="macOS, Apple Silicon">
  <a href="https://murmury.pages.dev"><img src="https://img.shields.io/badge/site-murmury.pages.dev-1fa463" alt="Website"></a>
</p>

# Murmury: the open-source Cluely alternative for Mac

**A small elf for big calls.** Murmury listens to the other side of your Zoom, Meet or Teams call on your
Mac, notices when someone asks you something, and whispers a short answer from your own documents in a
small floating window that screen sharing does not capture.

<p align="center">
  <img src="docs/assets/meeting.webp" alt="A video call where the other side asks why SMB is below plan; the Murmury window answers with two facts and their sources, while the shared screen shows only the slides." width="100%">
  <br><sub>They ask. You see the answer and its source. Your shared screen shows only your slides.</sub>
</p>

- **Your documents, your AI:** PDF, Excel, Word, PowerPoint and notes; answers come from your own API key for Claude, OpenAI,
  Gemini, Grok (xAI), Groq, Mistral or OpenRouter. Gemini, Groq and OpenRouter have free tiers.
- **Private by design:** speech is transcribed on your Mac (Whisper on Apple Silicon), nothing is saved,
  no bot joins the call.
- **Invisible on screen share:** measured, not promised: run `scripts/check_hidden.py` on your own Mac.
- **Free and open source** (GPL-3.0). Contributions welcome. If the elf helps you, a ⭐ helps the elf.

Requires a Mac with Apple Silicon (M1 or newer) and macOS 13 or later.

**Download:** [Murmury.dmg](https://github.com/GianlucaBave/murmury/releases/latest), drag it to
Applications. The build is not notarized yet, so the first time macOS blocks it: System Settings,
Privacy & Security, "Open Anyway". Or run it from source:

```bash
git clone https://github.com/GianlucaBave/murmury && cd murmury
swiftc -O audiotap/main.swift -o audiotap/audiotap -framework ScreenCaptureKit -framework AVFoundation -framework CoreMedia
uv run python -m copilot.app
```

It works with any call app and any material: a business plan before an investor call, a product spec
before a customer demo, a contract before a negotiation. Diagrams and the full walkthrough:
[`docs/architecture.html`](docs/architecture.html).

## How it works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/arch-dark.png">
  <img src="docs/assets/arch-light.png" alt="Architecture: audiotap captures the Mac's audio output with ScreenCaptureKit as 16 kHz float32 PCM; listen.py cuts it into utterances and transcribes them with mlx-whisper on the Apple GPU; pipeline.py runs a fast question check and the answer stream in parallel, sending only the line and the documents over HTTPS to the AI service you chose; app.py shows the answer in a window excluded from screen capture." width="100%">
</picture>

- **No bot joins the meeting.** Audio is read inside macOS with ScreenCaptureKit, so nothing
  appears in the call: no "Recording" badge, no extra participant.
- **Headphones or speakers both work.** The other side's audio is captured digitally before it
  reaches your output device.
- **Only their questions trigger an answer.** The live loop listens to the Mac's audio output; your
  microphone never starts an answer.
- **Audio never leaves the Mac.** Transcription runs locally; only the text of a question goes to
  the model, together with your documents.
- **Answers come from your documents only.** Every bullet names its source (section, table, sheet
  and cell). If the documents do not answer the question, the window says so instead of guessing.

## Layout

| Path | What it is |
|---|---|
| `audiotap/main.swift` | Captures system audio (`audiotap system`) or the microphone (`audiotap mic`) and streams raw float32, 16 kHz mono to stdout |
| `copilot/listen.py` | Cuts the audio into utterances and transcribes them locally (mlx-whisper, `whisper-large-v3-turbo`) |
| `copilot/material.py` | Turns chosen PDF, Excel, Word, PowerPoint and text files into one cached block; pages, sheets, tables and slides keep their source structure |
| `copilot/answer.py` | Question check and answers through the Claude API, with the material in the prompt cache; answers prepared before the call |
| `copilot/pipeline.py` | Runs the question check and the live answer in parallel and decides what the window shows |
| `copilot/setup.py` | The setup screen: documents, kind of call, names to transcribe, model |
| `copilot/app.py` | The floating window, always on top and excluded from screen sharing |
| `evals/run.py` | Test bench: fixed questions, rule checks and a model grader |
| `docs/architecture.html` | Diagrams: where each part runs, the audio path, the timeline, the window |

## Requirements

- macOS 13 or later on Apple Silicon (tested on macOS 26, arm64)
- Xcode command line tools (`swiftc`)
- [uv](https://docs.astral.sh/uv/)
- An API key for one AI service, chosen on the setup screen (`copilot/providers.py`): Anthropic, OpenAI,
  Google Gemini, xAI, Groq, Mistral or OpenRouter. The **Connection** row stores it in the macOS Keychain
  (or reads `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`, `GROQ_API_KEY`,
  `MISTRAL_API_KEY`, `OPENROUTER_API_KEY`), lists the service's models with a free call and preselects the
  suggested one (`models.json` on the site, read once a day, with built-in patterns as fallback). Anthropic
  goes through its own SDK with prompt caching and can prepare answers before the call; the others share
  `copilot/openai_copilot.py` (OpenAI chat format, the answer says SKIP for a line that is not a question).
  Never commit a key.

## Setup

```bash
swiftc -O audiotap/main.swift -o audiotap/audiotap -framework ScreenCaptureKit -framework AVFoundation -framework CoreMedia
```

```bash
uv sync
```

The first run asks for **Screen & System Audio Recording** (System Settings > Privacy & Security).
Grant it to the app you launch the copilot from. The speech model (about 1.6 GB) downloads on first use.

## Use it

```bash
uv run python -m copilot.app
```

1. **Your calls.** The app opens on the list of saved calls; press **+** for a new one. Each call keeps
   its documents (where they are, never a copy), description and settings; it is kept when you go back,
   start listening or press **Save**.
2. **The call.** Drop the documents (PDF, Excel, text), describe the call in a sentence or two ("a seed
   pitch to two investors who read our deck"), let it suggest names the transcription should get right,
   then pick an **AI service**, paste its API key (stored in the macOS Keychain) and press
   **List models**: the list comes from the service, so new models appear without an update.
3. **Answer style.** Format (*Talking points*: short sentences to say; *Key facts*: label and figure;
   *Script*: the whole answer to read), length, tone, language, sources, and your own rules under
   *How to answer*. A live preview shows the shape of a card.
4. **Start Listening.** The documents are prepared, the speech model loads (about 20 seconds; the first
   time it downloads about 1.6 GB), then the floating window shows one card per question, newest on
   top. Drag it anywhere, resize it from the bottom-right corner. Shortcuts: `⌥Space` type a question,
   `⌥K` clear.

Skip the setup screen by passing the documents on the command line:

```bash
uv run python -m copilot.app --docs plan.pdf model.xlsx --situation "a seed pitch to an investor" --provider anthropic
```

Keys can also come from the environment: `MURMURY_ANTHROPIC_API_KEY` (or `ANTHROPIC_API_KEY`),
`OPENAI_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`, `GROQ_API_KEY`, `MISTRAL_API_KEY`, `OPENROUTER_API_KEY`.

Live transcription only, in the terminal:

```bash
uv run python -m copilot.listen system
```

## Answering through Claude Code (removed from the app)

No longer offered in the app (9 October 2026): Anthropic does not allow third-party products to use a
Claude subscription login without approval. `copilot/claude_code.py` stays for its SKIP gate, used by the
OpenAI-format copilot. What it measured:


`copilot/claude_code.py` sends each line to a `claude -p` process started in advance (two are kept
ready), with the documents as its system prompt, no tools and low effort. One process per line: when the
line is not a question the model replies SKIP, the card is not shown and the process is closed, so
nothing stays in a session. A process that writes nothing for 6 seconds is replaced once. There is no
separate question check: through Claude Code it took 3 to 8 s.

Measured on 8 October 2026, full 70-page plan (88k tokens cached): first text 0.9 to 1.3 s when a
process is ready, 1.30 s median and 4.04 s worst on seven lines asked back to back; a line that is not a
question is dropped in about 1.3 s. One reply out of about twenty took 37 s, which the 6-second
replacement now cuts short.

Check Anthropic's terms before offering this in software you distribute: products built for others are
expected to use API keys rather than a Claude subscription login.

## Measured (7 October 2026, MacBook Pro, Apple Silicon)

End to end, from the moment a question finishes playing to text in the answer area, three spoken
test lines played through the Mac's audio:

| Case | First text | Full answer |
|---|---|---|
| New question, live answer (Claude Sonnet 5.5) | 0.64-0.80 s | 2.1-2.4 s |
| Expected question, answer prepared before the call | 0.50 s | live version at 2.1 s |
| Not a question (small talk) | dropped at 0.24 s | |

Why it is fast: the speech is transcribed while the person is still speaking, so when they stop the
text is usually ready; the question check (Claude Haiku 4.5, about 0.5-0.7 s) runs in parallel with the
answer, which starts at once and is dropped if the line was not a question.

Question check, calibrated on 12 lines (7 requests, 5 non-requests, including follow-ups without a
question mark): 12 of 12 correct on two runs.

Cost with Claude Sonnet 5.5 and an 84k-token document set: about $0.43 to cache the documents for an
hour, about $0.024 per question, and about $0.6 to prepare 25 expected answers before the call.

## Test bench for answer quality

`evals/run.py` runs fixed conversations (follow-ups included) through the copilot, checks the format
rules in code (SAY length, number of lines, sources, banned terms, text the window would hide) and has
a second model grade each answer 0-2 on three criteria: answers the question, clear to a listener who
has not read the documents, accurate against the material.

```bash
uv run python -m evals.run evals/local/cases.json
```

The format of a cases file is in `evals/cases.example.json`. Keep real cases in `evals/local/`, which
git ignores. Use a subset of PDF pages to keep a run cheap: about $0.30 for 14 answers on 22 pages.

## Build the app

```bash
uv run python packaging/make_icon.py
```

```bash
cd packaging && uv run pyinstaller murmury.spec --noconfirm --distpath ../dist --workpath ../build
```

The result is `dist/Murmury.app` (about 350 MB, of which 182 MB are MLX's GPU kernels). Move it to
Applications and open it from there: macOS then asks for **Screen & System Audio Recording** and
**Microphone** for Murmury itself, not for the terminal. The speech model (about 1.6 GB) downloads on
first use.

The build is signed ad hoc, not with an Apple Developer ID. On the Mac that built it, it opens normally.
Downloaded from the internet, macOS blocks it the first time: System Settings, Privacy & Security, "Open
Anyway". Signing and notarizing with a Developer ID (Apple Developer Program) removes that step.

## Privacy and use

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/share-dark.png">
  <img src="docs/assets/share-light.png" alt="Your screen shows the slides and the Murmury window; what the others see on Zoom, Meet or Teams shows only the slides. Measured: 0 pixels of the window in ScreenCaptureKit, screencapture and CGWindowListCreateImage." width="100%">
</picture>

- Nothing is saved: transcripts and answers live in memory and disappear on exit. Saved calls keep only
  names, document locations and settings.
- Audio never leaves the Mac. Only the text of a question goes to the AI service you chose, with your
  documents, on your own account. Free tiers (Gemini, OpenRouter's free models) may use it for training.
- Tell the other participants that an assistant takes notes where the law asks for it. In the EU and in
  Switzerland, transcribing someone's voice without telling them is a legal risk.
- Do not use it in exams, tests or job interviews.

The window is excluded from screen capture through macOS (`NSWindowSharingNone`). Check it on your Mac:

```bash
uv run --with pillow --with numpy python scripts/check_hidden.py
```

It shows a box set up like Murmury's window next to an ordinary one and captures the screen with
ScreenCaptureKit (what Zoom, Meet and Teams use), `screencapture` and CGWindowListCreateImage. On macOS
26.6.2 (13 October 2026) the hidden box was 0 pixels in all three, the ordinary one fully visible. Run it
again after each macOS update.

## Roadmap

- Windows version.
- Local models through Ollama or LM Studio (OpenAI-format, so mostly configuration), fully offline.
- Context from your tools before the call: Google Drive, Notion, CRM.
- Global shortcuts (today they work when the window has focus).
- Signed and notarized builds (Apple Developer ID), so macOS stops asking to "Open Anyway".

## Contributing

Issues and pull requests are welcome; [CONTRIBUTING.md](CONTRIBUTING.md) has the setup and the map of the
code. Good first steps: try it with a service other than Anthropic and
report what breaks, add a local-model provider in `copilot/providers.py`, or improve the answer
instructions in `copilot/answer.py` and measure the change with `evals/run.py` on your own cases
(`evals/cases.example.json` shows the format).

## License

GPL-3.0: use it, change it, share it; any version you distribute stays open source. See [LICENSE](LICENSE).


