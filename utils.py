import re

from aqt import mw


def remove_furigana(text: str) -> str:
    """Remove all furigana readings enclosed in parentheses, e.g., '酷い(ひどい)' → '酷い'."""
    return re.sub(r"\([^)]+\)", "", text)


def clean_pitch(word: str) -> str:
    cleaned_word = re.sub(r"[ꜛꜜ]", "", word)

    return cleaned_word


def get_due_words(deck: str) -> list[tuple[str, str]]:
    ids = mw.col.find_cards(f"deck:{deck} is:due")

    due_words = []
    for id in ids:
        card = mw.col.get_card(id)
        note = mw.col.get_note(card.nid)

        current_word = []
        for key, value in note.items():
            if key in ["Japanese", "Reading"]:  # , "Meaning"]:
                current_word.append(clean_pitch(value))
        due_words.append(tuple(current_word))
    return due_words


def format_words(words: list[tuple[str, str]]) -> str:
    # <b>{kanji}</b> <span style='font-size: smaller;'>({reading})</span>
    return "".join(
        [f"{w[0]}<span style='font-size: 12pt;'>({w[1]})</span>, " for w in words]
    )[:-2]
