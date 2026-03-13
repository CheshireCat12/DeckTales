import re

from aqt import mw

DEBUG = False


def remove_furigana(text: str) -> str:
    """Remove all furigana readings enclosed in parentheses, e.g., '酷い(ひどい)' → '酷い'."""
    return re.sub(r"\([^)]+\)", "", text)


def clean_pitch(word: str) -> str:
    """Remove the pitch accent symbols."""
    cleaned_word = re.sub(r"[ꜛꜜ]", "", word)

    return cleaned_word


def get_due_words(deck_name: str, field_names: list[str]) -> list[tuple[str, str]]:
    """
    Retrieve all due cards from a deck and return the processed content of specified fields.

    For each due card in the given deck, the corresponding note is fetched and the values
    of the fields listed in `field_names` are extracted, cleaned with `clean_pitch()`,
    and returned as a tuple. The result is a list of such tuples (one per due card).

    Args:
        deck_name: Name of the deck (including subdecks automatically via Anki's search syntax).
        field_names: List of field names (e.g., ["Front", "Back"]) whose content should be returned.

    Returns:
        A list of tuples, where each tuple contains the cleaned values of the requested fields
        for a single due card, in the same order as `field_names`.

    Example:
        >>> get_due_words("Japanese::Vocabulary", ["Expression", "Reading"])
        [("勉強", "べんきょう"), ("食べる", "たべる")]
    """
    # Search for all due cards in the deck (including subdecks)
    card_ids = mw.col.find_cards(f'"deck:{deck_name}" is:due')

    due_words = []
    for cid in card_ids:
        card = mw.col.get_card(cid)
        note = mw.col.get_note(card.nid)

        # Extract requested fields and clean them
        current_word = [clean_pitch(note[field]) for field in field_names]
        due_words.append(tuple(current_word))

    return due_words


def format_words(words: list[tuple[str, str]]) -> str:
    # <b>{kanji}</b> <span style='font-size: smaller;'>({reading})</span>
    return "".join(
        [f"{w[0]}<span style='font-size: 12pt;'>({w[1]})</span>, " for w in words]
    )[:-2]


def parse_sections(text: str) -> dict:
    """Parse your ##SECTION## delimited format."""

    sections = {
        "VAL": "",
        "SELECTED_WORDS": "",
        "THEME": "",
        "STORY": "",
        "SELECTED_WORDS_PARSED": [],
    }

    # Extract each section using regex
    for section in sections.keys():
        pattern = rf"##{section}##\s*(.*?)(?=##|$)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            sections[section] = match.group(1).strip()

    # Parse selected words into list of tuples
    words = []
    for line in sections["SELECTED_WORDS"].split("\n"):
        line = line.strip()
        if line:
            # Match pattern: 景色(けしき)
            word_match = re.match(r"^(.+?)\((.+?)\)$", line)
            if word_match:
                words.append((word_match.group(1), word_match.group(2)))

    sections["SELECTED_WORDS_PARSED"] = words

    return sections
