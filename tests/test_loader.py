from pathlib import Path
from src.docassist.loader import load_page

PAGES = sorted(Path("corpus/docs").glob("*.md"))


def test_there_are_20_pages():
    assert len(PAGES) == 20


def test_no_template_tags_left():
    for path in PAGES:
        page = load_page(path)
        assert "{%" not in page["text"], path.name
        assert "{{" not in page["text"], path.name


def test_header_is_removed():
    for path in PAGES:
        page = load_page(path)
        assert "redirect_from" not in page["text"], path.name
        assert page["title"], path.name


def test_no_kramdown_styling_or_html_comments_left():
    for path in PAGES:
        page = load_page(path)
        assert "{:" not in page["text"], path.name
        assert "<!--" not in page["text"], path.name
