# Learn by building Murmury

Murmury is a real desktop app, small enough to read in an afternoon. It listens to a call, transcribes it on
your own computer and answers the other side's questions from your documents. Working on it teaches things
that are hard to practise on toy projects: testing code that talks to an AI, measuring answer quality with
numbers, building a desktop interface, and porting audio and speech code to another operating system.

The issues are sorted into four tracks, one per level label. Start with track 1, even if you are
experienced: it is the quickest way to learn the code base, and your first pull request can be merged
within a few days.

New here? [CONTRIBUTING.md](CONTRIBUTING.md) has "Your first pull request in 30 minutes": setup, running
the tests and claiming an issue.

Teaching a course? [TEACHING.md](TEACHING.md) explains how to bring a class to Murmury.

## Track 1: tests (level 1, no Mac needed)

**What you learn:** pytest (fixtures, `tmp_path`, `monkeypatch`, `parametrize`), replacing an API or a
library with a small fake (`types.SimpleNamespace`), testing Qt widgets without a screen
(`QT_QPA_PLATFORM=offscreen`, `QTest`), and keeping tests away from real user settings.

**Read first:**

- `tests/test_vocabulary.py` and `tests/test_usage_cost.py`: short, plain tests of one function each.
- `tests/test_material.py`: files built in `tmp_path`, then read back.
- `tests/test_setup_widgets.py`: Qt widgets tested offscreen, with test settings.
- The function your issue names, and its docstring.

**Rule that matters:** tests that touch settings run with `MURMURY_TEST_SETTINGS=1`, so they write to a
separate "Murmury-test" store and never to a real user's preferences.

**Open issues:** [level 1, not assigned](https://github.com/GianlucaBave/murmury/issues?q=is%3Aopen+label%3A%22level+1%22+no%3Aassignee)

## Track 2: answer quality and evals (level 2)

**What you learn:** how an AI assistant decides whether a sentence is a question, how prompt caching keeps
the documents cheap, how to measure answers with code checks and a model grader instead of impressions, and
how to compare models (including small open-weight models running locally) on the same test.

**Read first:**

- `copilot/pipeline.py`: from a finished line to what the window shows; the question check and the live
  answer run in parallel.
- `copilot/answer.py`: the answer instructions and formats.
- `evals/faithfulness.py`: does the answer come from the document or from the model's memory?
- `evals/skip.py`: does a model stay quiet when a line is not a question, and answer when it is?
- `evals/run.py`: the answer-quality bench (`evals/cases.example.json` shows the format).

**Try it for free:** with [Ollama](https://ollama.com) and a small model, the skip and faithfulness evals
cost nothing:

```bash
uv run python -m evals.skip --provider ollama --model gemma3:4b
uv run python -m evals.faithfulness --provider ollama --model gemma3:4b
```

With Anthropic or another paid service, a run costs a few cents to a few tens of cents.

**Open issues:** [level 2, not assigned](https://github.com/GianlucaBave/murmury/issues?q=is%3Aopen+label%3A%22level+2%22+no%3Aassignee)

## Track 3: features (levels 2 and 3)

**What you learn:** building a desktop app with PySide6 (Qt for Python): frameless windows, custom
widgets, style sheets with light and dark palettes, settings that persist, global hotkeys, and work on
background threads that never freezes the interface. Some features touch macOS through PyObjC.

**Read first:**

- `copilot/setup.py`: the screen before the call (documents, kind of call, AI service).
- `copilot/app.py`: the floating answer window, hidden from screen sharing.
- `copilot/theme.py` and `copilot/chrome.py`: palettes and window buttons.
- `copilot/hotkeys.py`: global shortcuts that work while Zoom or Meet has focus.

Running the full app needs a Mac with Apple Silicon. Each issue says whether it does.

**Open issues:** [level 2](https://github.com/GianlucaBave/murmury/issues?q=is%3Aopen+label%3A%22level+2%22+no%3Aassignee)
and [level 3](https://github.com/GianlucaBave/murmury/issues?q=is%3Aopen+label%3A%22level+3%22+no%3Aassignee), not assigned.

## Track 4: the Windows port (level 3)

**What you learn:** capturing what a computer plays (ScreenCaptureKit on macOS, WASAPI loopback on
Windows), streaming raw audio between a native helper and Python, running speech-to-text on CPU or GPU
(MLX on Apple Silicon, faster-whisper with CTranslate2 elsewhere), and keeping one code base and one lock
file working on several operating systems with platform markers.

**Read first:**

- `audiotap/main.swift`: the macOS audio helper. It writes raw 16 kHz mono float32 to stdout.
- `copilot/listen.py`: reads the helper, cuts the audio into utterances, and streams partial text.
- `copilot/stt.py`: speech to text, mlx-whisper on macOS and faster-whisper everywhere else.
- `pyproject.toml`: the `sys_platform` markers that keep Mac-only packages off Windows and Linux.

**Where it stands:**

- Done: `uv sync` works on Windows and Linux ([#44](https://github.com/GianlucaBave/murmury/issues/44)),
  and speech-to-text runs there with faster-whisper ([#47](https://github.com/GianlucaBave/murmury/issues/47)).
- In progress: a Windows audio helper using WASAPI loopback ([#5](https://github.com/GianlucaBave/murmury/issues/5))
  and an audio source interface so each platform plugs in its own capture
  ([#46](https://github.com/GianlucaBave/murmury/issues/46)).
- Next: run the whole app on Windows end to end, keep the floating window out of screen sharing there, and
  package it. New issues for these will appear in this track.

## How a pull request gets merged

Every pull request is read in full and run on a Mac with the latest `main` before it is merged. The merge
comment says what was tested. If something needs changing, the review says exactly what and why, so each
review is also a lesson.
