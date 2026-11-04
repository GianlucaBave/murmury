<p align="center">
  <img src="docs/assets/banner.png" alt="Murmury: a small elf for big calls. Live answers from your own documents, hidden from screen sharing." width="100%">
</p>

<h1 align="center">The open-source Cluely alternative for Mac</h1>

<p align="center">
  Live answers from your own documents during Zoom, Meet and Teams calls,<br>
  in a small window that screen sharing doesn't capture.
</p>

<p align="center">
  <a href="https://github.com/GianlucaBave/murmury/releases/latest/download/Murmury.dmg"><img src="https://img.shields.io/badge/Download_for_Mac-Murmury.dmg-1fa463?style=for-the-badge&logo=apple&logoColor=white" alt="Download Murmury for Mac"></a>
</p>

<p align="center">
  <a href="https://github.com/GianlucaBave/murmury/releases/latest"><img src="https://img.shields.io/github/v/release/GianlucaBave/murmury?color=1fa463&label=release" alt="Latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-1fa463" alt="License: GPL-3.0"></a>
  <img src="https://img.shields.io/badge/macOS-Apple%20Silicon-0e2a1d" alt="macOS, Apple Silicon">
  <a href="https://github.com/GianlucaBave/murmury/stargazers"><img src="https://img.shields.io/github/stars/GianlucaBave/murmury?style=social" alt="GitHub stars"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#privacy-and-screen-sharing">Privacy</a> ·
  <a href="#for-developers">For developers</a> ·
  <a href="#roadmap">Roadmap</a> ·
  <a href="https://murmury.pages.dev">Website</a>
</p>

<p align="center">
  <img src="docs/assets/demo.gif" alt="A real recording: a voice asks how long the runway is; within about a second the Murmury window answers that there are about 15 months of runway, with three facts each citing q3-review.md." width="720">
  <br><sub>A real recording: the question comes through the speakers, the answer streams from <a href="docs/demo/q3-review.md"><code>docs/demo/q3-review.md</code></a>.<br>Recorded with <code>--show-in-screenshots</code>: without it, the window doesn't appear in recordings at all.</sub>
</p>

<table>
<tr>
<td width="33%" align="center" valign="top">
<img src="docs/assets/elf-paper.png" height="140" alt="">
<h3>Answers from your documents</h3>
PDF, Excel, Word, PowerPoint and notes. Every line names its source: page, sheet, cell. If your documents don't say, the window says so instead of guessing.
</td>
<td width="33%" align="center" valign="top">
<img src="docs/assets/elf-sly.png" height="140" alt="">
<h3>Hidden from screen sharing</h3>
You see the answers, the others see your slides. Measured, not promised: 0 px of the window in ScreenCaptureKit, <code>screencapture</code> and CGWindowListCreateImage.
</td>
<td width="33%" align="center" valign="top">
<img src="docs/assets/elf-whisper.png" height="140" alt="">
<h3>Private by design</h3>
Speech is transcribed on your Mac with Whisper. No bot joins the call and nothing is saved. With Ollama or LM Studio, nothing leaves the Mac at all.
</td>
</tr>
</table>

**Your AI, your choice.** Use your own key for Claude, OpenAI, Gemini, Grok (xAI), Groq, Mistral or
OpenRouter, or a model on your Mac through Ollama or LM Studio. Gemini, Groq and OpenRouter have free
tiers; local models cost nothing.

**Free and open source** (GPL-3.0). If the elf helps you, a ⭐ helps the elf.

## Quick start

