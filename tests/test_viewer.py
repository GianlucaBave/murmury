import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from copilot.viewer import after_name, page_from_tag, pdf_index


def test_after_name_removes_the_file_name_and_its_separator():
    assert after_name("plan.pdf, page 12", "plan.pdf") == "page 12"
    assert after_name("plan.pdf page 12", "plan.pdf") == "page 12"
    assert after_name("PLAN.PDF: page 12", "plan.pdf") == "page 12"
    assert after_name("notes.md#Pricing", "notes.md") == "Pricing"


def test_after_name_is_none_when_the_tag_does_not_name_the_file():
    assert after_name("page 12", "plan.pdf") is None
    assert after_name("plan.pdf.evil page 12", "plan.pdf") is None


def test_page_from_tag_reads_the_ways_a_page_is_written():
    for text, page in [("page 12", 12), ("Page 12", 12), ("p. 12", 12), ("p.12", 12),
                       ("pp. 12-13", 12), ("pages 12–14", 12), ("§4.2, page 7", 7)]:
        assert page_from_tag(text) == page, text


def test_page_from_tag_does_not_mistake_other_numbers_for_pages():
    for text in ["Table 8", "Figure 6", "§4.2", "slide 3", "sheet Summary!B4", "sheet P&L", "step 3"]:
        assert page_from_tag(text) is None, text


def test_pdf_index_opens_the_cited_page_counted_from_zero():
    assert pdf_index("page 12", "plan.pdf", 40) == (11, None)
    assert pdf_index("plan.pdf, page 12", "plan.pdf", 40) == (11, None)


def test_pdf_index_accepts_the_first_and_last_page():
    assert pdf_index("page 1", "plan.pdf", 40) == (0, None)
    assert pdf_index("page 40", "plan.pdf", 40) == (39, None)


def test_pdf_index_falls_back_to_page_1_with_a_message():
    for tag in ["page 41", "page 0"]:
        index, message = pdf_index(tag, "plan.pdf", 40)
        assert index == 0 and message, tag


def test_pdf_index_without_a_page_number_opens_page_1_and_says_so():
    index, message = pdf_index("Table 8", "plan.pdf", 40)
    assert index == 0 and message


def test_pdf_index_with_no_tag_opens_page_1_quietly():
    assert pdf_index("", "plan.pdf", 40) == (0, None)


def test_pdf_index_ignores_a_page_number_inside_the_file_name():
    assert pdf_index("page 3 notes.pdf, page 12", "page 3 notes.pdf", 40) == (11, None)

