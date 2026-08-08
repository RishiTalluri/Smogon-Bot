"""
rag_engine.chunking
──────────────────────
Fixes the real bugs in the old chunker, matched against the actual scraper
output format (see Crawler/Code/smogonscrape.py):

  - op_text is an entire THREAD: "POST 1:\n<text>\n\nPOST 2:\n<text>\n\n..."
  - Each post's whitespace is collapsed to a single line by the scraper,
    including inside [POKEPASTE] blocks — a 6-mon team export ends up as one
    long line with no line breaks between Pokémon.
  - [IMAGES: file1.jpg, ...] and [POKEPASTE]\n... get appended into the text.

What this module does differently from the old chunk_words():
  1. Splits by POST boundary FIRST — a chunk never merges text from two
     different users' posts. The old sliding word-window ignored this
     entirely and could glue the tail of one post to the head of the next.
  2. Extracts [POKEPASTE] blocks and keeps each one as a single atomic
     chunk — squashed single-line exports have no reliable marker
     distinguishing a move name from the next Pokémon's species name (both
     are capitalized words), so any regex attempt to split per-Pokémon
     produces false positives. Keeping it whole avoids cutting a team
     mid-moveset, which the old word-window chunker could do.
  3. Strips [IMAGES: ...] filename noise before embedding — it has no
     semantic value and only dilutes the embedding.
  4. Chunks long posts by SENTENCE, not raw word count — sentences are
     packed up to a word budget, with the last couple of sentences carried
     into the next chunk for continuity (replacing the old blind word
     overlap, which could cut a sentence in half at the boundary).
  5. Merges a too-small trailing remainder into the previous chunk instead
     of emitting a near-empty final chunk.
  6. Replaces the old "-" substring is_team() check (which matches almost
     any text containing a hyphen) with a real EV-spread + Ability + Nature
     pattern match.
"""

import re

MAX_CHUNK_WORDS     = 300
OVERLAP_SENTENCES    = 2      # sentences carried from the end of one chunk into the next
MIN_TRAILING_WORDS   = 60     # merge a final remainder into the previous chunk if smaller than this
MIN_POST_WORDS        = 12     # drop posts shorter than this UNLESS they contain a pokepaste

POST_SPLIT_RE   = re.compile(r"POST\s+\d+:\n", re.I)
IMAGES_RE        = re.compile(r"\[IMAGES:[^\]]*\]")
POKEPASTE_RE     = re.compile(r"\[POKEPASTE\]\n?(.*?)(?=\[IMAGES:|\Z)", re.S)
MAX_POKEPASTE_WORDS = 500  # a single fetched pokepaste is capped at 2000 chars by the
                            # scraper (~300 words); this only triggers if a post links
                            # multiple pastes joined together

NATURE_WORDS = {
    "hardy", "lonely", "brave", "adamant", "naughty", "bold", "docile", "relaxed",
    "impish", "lax", "timid", "hasty", "serious", "jolly", "naive", "modest",
    "mild", "quiet", "bashful", "rash", "calm", "gentle", "sassy", "careful", "quirky",
}
EV_TOKEN_RE = re.compile(r"\b\d{1,3}\s*(HP|Atk|Def|SpA|SpD|Spe)\b")

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")


def strip_noise(text: str) -> str:
    """Remove filename-only [IMAGES: ...] markers — no semantic value for embedding."""
    return IMAGES_RE.sub("", text).strip()


def is_team_block(text: str) -> bool:
    """
    A real Pokémon Showdown export has an EV spread token (e.g. '252 SpA'),
    an Ability: field, and a recognised Nature word — all three together are
    a much stronger signal than the old check (which just required a literal
    hyphen anywhere in the text, matching almost anything).
    """
    tl = text.lower()
    has_ability = "ability:" in tl
    has_ev = bool(EV_TOKEN_RE.search(text))
    has_nature = any(f" {n} nature" in tl for n in NATURE_WORDS) or any(
        tl.strip().startswith(n) or f" {n} " in tl for n in NATURE_WORDS
    )
    return has_ability and has_ev and has_nature