1. **Download** [Murmury.dmg](https://github.com/GianlucaBave/murmury/releases/latest) and drag it to
   Applications. Needs a Mac with Apple Silicon (M1 or newer) and macOS 13 or later.
2. **Open it once from Settings.** The build is not notarized yet, so the first time macOS blocks it:
   System Settings, Privacy & Security, "Open Anyway". Then allow **Screen & System Audio Recording**.
3. **Start a call.** Add your documents, pick an AI service (or Ollama / LM Studio), press
   **Start Listening**. The speech model (about 1.6 GB) downloads the first time.

**Try it without a call:** start Murmury with [`docs/demo/q3-review.md`](docs/demo/q3-review.md) as the
document, press Start Listening, then run `zsh docs/demo/ask.sh`: a voice asks three questions through your
speakers, the way the other side of a call would.

It works with any call app and any material: a business plan before an investor call, a product spec
before a customer demo, a contract before a negotiation. Diagrams and the full walkthrough:
[`docs/architecture.html`](docs/architecture.html).

Prefer the source? See [For developers](#for-developers).

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

## Privacy and screen sharing

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/share-dark.png">
  <img src="docs/assets/share-light.png" alt="Your screen shows the slides and the Murmury window; what the others see on Zoom, Meet or Teams shows only the slides. Measured: 0 pixels of the window in ScreenCaptureKit, screencapture and CGWindowListCreateImage." width="100%">
</picture>

- Nothing is saved: transcripts and answers live in memory and disappear on exit. Saved calls keep only
  names, document locations and settings.
- Audio never leaves the Mac. Only the text of a question goes to the AI service you chose, with your
  documents, on your own account. Free tiers (Gemini, OpenRouter's free models) may use it for training.
  With Ollama or LM Studio nothing leaves the Mac at all.
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

## For developers

<details>
<summary><b>Run from source</b>: requirements, setup and command-line options</summary>

```bash
git clone https://github.com/GianlucaBave/murmury && cd murmury
swiftc -O audiotap/main.swift -o audiotap/audiotap -framework ScreenCaptureKit -framework AVFoundation -framework CoreMedia
uv run python -m copilot.app
```

### Requirements

- macOS 13 or later on Apple Silicon (tested on macOS 26, arm64)
- Xcode command line tools (`swiftc`)
- [uv](https://docs.astral.sh/uv/)
- An API key for one AI service, chosen on the setup screen (`copilot/providers.py`): Anthropic, OpenAI,
  Google Gemini, xAI, Groq, Mistral or OpenRouter. No key for a local model: start Ollama
  (`localhost:11434`) or LM Studio's server (`localhost:1234`) and give the model a long context length,
  or long documents are cut (Murmury warns you when that happens). Measured on an M5 with 24 GB, Ollama
  0.40.14, a 27,000-token document and a 32k context: `gemma3:12b` (8.2 GB) and `qwen3:8b` (5.2 GB) showed
  the first text 0.3-0.5 s after the question and the full answer in 4-10 s; reading the documents the first
  time took 89-99 s. `gemma3:12b` gave the most faithful answers; `llama3.2:3b` was fast but made up
  numbers. Speech recognition downloads its model (1.5 GB) on the first run; after that everything works
  offline. The **Connection** row stores it in the macOS Keychain
  (or reads `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`, `GROQ_API_KEY`,
  `MISTRAL_API_KEY`, `OPENROUTER_API_KEY`), lists the service's models with a free call and preselects the
  suggested one (`models.json` on the site, read once a day, with built-in patterns as fallback). Anthropic
  goes through its own SDK with prompt caching and can prepare answers before the call; the others share
  `copilot/openai_copilot.py` (OpenAI chat format, the answer says SKIP for a line that is not a question).
  Never commit a key.

### Setup

```bash
swiftc -O audiotap/main.swift -o audiotap/audiotap -framework ScreenCaptureKit -framework AVFoundation -framework CoreMedia
```

```bash
uv sync
```

The first run asks for **Screen & System Audio Recording** (System Settings > Privacy & Security).
Grant it to the app you launch the copilot from. The speech model (about 1.6 GB) downloads on first use.

### Use it

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

</details>

<details>
<summary><b>Layout</b>: what each file does</summary>

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

</details>

<details>
<summary><b>Test bench for answer quality</b></summary>

`evals/run.py` runs fixed conversations (follow-ups included) through the copilot, checks the format
rules in code (SAY length, number of lines, sources, banned terms, text the window would hide) and has
a second model grade each answer 0-2 on three criteria: answers the question, clear to a listener who
has not read the documents, accurate against the material.

```bash
uv run python -m evals.run evals/local/cases.json
```

The format of a cases file is in `evals/cases.example.json`. Keep real cases in `evals/local/`, which
git ignores. Use a subset of PDF pages to keep a run cheap: about $0.30 for 14 answers on 22 pages.

</details>

<details>
<summary><b>Build the app</b></summary>

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

</details>

<details>
<summary><b>Answering through Claude Code</b> (removed from the app)</summary>

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

</details>

## Roadmap

<img src="docs/assets/elf-drill.png" align="right" height="150" alt="">

The full list, with what is done, is in [issue #10](https://github.com/GianlucaBave/murmury/issues/10).

- Answers in your voice: a few things you wrote or said teach Murmury your phrasing, tone and length.
- Global shortcuts (today they work when the window has focus).
- Signed and notarized builds (Apple Developer ID), so macOS stops asking to "Open Anyway".
- Bigger local models on another machine: a Mac mini or PC runs the model, your laptop or phone uses it ([#16](https://github.com/GianlucaBave/murmury/issues/16)).
- Murmury on your phone ([#17](https://github.com/GianlucaBave/murmury/issues/17)) and memory across calls, opt-in and on your machine ([#18](https://github.com/GianlucaBave/murmury/issues/18)).
- Your own model: an open-weight model tuned for call answers, then fine-tuned on your Mac (MLX, LoRA) on the answers you choose to keep.
- Windows version, and context from your tools before the call: Google Drive, Notion, CRM.

## Contributing

Issues and pull requests are welcome; [CONTRIBUTING.md](CONTRIBUTING.md) has the setup and the map of the
code. Good first steps: the issues labelled
[good first issue](https://github.com/GianlucaBave/murmury/issues?q=is%3Aopen+label%3A%22good+first+issue%22)
(for example [#16](https://github.com/GianlucaBave/murmury/issues/16), a local model on another computer),
trying it with a service other than Anthropic and reporting what breaks
([#3](https://github.com/GianlucaBave/murmury/issues/3)), or improving the answer instructions in
`copilot/answer.py` and measuring the change with `evals/run.py` on your own cases
(`evals/cases.example.json` shows the format).

## License

GPL-3.0: use it, change it, share it; any version you distribute stays open source. See [LICENSE](LICENSE).
