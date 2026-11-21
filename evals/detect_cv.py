"""Five-fold cross-validation of the classifier over all 80 labelled lines."""

from evals.detect import HELDOUT, classifier, question_mark, train
from evals.skip import ANSWER, LINES, SKIP, Line, load


def folds(lines: list[Line], k: int = 5) -> list[list[Line]]:
    """Line i goes to fold i % k. The two files are blocks of answers then skips, so every fold is balanced."""
    return [[line for index, line in enumerate(lines) if index % k == fold] for fold in range(k)]


def cross_validate(lines: list[Line], k: int = 5) -> list[tuple[int, int, int]]:
    """For each fold, train on the other folds. Returns (false answers, false skips, lines) per fold."""
    parts = folds(lines, k)
    results = []
    for held_out in range(k):
        training = [line for fold, part in enumerate(parts) if fold != held_out for line in part]
        detect = classifier(train(training))
        test = parts[held_out]
        false_answers = sum(1 for line in test if detect(line) and line.expect == SKIP)
        false_skips = sum(1 for line in test if not detect(line) and line.expect == ANSWER)
        results.append((false_answers, false_skips, len(test)))
    return results


def main() -> None:
    lines = load(LINES)[1] + load(HELDOUT)[1]
    results = cross_validate(lines)
    print("Fold  Lines  False answers  False skips  Accuracy")
    accuracies = []
    for number, (false_answers, false_skips, count) in enumerate(results, start=1):
        accuracy = 1 - (false_answers + false_skips) / count
        accuracies.append(accuracy)
        print(f"{number:<6}{count:<7}{false_answers:<15}{false_skips:<13}{accuracy:.1%}")
    total = sum(count for _, _, count in results)
    wrong_answers = sum(item[0] for item in results)
    wrong_skips = sum(item[1] for item in results)
    print()
    print(f"classifier, {len(results)}-fold, {total} lines: mean {sum(accuracies) / len(accuracies):.1%}, "
          f"min {min(accuracies):.1%}, max {max(accuracies):.1%}")
    print(f"pooled: answered when it should skip {wrong_answers}/{total // 2}, "
          f"skipped when it should answer {wrong_skips}/{total // 2}")
    mark_answers = sum(1 for line in lines if question_mark(line) and line.expect == SKIP)
    mark_skips = sum(1 for line in lines if not question_mark(line) and line.expect == ANSWER)
    print(f"question mark on the same lines: answered when it should skip {mark_answers}/{total // 2}, "
          f"skipped when it should answer {mark_skips}/{total // 2}, "
          f"accuracy {1 - (mark_answers + mark_skips) / total:.1%}")


if __name__ == "__main__":
    main()
