import re

from aqt import mw
from aqt.qt import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

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


###########################
## QT Dialog
###########################


class MultiSelectDialog(QDialog):
    """
    A dialog that displays a list of items and allows multiple selections.
    Returns a list of selected strings when accepted.
    """

    def __init__(self, items, title="Select Items", parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)  # Block interaction with parent window
        self.resize(300, 400)

        # Main layout
        layout = QVBoxLayout(self)

        # List widget with multi‑selection enabled
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        self.list_widget.addItems(items)
        layout.addWidget(self.list_widget)

        # OK / Cancel buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_selected_items(self):
        """Return the text of all selected items."""
        return [item.text() for item in self.list_widget.selectedItems()]

    @staticmethod
    def get_items(items, title="Select Items", parent=None):
        """
        Convenience static method: create, show, and return selected items.
        Returns a list of strings (empty if cancelled).
        """
        dialog = MultiSelectDialog(items, title, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_selected_items()
        return []


class PromptDialog(QDialog):
    def __init__(self, prompt: str):
        super().__init__()

        self.prompt = prompt

        self.setWindowTitle("Prompt")

        QBtn = (
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        layout = QVBoxLayout()

        self.message = QTextEdit()
        self.message.setStyleSheet(EDITOR_SETTING)
        self.message.setPlainText(self.prompt)

        layout.addWidget(self.message)
        layout.addWidget(self.buttonBox)
        self.setLayout(layout)

    def get_prompt(self) -> str:
        return self.message.toPlainText()

    @staticmethod
    def get_items(prompt: str) -> str:
        """
        Convenience static method: create, show, and return prompt.
        Returns a modify prompt strings (unchanged if cancelled).
        """
        dialog = PromptDialog(prompt=prompt)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_prompt()
        return prompt
