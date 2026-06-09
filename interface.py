"""
interface.py — CLI interface for The Unofficial Guide.

Presents a simple menu loop:
    1. Ask your own question
    2. Select a demo question (1–5)
    3. Exit
"""

import sys
import textwrap
import threading
import itertools
import time

from retriever import retrieve
from generator import generate
from logger import get_session_logger

logger = get_session_logger()

# ---------------------------------------------------------------------------
# Demo questions
# ---------------------------------------------------------------------------

DEMO_QUESTIONS = [
    "Is CS2204 a difficult course?",
    "What is CS4407 about?",
    "Has anyone ever encountered any professors that give good feedback?",
    "Are there any courses on databases in this degree?",
    "Are there any tips for passing CS1102?",
]

# ---------------------------------------------------------------------------
# Spinner
# ---------------------------------------------------------------------------

class _Spinner:
    """
    Displays an animated spinner on stdout while the answer is being generated.
    Runs on a background thread so the main thread can block on the Groq call.
    """

    def __init__(self, message: str = "Thinking") -> None:
        self._message = message
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self) -> None:
        for frame in itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]):
            if self._stop_event.is_set():
                break
            sys.stdout.write(f"\r{self._message} {frame} ")
            sys.stdout.flush()
            time.sleep(0.08)
        # Clear the spinner line
        sys.stdout.write("\r" + " " * (len(self._message) + 4) + "\r")
        sys.stdout.flush()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join()


# ---------------------------------------------------------------------------
# ANSI color helpers
# ---------------------------------------------------------------------------

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_CYAN   = "\033[36m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"


def _c(text: str, *codes: str) -> str:
    """Wrap text with ANSI codes and reset at the end."""
    return "".join(codes) + text + _RESET


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _print_banner() -> None:
    print()
    print(_c("╔══════════════════════════════════════════════╗", _CYAN, _BOLD))
    print(_c("║              The Unofficial Guide            ║", _CYAN, _BOLD))
    print(_c("║  Your RAG-powered assistant for CS students  ║", _CYAN, _BOLD))
    print(_c("╚══════════════════════════════════════════════╝", _CYAN, _BOLD))
    print()


def _print_menu() -> None:
    print(_c("Demo questions:", _BOLD))
    for i, q in enumerate(DEMO_QUESTIONS, 1):
        print(_c(f"  {i}.", _YELLOW) + f" {q}")
    print()
    print(
        _c("  [1–5]", _YELLOW) + " demo question  " +
        _c("[a]", _YELLOW) + " ask your own  " +
        _c("[x]", _YELLOW) + " exit"
    )
    print()


def _ask_and_answer(query: str) -> None:
    """Run the full RAG pipeline for a query and print the answer."""
    logger.info(f"User query: {query}")
    print()

    spinner = _Spinner("Thinking")
    spinner.start()

    try:
        chunks = retrieve(query)
        answer = generate(query, chunks)
    finally:
        spinner.stop()

    print(_c("Answer:", _BOLD, _GREEN))
    print(textwrap.fill(answer, width=80))
    print()
    logger.info(f"Answer delivered: {answer}.")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def launch() -> None:
    """Entry point — starts the interactive CLI loop."""
    _print_banner()

    while True:
        _print_menu()

        try:
            raw = input(_c("› ", _CYAN, _BOLD)).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not raw:
            continue

        # Exit
        if raw.lower() == "x":
            print("\nGoodbye!")
            break

        # Demo question by number
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(DEMO_QUESTIONS):
                query = DEMO_QUESTIONS[idx - 1]
                print(f"\nQuestion: {query}")
                _ask_and_answer(query)
            else:
                print(f"\nPlease enter a number between 1 and {len(DEMO_QUESTIONS)}.\n")
            continue

        # Custom question
        if raw.lower() == "a":
            try:
                query = input(_c("Your question: ", _BOLD)).strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not query:
                print("\nNo question entered.\n")
                continue

            print(f"\nQuestion: {query}")
            _ask_and_answer(query)
            continue

        print("\nInvalid choice. Enter 1–5, a, or x.\n")
