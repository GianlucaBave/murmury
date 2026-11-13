"""The pipeline: the question check and the live answer run in parallel, and respond() decides what shows.

No network, no keys: a fake copilot stands in, and threading.Event fixes which side finishes first.
"""

import threading

from copilot.answer import Answer, Prepared
from copilot.pipeline import respond, respond_gated

WAIT = 5  # seconds; only reached if the pipeline is stuck, so a failing test fails instead of hanging


def done(text: str) -> Answer:
    return Answer(question="q", text=text, first_token=0.0, total=0.0)


class Fake:
    """classify() and answer() each run a script the test hands in."""

    def __init__(self, classify, answer):
        self._classify, self._answer = classify, answer
        self.asked = None

    def classify(self, line, before=""):
        self.asked = (line, before)
        return self._classify()

    def answer(self, line, before=""):
        return self._answer()


def kinds(shows):
    return [(s.kind, s.text) for s in shows]


# -- respond() ----------------------------------------------------------------------------------


def test_not_a_question_shows_one_dropped_and_stops_the_answer_stream():
    go, finished, pulled_past = threading.Event(), threading.Event(), threading.Event()

    def answer():
        try:
            yield "Well"
            go.wait(WAIT)  # hold the stream until the window has shown "dropped"
            yield " then"
            pulled_past.set()  # only reached if the pipeline asks for more after being stopped
            yield " more"
            yield done("Well then more")
        finally:
            finished.set()

    fake = Fake(lambda: None, answer)
    shows = respond(fake, "Thanks for joining.", before="Hello all.")

    assert kinds([next(shows)]) == [("dropped", "")]
    go.set()
    assert list(shows) == []  # one dropped, nothing after it
    assert finished.wait(WAIT)
    assert not pulled_past.is_set()
    assert fake.asked == ("Thanks for joining.", "Hello all.")


def test_new_question_streams_live_chunks_then_live_done():
    two_queued, shown = threading.Event(), threading.Event()

    def answer():
        yield "Hel"
        yield "lo"
        two_queued.set()  # the pipeline asked for a third part, so the first two are queued
        shown.wait(WAIT)
        yield " world"
        yield done("Hello world")

    def classify():
        two_queued.wait(WAIT)  # the verdict comes after two chunks: they are held, then shown together
        return "NEW"

    shows = respond(Fake(classify, answer), "What is the revenue?")

    first = next(shows)
    assert (first.kind, first.text) == ("live-chunk", "Hello")
    shown.set()
    assert kinds(shows) == [("live-chunk", " world"), ("live-done", "Hello world")]


def test_prepared_shows_first_then_live_done_replaces_it():
    shown = threading.Event()

    def answer():
        shown.wait(WAIT)  # the live answer streams only after the prepared one is up
        yield "Forty"
        yield done("Forty two")

    prepared = Prepared(question="What is the answer?", answer="42")
    shows = respond(Fake(lambda: prepared, answer), "What's the answer?")

    first = next(shows)
    assert (first.kind, first.text) == ("prepared", "42")
    shown.set()
    assert kinds(shows) == [("live-done", "Forty two")]  # its chunks don't show over the prepared answer


def test_answer_finishing_before_the_check_waits_for_the_verdict():
    answered = threading.Event()

    def answer():
        yield "Yes"
        yield done("Yes, in March")
        answered.set()  # the pipeline asked past the Answer, so it is already queued

    def classify():
        answered.wait(WAIT)
        return "NEW"

    shows = list(respond(Fake(classify, answer), "Did it ship?"))
    assert answered.is_set()
    assert kinds(shows) == [("live-done", "Yes, in March")]


def test_answer_finishing_before_a_not_a_question_verdict_is_still_dropped():
    answered = threading.Event()

    def answer():
        yield "Sure"
        yield done("Sure")
        answered.set()

    def classify():
        answered.wait(WAIT)
        return None

    shows = list(respond(Fake(classify, answer), "Great to see you."))
    assert answered.is_set()
    assert kinds(shows) == [("dropped", "")]


# -- respond_gated() ----------------------------------------------------------------------------


class Gated:
    """A copilot whose answer itself says SKIP when the line is not a question, like Claude Code."""

    gatekeeps = True

    def __init__(self, *parts):
        self.parts, self.asked, self.closed = parts, None, False

    def classify(self, line, before=""):
        raise AssertionError("a gatekeeping copilot is never asked to classify")

    def answer(self, line, before=""):
        self.asked = (line, before)
        try:
            yield from self.parts
        except GeneratorExit:
            self.closed = True
            raise


def test_gated_skip_split_over_chunks_is_dropped_and_closes_the_stream():
    fake = Gated("SK", "IP", "never shown", done("SKIP never shown"))
    assert kinds(respond_gated(fake, "Thanks for joining.")) == [("dropped", "")]
    assert fake.closed


def test_gated_answer_streams_once_it_cannot_be_skip():
    fake = Gated("Ye", "s, in", " March", done("Yes, in March"))
    assert kinds(respond_gated(fake, "Did it ship?", before="We planned Q1.")) == [
        ("live-chunk", "Yes, in"),
        ("live-chunk", " March"),
        ("live-done", "Yes, in March"),
    ]
    assert fake.asked == ("Did it ship?", "We planned Q1.")


def test_gated_short_answer_shows_what_was_held():
    fake = Gated("No", done("No"))
    assert kinds(respond_gated(fake, "Is it late?")) == [("live-chunk", "No"), ("live-done", "No")]


def test_gated_skip_with_no_chunks_is_dropped():
    assert kinds(respond_gated(Gated(done("SKIP")), "Hi.")) == [("dropped", "")]


def test_respond_hands_a_gatekeeping_copilot_to_respond_gated():
    fake = Gated("SKIP", done("SKIP"))
    assert kinds(respond(fake, "Thanks.", before="Hi.")) == [("dropped", "")]
    assert fake.asked == ("Thanks.", "Hi.")
