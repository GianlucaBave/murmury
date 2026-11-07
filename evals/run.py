"""Answer-quality test bench: fixed questions, rule checks, and a model grader.

Runs every conversation in a cases file through the copilot (follow-ups see the earlier turns), checks
the format rules in code, and asks a cheap model to grade each answer against the same material. Use it
to change the answer instructions with numbers instead of impressions.

    uv run python -m evals.run evals/local/cases.json

The cases file (see cases.example.json) names the documents, an optional subset of PDF pages (to keep a
run cheap), banned terms, and the conversations. Results go to evals/results/, which git ignores.

A separate, cheaper check asks whether answers come from the loaded document at all (right price, a source,
and "not in the document" for something it never says): see evals/faithfulness.py, which needs no grader.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from copilot import material
from copilot.answer import Answer, Copilot, Usage, client

GRADER = "claude-sonnet-5-5"
GRADER_EXTRA = {"thinking": {"type": "between_tools"}, "output_config": {"effort": "low"}}
# $/M tokens, estimates: 5-minute cache write is 1.25x input, cache read 0.1x.
PRICES = {"claude-sonnet-5-5": (2.0, 2.5, 0.2, 10.0), "claude-haiku-4-5": (1.0, 1.25, 0.1, 5.0)}

GRADE_INSTRUCTIONS = """You grade answers a live-call assistant gave from the material below. The user \
glances at the answer while speaking and the listener has NOT read the material. Score each criterion \
0, 1 or 2:
- answers: it responds directly to what was asked, read in the context of the earlier turns (2), \
partly or with filler lines off the question (1), not at all (0).
- clear: a listener understands every term and every figure at first hearing: each percentage says of \
what, each amount says what and when, no labels of the plan itself or literal translations, and every line \
is a sentence the user can say aloud as is, not a label followed by fragments (2); one unclear item (1); \
more (0).
- accurate: every figure appears in the material and is used with its correct meaning (2); one figure \
wrong, misattributed or presented as something it is not (1); more (0).
Terms the listener uses in their job are clear: for an investor, ARR, EBITDA, CAC, pre-money, churn; \
for a customer, their own trade's words. Also consider the expectation given with the question. Before calling a figure wrong, look for it in the \
material: if the material states it with that meaning, it is accurate.
Reply with JSON only: {"answers": n, "clear": n, "accurate": n, "issue": "the main problem in at most 25 \
words, or empty"}"""


def subset(source: material.Source, pages: set[int] | None, keywords: list[str]) -> material.Source:
    if source.kind != "pdf" or (pages is None and not keywords):
        return source
    kept = []
    for chunk in re.split(r"\n\n(?=\[page \d+\])", source.text):
        number = int(re.match(r"\[page (\d+)\]", chunk).group(1))
        if (pages and number in pages) or any(k.lower() in chunk.lower() for k in keywords):
            kept.append(chunk)
    return material.Source(source.name, source.kind, "\n\n".join(kept))


def page_set(spec: str | None) -> set[int] | None:
    if not spec:
        return None
    out: set[int] = set()
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out |= set(range(int(a), int(b or a) + 1))
    return out


def rule_flags(text: str, banned: list[str], max_lines: int = 3, max_words: int = 14) -> list[str]:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    flags = []
    if not lines or not lines[0].upper().startswith("SAY:"):
        flags.append("no SAY first")
    else:
        say = lines[0][4:].strip()
        words = len(say.split())
        if words > 12:
            flags.append(f"SAY {words} words")
        if re.match(r"(?i)(no|not|non|nessun\w*|we don'?t|il piano non|the plan (does not|doesn'?t))\b", say) \
                and not say.lower().startswith(("that is not in our plan", "non è nel nostro piano")):
            flags.append("SAY opens with a negation")
    facts = [ln for ln in lines[1:] if ln[0] in "-•*"]
    stray = [ln for ln in lines[1:] if ln[0] not in "-•*"]
    if len(facts) > max_lines:
        flags.append(f"{len(facts)} lines")
    if stray:
        flags.append(f"stray text (hidden in window): {stray[0][:50]}")
    for ln in facts:
        body = re.sub(r"\[[^\]]*\]\s*$", "", ln.lstrip("-•* ")).strip()
        if len(body.split()) > max_words + 2:  # a little slack: the model counts words loosely
            flags.append(f"long line: {ln[:40]}")
        if re.match(r"^[A-Z][\w /&'’-]{0,30}:\s", body) and not re.match(r"(?i)(not in plan|non nel piano)", body):
            flags.append(f"label, not a sentence: {ln[:40]}")
        if not re.search(r"\[[^\]]+\]\s*$", ln) and not re.match(r"(?i)^[-•*]\s*(not in plan|non nel piano)", ln):
            flags.append(f"no source: {ln[:40]}")
    low = text.lower()
    flags += [f"banned: {b}" for b in banned if b.lower() in low]
    return flags


def cost(model: str, u: Usage) -> float:
    i, w, r, o = PRICES.get(model, (0, 0, 0, 0))
    return (u.input * i + u.cache_write * w + u.cache_read * r + u.output * o) / 1e6


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cases")
    parser.add_argument("--model", default="claude-sonnet-5-5")
    parser.add_argument("--only", type=int, nargs="*", help="conversation numbers to run (1-based)")
    parser.add_argument("--think", action="store_true", help="let the answer model think briefly first")
    args = parser.parse_args()

    spec = json.loads(Path(args.cases).read_text())
    base = Path(args.cases).parent
    docs = [Path(d) if Path(d).is_absolute() else base / d for d in spec["docs"]]
    sources = [subset(s, page_set(spec.get("pages")), spec.get("keywords", [])) for s in material.load(docs)]
    text = material.as_prompt(sources)
    api = client()

    def copilot() -> Copilot:
        c = Copilot(text, spec.get("situation", "a meeting"), args.model, api)
        c.system[1]["cache_control"] = {"type": "ephemeral"}  # 5 minutes is enough for a test run
        if args.think:
            c.think = True
        return c

    grader_system = [{"type": "text", "text": GRADE_INSTRUCTIONS},
                     {"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]
    spent = {"answer": Usage(), "grade": Usage()}
    w = copilot().warm()
    spent["answer"].cache_write += w.cache_write
    g = api.messages.create(model=GRADER, max_tokens=1, system=grader_system, **GRADER_EXTRA,
                            messages=[{"role": "user", "content": "Reply OK."}])
    spent["grade"].add(g.usage)
    print(f"material: {w.cache_write:,} tokens cached\n", flush=True)

    conversations = spec["conversations"]
    chosen = [(n, c) for n, c in enumerate(conversations, 1) if not args.only or n in args.only]

    def run(item):
        n, turns = item
        cp, results = copilot(), []
        for turn in turns:
            answer = next(p for p in cp.answer(turn["q"]) if isinstance(p, Answer))
            cp.remember(turn["q"], answer.text)
            earlier = "\n\n".join(f"Q: {q}\nA: {a}" for q, a in cp.history[:-1])
            prompt = (f"Earlier turns:\n{earlier or '(none)'}\n\nQuestion: {turn['q']}\n"
                      f"Expectation: {turn.get('expect', '(none)')}\n\nAnswer:\n{answer.text}")
            graded = api.messages.create(model=GRADER, max_tokens=1000, system=grader_system, **GRADER_EXTRA,
                                         messages=[{"role": "user", "content": prompt}])
            raw = "".join(b.text for b in graded.content if b.type == "text")
            try:
                grade = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
            except ValueError:
                grade = {"answers": 0, "clear": 0, "accurate": 0, "issue": f"grader reply unreadable: {raw[:60]}"}
            results.append({"q": turn["q"], "answer": answer.text, "first": round(answer.first_token, 2),
                            "flags": rule_flags(answer.text, spec.get("banned", []), turn.get("parts", 3)), "grade": grade,
                            "usage": answer.usage, "grade_usage": graded.usage})
        return n, results

    with ThreadPoolExecutor(6) as pool:
        done = sorted(pool.map(run, chosen))

    total, maximum, flagged, report = 0, 0, 0, []
    for n, results in done:
        for r in results:
            for k in ("input", "cache_write", "cache_read", "output"):
                setattr(spent["answer"], k, getattr(spent["answer"], k) + getattr(r["usage"], k))
            spent["grade"].add(r["grade_usage"])
            g = r["grade"]
            score = sum(int(g.get(k, 0)) for k in ("answers", "clear", "accurate"))
            total, maximum, flagged = total + score, maximum + 6, flagged + bool(r["flags"])
            print(f"[{n}] {r['q']}\n{r['answer'].strip()}")
            print(f"  -> {score}/6 (answers {g.get('answers')}, clear {g.get('clear')}, accurate "
                  f"{g.get('accurate')}) {g.get('issue', '')}")
            if r["flags"]:
                print(f"  -> rules: {'; '.join(r['flags'])}")
            print(f"  -> first text {r['first']}s\n", flush=True)
            report.append({k: v for k, v in r.items() if k not in ("usage", "grade_usage")} | {"conversation": n})

    c = cost(args.model, spent["answer"]) + cost(GRADER, spent["grade"])
    firsts = sorted(r["first"] for r in report)
    print(f"FIRST TEXT median {firsts[len(firsts) // 2]}s, p90 {firsts[int(len(firsts) * 0.9)]}s, max {firsts[-1]}s")
    print(f"SCORE {total}/{maximum} ({100 * total / max(maximum, 1):.0f}%), answers with rule flags: {flagged}"
          f"/{len(report)}, cost about ${c:.2f}")
    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    (out / f"{time.strftime('%Y%m%d-%H%M%S')}.json").write_text(
        json.dumps({"score": total, "max": maximum, "cost": round(c, 3), "results": report}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
