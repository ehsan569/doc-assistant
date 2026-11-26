import re
from pathlib import Path


def load_page(path):
    text = Path(path).read_text(encoding="utf-8")
    parts = text.split("---", 2)
    header = parts[1]
    body = parts[2]

    title = None
    for line in header.splitlines():
        if line.startswith("title:"):
            title = line.replace("title:", "").strip()

    body = re.sub(r"\[([^\]]*)\]\(\{%.*?%\}[^)]*\)", r"\1", body)
    body = re.sub(r"<img[^>]*>", "", body)
    # Kramdown styling like {:.language-sql .highlight} after inline code, and HTML comments
    body = re.sub(r"\{:[^}]*\}", "", body)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    # The website fills this in automatically; at our pinned commit it is 2.0.1
    body = body.replace("{{ site.latest_duckdb_version }}", "2.0.1")
    return {"title": title, "text": body.strip(), "file": Path(path).name}
