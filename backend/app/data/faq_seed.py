"""
Ingests the FAQ knowledge-base Excel sheets (BatchSmart_FAQs.xlsx,
LabelSmart_FAQs.xlsx) into support.db, precomputing and caching a
sentence-embedding for every question so kb_service can do fast
in-memory semantic search at request time.

Run once (and again any time the Excel sheets change):
    python -m app.data.faq_seed   (run from backend/ folder)

Excel format expected (Section / Question / Answer). "Section" cells
are merged in the source sheet, so blank Section cells are forward-
filled from the row above.
"""
import sqlite3
from pathlib import Path

import openpyxl

from app.utils.embeddings import embed_texts

DB_PATH = Path(__file__).resolve().parent / "support.db"
DATA_DIR = Path(__file__).resolve().parent

# (excel filename, product label stored alongside each row)
SOURCE_FILES = [
    ("BatchSmart_FAQs.xlsx", "BatchSmart"),
    ("LabelSmart_FAQs.xlsx", "LabelSmart"),
]


def _read_faq_sheet(path: Path) -> list[tuple[str, str, str]]:
    """Returns list of (section, question, answer), forward-filling Section."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active

    rows: list[tuple[str, str, str]] = []
    current_section = ""
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):  # skip header
        section, question, answer = (row[0], row[1], row[2]) if len(row) >= 3 else (None, None, None)
        if section:
            current_section = str(section).strip()
        if not question or not answer:
            continue
        rows.append((current_section, str(question).strip(), str(answer).strip()))
    return rows


def seed() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript(
        """
        DROP TABLE IF EXISTS faq_kb;
        CREATE TABLE faq_kb (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product TEXT,
            section TEXT,
            question TEXT,
            answer TEXT,
            embedding BLOB
        );
        """
    )

    all_rows: list[tuple[str, str, str, str]] = []  # product, section, question, answer
    for filename, product in SOURCE_FILES:
        path = DATA_DIR / filename
        if not path.exists():
            print(f"Skipping {filename} (not found in {DATA_DIR})")
            continue
        for section, question, answer in _read_faq_sheet(path):
            all_rows.append((product, section, question, answer))

    if not all_rows:
        print("No FAQ rows found — nothing seeded.")
        conn.close()
        return

    questions = [q for _, _, q, _ in all_rows]
    embeddings = embed_texts(questions)  # np.ndarray, shape (n, dim)

    for (product, section, question, answer), emb in zip(all_rows, embeddings):
        cur.execute(
            "INSERT INTO faq_kb (product, section, question, answer, embedding) VALUES (?, ?, ?, ?, ?)",
            (product, section, question, answer, emb.tobytes()),
        )

    conn.commit()
    conn.close()
    print(f"Seeded {len(all_rows)} FAQ entries into {DB_PATH}")


if __name__ == "__main__":
    seed()
