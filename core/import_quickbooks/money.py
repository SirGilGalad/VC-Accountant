"""Turn report amounts into integer cents. No floats."""

from __future__ import annotations


def parse_amount(raw: str | None) -> int:
    """Parentheses and a leading minus are negative. Commas are thousands separators."""
    text = (raw or "").strip().replace("$", "").replace(",", "").replace(" ", "")
    if text in {"", "-", ".", "()"}:
        return 0
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1].strip()
    if text.startswith("-"):
        negative = True
        text = text[1:]
    if text.startswith("+"):
        text = text[1:]
    if not text:
        return 0
    if "." in text:
        whole, frac = text.split(".", 1)
        frac = "".join(ch for ch in frac if ch.isdigit())
        frac = (frac + "00")[:2]
    else:
        whole, frac = text, "00"
    whole = "".join(ch for ch in whole if ch.isdigit()) or "0"
    cents = int(whole) * 100 + int(frac or "0")
    return -cents if negative else cents


def fold_sides(debit_raw: str | None, credit_raw: str | None) -> tuple[int, int] | None:
    """One column with a negative amount moves to the other side.

    Returns None when both sides still have an amount.
    """
    debit = parse_amount(debit_raw)
    credit = parse_amount(credit_raw)
    if debit < 0 and credit == 0:
        credit = -debit
        debit = 0
    elif credit < 0 and debit == 0:
        debit = -credit
        credit = 0
    if debit < 0 or credit < 0 or (debit == 0) == (credit == 0):
        if debit == 0 and credit == 0:
            return (0, 0)
        return None
    return debit, credit
