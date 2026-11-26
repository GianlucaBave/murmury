from time import perf_counter

from copilot import material, providers
from copilot.answer import Answer
from copilot.openai_copilot import OpenAICopilot

from evals.faithfulness import (
    FIXTURES,
    VERSIONS,
    SITUATION,
    PRICE_QUESTION,
    WARRANTY_QUESTION,
    check_price,
    check_source,
    check_not_in_document,
)

MODEL = "qwen2.5:1.5b"
CONTEXT_LIMIT = 4096


def make_sources(version):
    original = material.load([FIXTURES / version.file])

    filler = "\n\n".join(
        f"Section {i}: The distribution team reviews "
        "warehouse operations, delivery schedules, "
        "inventory records and packaging procedures."
        for i in range(400)
    )

    return original + [
        material.Source("operations.md", "md", filler)
    ]


def ask(copilot, question):
    started = perf_counter()

    answer = next(
        part
        for part in copilot.answer(question)
        if isinstance(part, Answer)
    )

    elapsed = perf_counter() - started

    text = answer.text.strip()

    if "</think>" in text:
        text = text.rsplit("</think>", 1)[-1].strip()

    if text.startswith("SAY:"):
        copilot.remember(question, text)

    return text, elapsed


def main():
    service = providers.provider("ollama")

    for enabled in (False, True):
        mode = "ON" if enabled else "OFF"

        print(f"\nRETRIEVAL {mode}", flush=True)

        scores = []
        latencies = []

        for version in VERSIONS:
            print(
                f"\nVersion {version.label}",
                flush=True,
            )

            sources = make_sources(version)
            prompt = material.as_prompt(sources)

            copilot = OpenAICopilot(
                prompt,
                SITUATION,
                service,
                "local",
                MODEL,
            )

            if enabled:
                print(
                    "Building retrieval index...",
                    flush=True,
                )

                started = perf_counter()

                copilot.enable_retrieval(
                    sources,
                    CONTEXT_LIMIT,
                )

                print(
                    f"Index setup: "
                    f"{perf_counter() - started:.2f}s",
                    flush=True,
                )

            print("Asking price question...", flush=True)

            price, price_time = ask(
                copilot,
                PRICE_QUESTION,
            )

            print("Asking warranty question...", flush=True)

            warranty, warranty_time = ask(
                copilot,
                WARRANTY_QUESTION,
            )

            wrong = next(
                item.price
                for item in VERSIONS
                if item.label != version.label
            )

            checks = {
                "Price": (
                    price.startswith("SAY:")
                    and check_price(
                        price,
                        version.price,
                        wrong,
                    )
                ),
                "Source": (
                    price.startswith("SAY:")
                    and check_source(
                        price,
                        version.file,
                        sources[0].text,
                    )
                ),
                "Warranty": (
                    warranty.startswith("SAY:")
                    and check_not_in_document(warranty)
                ),
            }

            print(f"Price answer: {price}")
            print(f"Price latency: {price_time:.2f}s")

            print(f"Warranty answer: {warranty}")
            print(f"Warranty latency: {warranty_time:.2f}s")

            for name, passed in checks.items():
                print(
                    f"{name}: "
                    f"{'PASS' if passed else 'FAIL'}"
                )

            scores.extend(checks.values())
            latencies.extend([price_time, warranty_time])

        print(f"\nRetrieval {mode} summary")
        print(f"Score: {sum(scores)}/{len(scores)}")
        print(
            f"Average latency: "
            f"{sum(latencies) / len(latencies):.2f}s"
        )


if __name__ == "__main__":
    main()
