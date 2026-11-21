from evals import detect_llm
from evals.skip import ANSWER, SKIP, Line, Result


def result(expect, answered, seconds):
    return Result(Line("x", expect, "kind"), answered, seconds, "text" if answered else "")


def test_row_counts_both_mistakes_separately():
    results = [result(SKIP, True, 1.0), result(SKIP, False, 2.0),
               result(ANSWER, False, 3.0), result(ANSWER, True, 4.0)]
    assert detect_llm.row("m", "development", results) == ["m", "development (4)", "1/2", "1/2", "50.0%", "2.50 s"]


def test_markdown_table_has_the_detector_columns():
    rows = [["m", "development (4)", "1/2", "1/2", "50.0%", "2.50 s"]]
    lines = detect_llm.markdown(rows).splitlines()
    assert lines[0].startswith("| Detector | Lines |")
    assert lines[2] == "| " + " | ".join(rows[0]) + " |"
