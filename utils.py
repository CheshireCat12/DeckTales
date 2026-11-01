"""Helpers for reading Anki cards and parsing AI responses, plus reusable Qt dialogs."""

from pathlib import Path

from aqt import mw
from aqt.qt import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# remove_furigana and parse_sections are imported by other add-on modules from here
from decktales.core import (  # noqa: F401
    clean_pitch,
    collect_due_words,
    parse_sections,
    remove_furigana,
)

# When True, APICaller returns a canned response instead of calling the real API
DEBUG = False

# Style for text editors that display Japanese: lists fonts with good CJK coverage.
EDITOR_STYLESHEET = """
    QTextEdit {
        font-family: "Hiragino Mincho ProN", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", "Noto Sans CJK JP", sans-serif;
        font-size: 18pt;
    }
"""

# Style for the whole window. Colors come from palette() so that it follows
# Anki's light or dark theme instead of fixing colors of its own.
APP_STYLESHEET = """
    QLabel#panelTitle {
        font-size: 18pt;
        font-weight: 600;
    }
    QLabel#settingTitle {
        font-weight: 600;
    }
    QLabel#settingValue {
        color: palette(link);
        font-weight: 600;
    }
    QLabel#settingHelp {
        color: palette(placeholder-text);
        font-size: 9pt;
    }
    QLabel#emptyState {
        color: palette(placeholder-text);
        font-size: 13pt;
        border: 1px dashed palette(mid);
        border-radius: 12px;
        padding: 24px;
    }
    QFrame#settingCard {
        background: palette(base);
        border: 1px solid palette(mid);
        border-radius: 10px;
    }
    QScrollArea {
        border: none;
        background: transparent;
    }
    QWidget#settingsCards {
        background: transparent;
    }
    QTextEdit, QListWidget {
        background: palette(base);
        border: 1px solid palette(mid);
        border-radius: 8px;
        padding: 6px;
    }
    QComboBox {
        background: palette(button);
        border: 1px solid palette(mid);
        border-radius: 8px;
        padding: 5px 10px;
    }
    QComboBox:hover {
        border-color: palette(highlight);
    }
    QComboBox::drop-down {
        background: transparent;
        border: none;
        width: 24px;
    }
    QPushButton {
        background: palette(button);
        border: 1px solid palette(mid);
        border-radius: 8px;
        padding: 7px 14px;
    }
    QPushButton:hover {
        border-color: palette(highlight);
    }
    QPushButton#toggleButton:checked {
        background: palette(highlight);
        border-color: palette(highlight);
        color: palette(highlighted-text);
    }
    QPushButton#primaryButton {
        background: palette(highlight);
        border: none;
        color: palette(highlighted-text);
        font-weight: 600;
        padding: 8px 16px;
    }
    QPushButton#primaryButton:disabled {
        background: palette(mid);
        color: palette(placeholder-text);
    }
    QSlider::groove:horizontal {
        background: palette(mid);
        border-radius: 2px;
        height: 4px;
    }
    QSlider::sub-page:horizontal {
        background: palette(highlight);
        border-radius: 2px;
    }
    QSlider::handle:horizontal {
        background: palette(highlight);
        border-radius: 8px;
        margin: -6px 0;
        width: 16px;
    }
    QScrollBar:vertical {
        background: transparent;
        width: 8px;
    }
    QScrollBar::handle:vertical {
        background: palette(mid);
        border-radius: 4px;
        min-height: 24px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: transparent;
    }
    QTabWidget::pane {
        background: palette(base);
        border: 1px solid palette(mid);
        border-radius: 10px;
        top: 10px;  /* gap between the tab bar and the tab's content */
    }
    QTabBar::tab {
        background: transparent;
        border-bottom: 2px solid transparent;
        padding: 8px 16px;
    }
    QTabBar::tab:selected {
        border-bottom-color: palette(highlight);
        color: palette(link);
        font-weight: 600;
    }
"""

# Added separately because it needs the add-on's location. The arrow is mid-grey
# so that one image can be read on both light and dark themes.
CHEVRON_PATH = (Path(__file__).parent / "assets" / "chevron-down.svg").as_posix()
APP_STYLESHEET += f"""
    QComboBox::down-arrow {{
        height: 12px;
        image: url("{CHEVRON_PATH}");
        width: 12px;
    }}
"""


def make_help_label(text: str) -> QLabel:
    """Return a small, word-wrapped label explaining what a control is for."""
    help_label = QLabel(text)
    help_label.setObjectName("settingHelp")
    help_label.setWordWrap(True)
    return help_label


def get_due_words(deck_name: str, field_names: list[str]) -> list[tuple[str, ...]]:
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
    return collect_due_words(mw.col, deck_name, field_names)


def format_word(word_fields: tuple[str, ...]) -> str:
    """
    Format one word as HTML, with its reading in smaller text if it has one.

    The first value is the word and the second, if present, is its reading.
    Any further values are not displayed.
    """
    word = word_fields[0]
    reading = word_fields[1] if len(word_fields) > 1 else ""
    if not reading:
        return word
    return f"{word}<span style='font-size: 12pt;'>({reading})</span>"


def format_words(words: list[tuple[str, ...]]) -> str:
    """Format words as a comma-separated HTML string."""
    return ", ".join(format_word(word_fields) for word_fields in words)


###########################
## QT Dialog
###########################


class MultiSelectDialog(QDialog):
    """
    A dialog that displays a list of items and allows multiple selections.
    Returns a list of selected strings when accepted.
    """

    def __init__(
        self, items, title="Select Items", parent: QWidget = None, help_text: str = ""
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)  # Block interaction with parent window
        self.resize(300, 400)

        # Main layout
        layout = QVBoxLayout(self)

        if help_text:
            layout.addWidget(make_help_label(help_text))

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
    def get_items(items, title="Select Items", parent=None, help_text=""):
        """
        Convenience static method: create, show, and return selected items.
        Returns a list of strings (empty if cancelled).
        """
        dialog = MultiSelectDialog(items, title, parent, help_text)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_selected_items()
        return []


class PromptDialog(QDialog):
    """A dialog that lets the user view and edit a prompt before it is sent to the AI."""

    def __init__(self, prompt: str):
        super().__init__()

        self.prompt = prompt

        self.setWindowTitle("Prompt")
        self.setStyleSheet(APP_STYLESHEET)
        self.resize(760, 600)

        standard_buttons = (
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        self.button_box = QDialogButtonBox(standard_buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()

        self.prompt_editor = QTextEdit()
        self.prompt_editor.setStyleSheet(EDITOR_STYLESHEET)
        self.prompt_editor.setPlainText(self.prompt)

        layout.addWidget(
            make_help_label(
                "These instructions are sent to the model for this batch. Keep the "
                "##STORY## section in the requested output, as the story is read from it."
            )
        )
        layout.addWidget(self.prompt_editor)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

    def get_prompt(self) -> str:
        """Return the current text of the editor."""
        return self.prompt_editor.toPlainText()

    @staticmethod
    def get_items(prompt: str) -> str:
        """
        Convenience static method: create, show, and return prompt.
        Returns the modified prompt string (unchanged if cancelled).
        """
        dialog = PromptDialog(prompt=prompt)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_prompt()
        return prompt
