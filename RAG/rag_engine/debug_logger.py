"""
rag_engine.debug_logger
──────────────────────────
Prints exactly what the hybrid retriever found and used, to the *server's own
terminal only* (plain stdout). This is never returned from any Flask route,
never appended to an LLM prompt, and never reaches the chat UI — Server.py's
API responses only ever contain {answer, chunks_used, corrected_mon}, same as
before this change.

Run with SHOW_RETRIEVAL_DEBUG=1 (the default — see config.py) to see this on
every request; set the env var to "0" to silence it.
"""

_DIM    = "\033[2m"
_BOLD   = "\033[1m"
_CYAN   = "\033[36m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_MAGENTA = "\033[35m"
_RESET  = "\033[0m"


def _truncate(text: str, n: int = 110) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def log_retrieval(query: str, parsed: dict, variants: list[str], scored: list[dict], selected: list[dict]) -> None:
    selected_ids = {c["id"] for c in selected}

    print(f"\n{_BOLD}{_CYAN}┌─ RETRIEVAL DEBUG {'─' * 50}{_RESET}")
    print(f"{_BOLD}│ Query:{_RESET} {query}")
    print(
        f"{_DIM}│ Parsed → intent={parsed['intent']}  tier={parsed['tier']}  "
        f"gen={parsed['gen']}  mon={parsed['mon'] or '—'}{_RESET}"
    )
    print(f"{_DIM}│ {len(variants)} search variants:{_RESET}")
    for v in variants:
        print(f"{_DIM}│   • {v}{_RESET}")

    print(f"{_BOLD}│ Candidates scored: {len(scored)}  |  Selected for LLM: {len(selected)}{_RESET}")
    print(f"│ {'#':<3} {'id':<6} {'score':<7} {'vec':<6} {'kw':<6} {'graph':<6} {'src':<12} chunk")
    print(f"│ {'-'*3} {'-'*6} {'-'*7} {'-'*6} {'-'*6} {'-'*6} {'-'*12} {'-'*50}")

    for i, c in enumerate(scored[:25]):  # cap terminal noise even if scored is huge
        marker = f"{_GREEN}✓{_RESET}" if c["id"] in selected_ids else " "
        src = ",".join(c["sources"]) or "-"
        title = c.get("title") or ""
        snippet = _truncate(c["text"].split("\n\n")[-1] if "\n\n" in c["text"] else c["text"], 60)
        print(
            f"│{marker}{i+1:<3} {c['id']:<6} {c['score']:.3f}   "
            f"{c['vector_score']:.3f}  {c['keyword_score']:.3f}  {c['graph_score']:.3f}  "
            f"{_YELLOW}{src:<12}{_RESET} {_MAGENTA}{_truncate(title, 30):<30}{_RESET} {snippet}"
        )

    if len(scored) > 25:
        print(f"{_DIM}│ … {len(scored) - 25} more candidates not shown{_RESET}")

    if not scored:
        print(f"{_DIM}│ (no candidates — nothing from vector or graph search){_RESET}")

    print(f"{_BOLD}{_CYAN}└{'─' * 68}{_RESET}\n")
