# Contributing to Murmury

Issues, ideas and pull requests are welcome. If Murmury helps you, a star on GitHub helps others find it.

Here to learn? [LEARNING.md](LEARNING.md) walks through the code in four tracks, from tests to the Windows
port.

## Your first pull request in 30 minutes

The tests run on macOS, Windows and Linux, so most level 1 issues need no Mac (each issue says if it does).

1. **Sign the CLA first.** Read the short [agreement](docs/CLA.md) and sign it with your GitHub account
   on [CLA Assistant](https://cla-assistant.io/GianlucaBave/murmury) (one click). Make sure the email on
   your commits is one your GitHub account knows (`git config user.email`): a commit from an unknown email
   blocks the check and the merge.
2. **Get the code and the tools.** Install [uv](https://docs.astral.sh/uv/), then:

   ```bash
   git clone https://github.com/YOUR-NAME/murmury && cd murmury
   uv sync
   ```

   (Fork the repository on GitHub first, and clone your fork.)
3. **Run the tests.** They should all pass before you change anything:

   ```bash
   MURMURY_TEST_SETTINGS=1 uv run --with pytest python -m pytest tests -q
   ```

   On Windows PowerShell: `$env:MURMURY_TEST_SETTINGS="1"; uv run --with pytest python -m pytest tests -q`
4. **Pick an issue.** Choose a [level 1 issue nobody has yet](https://github.com/GianlucaBave/murmury/issues?q=is%3Aopen+label%3A%22level+1%22+no%3Aassignee).
   Each one says which files to touch, what to check and when it's done.
5. **Claim it with a short plan.** Comment on the issue: which file you'll add or change and what you'll
   test. We pick the clearest plan, not the first comment, and give priority to people who haven't
   contributed yet. Wait until it is assigned to you before you write code.
6. **Open the pull request.** Run the tests again, push to a branch on your fork and open a pull request
   with "Closes #N" in the description.

## Run the app from source

You need a Mac with Apple Silicon, macOS 13 or later, [uv](https://docs.astral.sh/uv/) and the Xcode command
line tools.

```bash
git clone https://github.com/GianlucaBave/murmury && cd murmury
swiftc -O audiotap/main.swift -o audiotap/audiotap -framework ScreenCaptureKit -framework AVFoundation -framework CoreMedia
uv run python -m copilot.app
```

The first start downloads the speech model (Whisper large-v3-turbo, about 1.6 GB) and macOS asks for screen
recording permission, which is how the app hears the call's audio.

## Where things live

| Path | What |
|---|---|
| `audiotap/main.swift` | system audio and mic capture (ScreenCaptureKit) |
| `copilot/listen.py` | live listening: audio from the helper, cut into utterances |
| `copilot/stt.py` | speech to text: mlx-whisper on macOS, faster-whisper elsewhere |
| `copilot/material.py` | PDF, Excel and text into one prompt block |
| `copilot/pipeline.py` | question check and answer orchestration |
| `copilot/answer.py` | Anthropic answers, answer style and formats |
| `copilot/openai_copilot.py` | every OpenAI-format service |
| `copilot/providers.py` | the AI services, keys, model lists |
| `copilot/setup.py`, `copilot/app.py` | setup window and floating answer window |
| `evals/run.py` | answer-quality bench |
| `scripts/check_hidden.py` | proves the window stays out of screen capture |
| `scripts/check_hidden_windows.py` | the same check on Windows |

## Before you open a pull request

- Keep the change small and focused; one idea per pull request.
- If you touch the answer instructions, run the bench on your own cases and put the before and after scores
  in the pull request: `uv run python -m evals.run path/to/cases.json` (`evals/cases.example.json` shows the
  format; a run costs a few cents to a few tens of cents of API usage).
- If you touch the floating window, run `uv run --with pillow python scripts/check_hidden.py` on a Mac, or
  `uv run --with pillow python scripts/check_hidden_windows.py` on Windows, and say what it printed.
- Never commit API keys, your own documents or call transcripts.

## Where to start

- Issues labelled [good first issue](https://github.com/GianlucaBave/murmury/issues?q=is%3Aopen+label%3A%22good+first+issue%22)
  are small and say what "done" looks like. `level 1`, `level 2` and `level 3` tell you the size: small,
  moderate, substantial.
- No code needed: try Murmury with a service other than Anthropic (OpenAI, Gemini, Grok, Groq, Mistral,
  OpenRouter, Ollama, LM Studio) and report what works and what breaks in
  [#3](https://github.com/GianlucaBave/murmury/issues/3).
- Have an idea that isn't in the issues? Open an issue first, so we can agree on it before you write code.

## How to take an issue

1. Comment on the issue with a short plan: what you'll change and how you'll test it. It's not first come,
   first served: the issue goes to the clearest plan, and when plans are close, to someone who hasn't
   contributed yet. We usually assign within a day or two.
2. One issue at a time, please, so others get a chance too.
3. Open a pull request within a week, even a draft. If you need more time, say so in the issue; without news
   for a week, the issue opens up again.
4. Link the issue in the pull request ("Closes #11").

Taking part in Winter of Code Social? Nothing extra to do: we add the `wocs` and level labels to your pull
request before merging it.

## Using AI tools

AI-assisted contributions are welcome, as long as you understand the change, tested it, and can explain it
in the review. Pull requests that look mass-generated, don't run, or that the author can't explain are closed.

## Contributor License Agreement

On your first pull request, CLA Assistant asks you to sign a short [agreement](docs/CLA.md) with one click.
You keep the copyright of your work; the agreement also lets the project use it under other licences.