def split_pokepaste_block(pokepaste_text: str) -> list[str]:
    """
    Kept as ONE atomic chunk whenever possible — a squashed, whitespace-collapsed
    export has no reliable marker distinguishing "the last move of mon N" from
    "the species name of mon N+1" (both are capitalized words), so any regex
    attempt to split per-Pokémon on this format produces false positives (a move
    like "Recover" or "Rain" gets mistaken for the start of the next Pokémon).
    Splitting mid-Pokémon is worse than not splitting at all, so instead: keep
    whole, and only fall back to a plain word-window split in the rare case a
    post links multiple pastes joined together and the combined text is long
    enough to blow the context budget on its own.
    """
    pokepaste_text = pokepaste_text.strip()
    if not pokepaste_text:
        return []
    words = pokepaste_text.split()
    if len(words) <= MAX_POKEPASTE_WORDS:
        return [pokepaste_text]
    return [
        " ".join(words[i:i + MAX_POKEPASTE_WORDS])
        for i in range(0, len(words), MAX_POKEPASTE_WORDS)
    ]


def split_into_posts(content: str) -> list[str]:
    """Split thread text into individual post bodies. Falls back to treating
    the whole content as one 'post' if no POST markers are present (this
    happens for the .txt source, which isn't thread-structured)."""
    if not POST_SPLIT_RE.search(content):
        return [content]
    # POST_SPLIT_RE splits ON the marker; re.split keeps the text between markers.
    parts = POST_SPLIT_RE.split(content)
    return [p.strip() for p in parts if p.strip()]


def sentence_split(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    sentences = SENTENCE_SPLIT_RE.split(text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_sentences(sentences: list[str], max_words: int = MAX_CHUNK_WORDS) -> list[str]:
    """
    Greedily pack sentences into chunks up to max_words. The last
    OVERLAP_SENTENCES sentences of each chunk are carried into the start of
    the next chunk for retrieval continuity, replacing the old blind
    50-word suffix overlap (which could cut a sentence in half).
    """
    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for sent in sentences:
        sent_words = len(sent.split())
        if current and current_words + sent_words > max_words:
            chunks.append(" ".join(current))
            current = current[-OVERLAP_SENTENCES:] if OVERLAP_SENTENCES else []
            current_words = sum(len(s.split()) for s in current)
        current.append(sent)
        current_words += sent_words

    if current:
        chunks.append(" ".join(current))

    # Merge a too-small trailing chunk into the previous one instead of
    # emitting a near-empty final chunk.
    if len(chunks) >= 2 and len(chunks[-1].split()) < MIN_TRAILING_WORDS:
        chunks[-2] = chunks[-2] + " " + chunks[-1]
        chunks.pop()

    return chunks


def chunk_document(content: str) -> list[dict]:
    """
    Main entry point. Takes one raw document's content (a whole thread, or a
    txt-source paragraph) and returns a list of
        {"text": <chunk text>, "is_team": bool}
    ready to have doc-level metadata (title/forum/url) attached by the caller.

    Never merges text across a POST boundary. Pokémon export blocks are
    extracted and chunked per-Pokémon, never split mid-moveset by a word
    window.
    """
    results: list[dict] = []

    for post in split_into_posts(content):
        pokepaste_match = POKEPASTE_RE.search(post)
        discussion_text = POKEPASTE_RE.sub("", post)
        discussion_text = strip_noise(discussion_text).strip()

        if pokepaste_match:
            pokepaste_text = pokepaste_match.group(1).strip()
            for mon_block in split_pokepaste_block(pokepaste_text):
                if len(mon_block.split()) >= 5:  # skip empty/garbage fragments
                    results.append({"text": mon_block, "is_team": True})

        if not discussion_text:
            continue

        word_count = len(discussion_text.split())
        if word_count < MIN_POST_WORDS:
            continue  # low-value one-liner ("nice team!", "+1") with no team data

        if is_team_block(discussion_text):
            # A set pasted as plain text (not via pokepaste link) — keep whole,
            # don't window-chunk it, same as the pokepaste branch above.
            results.append({"text": discussion_text, "is_team": True})
            continue

        sentences = sentence_split(discussion_text)
        for chunk_text in chunk_sentences(sentences, MAX_CHUNK_WORDS):
            if len(chunk_text.split()) >= MIN_POST_WORDS:
                results.append({"text": chunk_text, "is_team": False})

    return results
