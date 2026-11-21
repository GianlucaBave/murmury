from evals import detect_cv
from evals.skip import ANSWER, SKIP, Line


def make(count):
    return [Line(f"line {number}", ANSWER if number % 2 == 0 else SKIP, "question", "") for number in range(count)]


def test_every_line_is_in_exactly_one_fold():
    lines = make(23)
    parts = detect_cv.folds(lines, 5)
    assert len(parts) == 5
    assert sorted(line.text for part in parts for line in part) == sorted(line.text for line in lines)


def test_cross_validation_tests_every_line_once():
    results = detect_cv.cross_validate(make(40), 5)
    assert len(results) == 5
    assert sum(count for _, _, count in results) == 40
    assert all(false_answers + false_skips <= count for false_answers, false_skips, count in results)
