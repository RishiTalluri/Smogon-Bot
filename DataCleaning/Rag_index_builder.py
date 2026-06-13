import os
import pandas as pd
import json
import pickle
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# =========================
# INPUT FILES (PUT YOUR FILE PATHS HERE)
# =========================
FILES = [
    r"..\Crawler\dataObtained\smogon_threads.csv",
    r"..\Crawler\dataObtained\smogon_threads.json",
    r"..\Crawler\dataObtained\smogon_full_text.txt"
]

# OUTPUT DIRECTORY
OUTPUT_DIR = r"..\RAG_Data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =========================
# CLEAN TEXT
# =========================
def clean_text(text):
    if text is None:
        return ""
    return str(text).strip()

# =========================
# DETECT POKEMON TEAM
# =========================
def is_team(text):
    return (
        "Ability:" in text and
        "EVs:" in text and
        "-" in text
    )

# =========================
# FORMAT DOCUMENT
# =========================
def format_doc(content, metadata):
    tag = "[POKEMON TEAM]" if is_team(content) else "[DISCUSSION]"
    return f"""{tag}
{metadata}

{content}
"""

# =========================
# PROCESS CSV
# =========================
def process_csv(path):
    print(f"\nProcessing CSV: {path}")
    df = pd.read_csv(path)

    docs = []
    for _, row in df.iterrows():
        content = clean_text(row.get("op_text"))
        if not content:
            continue

        metadata = f"""Title: {row.get('title', 'unknown')}
Forum: {row.get('forum', 'unknown')}
URL: {row.get('url', 'unknown')}"""

        docs.append(format_doc(content, metadata))

    return docs

# =========================
# PROCESS JSON
# =========================
def process_json(path):
    print(f"\nProcessing JSON: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    docs = []
    for item in data:
        content = clean_text(item.get("op_text"))
        if not content:
            continue

        metadata = f"""Title: {item.get('title', 'unknown')}
Forum: {item.get('forum', 'unknown')}
URL: {item.get('url', 'unknown')}"""

        docs.append(format_doc(content, metadata))

    return docs

# =========================
# PROCESS TXT
# =========================
def process_txt(path):
    print(f"\nProcessing TXT: {path}")

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    parts = text.split("\n\n")  # split paragraphs

    docs = []
    for part in parts:
        part = clean_text(part)
        if not part:
            continue

        metadata = f"Source: {path}"
        docs.append(format_doc(part, metadata))

    return docs

# =========================
# LOAD ALL FILES
# =========================
all_docs = []

for file in FILES:
    if file.endswith(".csv"):
        all_docs.extend(process_csv(file))
    elif file.endswith(".json"):
        all_docs.extend(process_json(file))
    elif file.endswith(".txt"):
        all_docs.extend(process_txt(file))
    else:
        print("Skipping:", file)

print("\nTotal documents:", len(all_docs))

# =========================
# CHUNKING
# =========================
def chunk_text(text, chunk_size=300, overlap=50):
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)

    return chunks

def smart_chunk(doc):
    if "[POKEMON TEAM]" in doc:
        return [doc]
    return chunk_text(doc)

chunked_docs = []
for doc in all_docs:
    chunked_docs.extend(smart_chunk(doc))

print("Total chunks:", len(chunked_docs))

# =========================
# EMBEDDINGS
# =========================
print("\nLoading model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

print("Creating embeddings...")
embeddings = model.encode(chunked_docs, show_progress_bar=True)

# =========================
# FAISS
# =========================
print("Building FAISS index...")
dim = embeddings.shape[1]
index = faiss.IndexFlatL2(dim)
index.add(np.array(embeddings))

# =========================
# SAVE
# =========================
faiss_path = os.path.join(OUTPUT_DIR, "faiss_index.bin")
docs_path = os.path.join(OUTPUT_DIR, "docs.pkl")

faiss.write_index(index, faiss_path)

with open(docs_path, "wb") as f:
    pickle.dump(chunked_docs, f)

print("\n✅ DONE")
print("Saved:")
print(f"- {faiss_path}")
print(f"- {docs_path}")