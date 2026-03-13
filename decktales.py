from functools import partial
from math import ceil

from aqt import Qt, mw
from aqt.operations import QueryOp
from aqt.qt import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from decktales.api import APICaller
from decktales.prompt import PromptGenerator
from decktales.utils import (
    MultiSelectDialog,
    PromptDialog,
    format_words,
    get_due_words,
    parse_sections,
    remove_furigana,
)

EDITOR_SETTING = """
    QTextEdit {
        font-family: "Hiragino Mincho ProN", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", "Noto Sans CJK JP", sans-serif;
        font-size: 18pt;
    }
"""


class DecktalesWindow(QWidget):
    """
    Main window for the Decktales Anki add‑on.

    Provides a settings panel (left) to select a deck, fields, model, and generation parameters.
    After clicking "Apply", it creates a tab for each batch of due cards, where each tab
    displays the vocabulary and a button to generate a story via an AI model.
    """

    def __init__(self):
        super().__init__()

        # Main horizontal layout: menu (left) + tab area (right)
        self.main_layout = QHBoxLayout()

        # Left panel – settings menu (fixed width)
        menu_container = QWidget()
        menu_container.setMaximumWidth(300)
        self.menu_layout = QFormLayout(menu_container)

        # Right area – tab widget for batches
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMovable(True)

        # Layout that holds the tabs (will be populated later)
        self.app_layout = QVBoxLayout()

        # Build the settings menu
        self._init_menu()

        # Assemble main layout
        self.main_layout.addWidget(menu_container)
        self.main_layout.addLayout(self.app_layout)

        self.setLayout(self.main_layout)

    def _init_menu(self):
        """
        Create and arrange all control widgets in the left settings panel.
        Includes deck selection, field selection, model, vocabulary level, and sliders.
        """

        # Title label
        title_label = QLabel("Settings")
        self.menu_layout.addRow(title_label)

        # ===== Deck selection =====
        self.menu_layout.addRow(QLabel("Deck"))
        self.deck_combobox = QComboBox()

        # Get all top‑level deck names (before any "::")
        all_decks = {d.name.split("::")[0] for d in mw.col.decks.all_names_and_ids()}
        for deck_name in sorted(all_decks):
            self.deck_combobox.addItem(deck_name)
        self.deck_combobox.setCurrentIndex(-1)  # nothing selected initially

        self.menu_layout.addRow(self.deck_combobox)

        # ===== Field selection (shows after deck is chosen) =====
        self.selected_field_names = []  # will hold the chosen note fields
        self.selected_fields_label = QLabel("Selected Fields: (none)")
        self.menu_layout.addRow(self.selected_fields_label)

        # Connect deck change to field selection dialog
        self.deck_combobox.currentTextChanged.connect(self._on_deck_selected)

        # ===== LLM model selection =====
        self.menu_layout.addRow(QLabel("LLM Model"))
        self.model_combobox = QComboBox()
        self.model_combobox.addItem("Gemini 3", "gemini-3-flash-preview")
        self.model_combobox.addItem("Gemini 3.1", "gemini-3.1-flash-lite-preview")
        self.model_combobox.addItem("Gemini 2", "gemini-2.5-flash")
        self.menu_layout.addRow(self.model_combobox)

        # ===== Vocabulary level =====
        self.menu_layout.addRow(QLabel("Level Vocabulary"))
        self.vocab_level_combobox = QComboBox()
        for i in range(1, 6):
            self.vocab_level_combobox.addItem(f"N{i}")
        self.menu_layout.addRow(self.vocab_level_combobox)

        # ===== Batch size slider =====
        self.batch_size_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.batch_size_slider.setRange(5, 40)
        self.batch_size_slider.setValue(20)
        self.batch_size_label = QLabel(f"Batch Size: {self.batch_size_slider.value()}")
        self.batch_size_slider.valueChanged.connect(
            lambda val: self.batch_size_label.setText(f"Batch Size: {val}")
        )
        self.menu_layout.addRow(self.batch_size_label)
        self.menu_layout.addRow(self.batch_size_slider)

        # ===== Selection percentage slider =====
        self.selection_percentage_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.selection_percentage_slider.setRange(1, 100)
        self.selection_percentage_slider.setValue(90)
        self.selection_percentage_label = QLabel(
            f"Selection %: {self.selection_percentage_slider.value() / 100}"
        )
        self.selection_percentage_slider.valueChanged.connect(
            lambda val: self.selection_percentage_label.setText(
                f"Selection %: {val / 100}"
            )
        )
        self.menu_layout.addRow(self.selection_percentage_label)
        self.menu_layout.addRow(self.selection_percentage_slider)

        # ===== Text scaling factor slider =====
        self.text_scaling_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.text_scaling_slider.setRange(1, 20)
        self.text_scaling_slider.setValue(10)
        self.text_scaling_label = QLabel(
            f"Text Scaling: {self.text_scaling_slider.value()}"
        )
        self.text_scaling_slider.valueChanged.connect(
            lambda val: self.text_scaling_label.setText(f"Text Scaling: {val}")
        )
        self.menu_layout.addRow(self.text_scaling_label)
        self.menu_layout.addRow(self.text_scaling_slider)

        # ===== Apply button =====
        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self._on_apply_clicked)
        self.menu_layout.addRow(apply_button)

    def _on_deck_selected(self, deck_name: str):
        """
        Called when the user selects a deck. Opens a multi‑selection dialog
        showing all fields (note keys) of the first card found in the deck hierarchy.
        Updates self.selected_field_names and the corresponding label.
        """
        if not deck_name:
            return

        # Search for any card in the deck (including subdecks)
        query = f'"deck:{deck_name}"'
        card_ids = mw.col.find_cards(query)
        if not card_ids:
            # Try including subdecks explicitly if the above didn't work
            card_ids = mw.col.find_cards(f'deck:"{deck_name}" OR deck:"{deck_name}::*"')
        if not card_ids:
            # No cards at all – show error or leave fields empty
            self.selected_field_names = []
            self.selected_fields_label.setText("Selected Fields: (no cards)")
            return

        # Take the first card's note to get its field names
        card = mw.col.get_card(card_ids[0])
        note = mw.col.get_note(card.nid)
        field_names = list(note.keys())  # all field names of this note type

        # Open multi‑selection dialog
        selected = MultiSelectDialog.get_items(
            field_names,
            title="Choose fields to process",
            parent=self,
        )

        if selected:
            self.selected_field_names = selected
        else:
            # Default to the first field if nothing selected
            self.selected_field_names = [field_names[0]]

        # Update the label
        self.selected_fields_label.setText(
            f"Selected Fields: {', '.join(self.selected_field_names)}"
        )

    def _on_apply_clicked(self):
        """
        Triggered by the Apply button. Gathers current settings and calls
        init_app() to rebuild the tab area with batches for the selected deck.
        """
        self.init_app(
            deck_name=self.deck_combobox.currentText(),
            field_names=self.selected_field_names,
            model=self.model_combobox.currentData(),
            vocab_level=self.vocab_level_combobox.currentText(),
            batch_size=self.batch_size_slider.value(),
            selection_ratio=self.selection_percentage_slider.value() / 100,
            text_scaling=self.text_scaling_slider.value(),
        )

    def init_app(
        self,
        deck_name: str,
        field_names: list[str],
        model: str,
        vocab_level: str,
        batch_size: int,
        selection_ratio: float,
        text_scaling: int,
    ):
        """
        (Re)build the tab area with one tab per batch of due cards from the chosen deck.

        For each batch, a tab is created showing the vocabulary words and a button to
        generate a story. The generation uses the selected AI model and settings.

        Args:
            deck_name: Name of the Anki deck (including subdecks automatically).
            field_names: List of note field names to extract from each card.
            model: Identifier of the AI model to use.
            vocab_level: String like "N4" for the prompt.
            batch_size: Number of cards per batch.
            selection_ratio: Fraction (0..1) of words to be used in the story (passed to prompt generator).
            text_scaling: Factor to adjust story length (passed to prompt generator).
        """
        # Remove old tabs (if any) – the old QTabWidget will be deleted later
        self.tabs.deleteLater()

        # Create a fresh tab widget
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMovable(True)
        self.app_layout.addWidget(self.tabs)

        # API caller instance (synchronous, but used via background threads)
        api = APICaller()

        # Retrieve all due words from the deck
        due_words = get_due_words(deck_name=deck_name, field_names=field_names)

        # Prompt generator (builds the text prompt for the AI)
        prompt_gen = PromptGenerator(
            vocab_level=vocab_level,
            story_theme="",
            scaling_factor=text_scaling,
            percentage_selection=selection_ratio,
        )

        # Split due words into batches and generate a prompt for each batch
        batch_words_list = []  # list of batches, each batch = list of (kanji, reading) tuples
        prompt_list = []  # list of corresponding prompts

        num_batches = ceil(len(due_words) / batch_size)
        for batch_num in range(num_batches):
            start = batch_num * batch_size
            end = (batch_num + 1) * batch_size
            batch = due_words[start:end]

            batch_words_list.append(batch)
            prompt_list.append(prompt_gen.generate(words=batch))

            # Create a new tab for this batch
            tab_widget = QWidget()
            tab_layout = QVBoxLayout()

            # Editor showing the vocabulary words of this batch
            words_editor = QTextEdit()
            words_editor.setStyleSheet(EDITOR_SETTING)  # assumed constant
            words_editor.setReadOnly(True)
            words_editor.setFixedHeight(200)
            words_editor.setHtml(format_words(batch))

            # Checkbox to toggle furigana display
            show_hiragana_checkbox = QCheckBox("Show Hiragana")

            # Button to edit the prompt manually
            edit_prompt_button = QPushButton(f"Edit Prompt {batch_num}")

            # Connect prompt edit button – modifies the prompt list in place
            edit_prompt_button.clicked.connect(
                partial(
                    self._on_edit_prompt_clicked,
                    batch_index=batch_num,
                    prompt_list=prompt_list,
                )
            )

            # Button to generate the story
            generate_story_button = QPushButton(f"Generate {batch_num}")

            # Editor that will display the generated story
            story_editor = QTextEdit()
            story_editor.setStyleSheet(EDITOR_SETTING)
            story_editor.setReadOnly(True)

            # Connect generate button – launches background API call
            generate_story_button.clicked.connect(
                partial(
                    self.call_and_generate_text,
                    batch_index=batch_num,
                    batch_words_list=batch_words_list,
                    prompt_list=prompt_list,
                    model=model,
                    show_hiragana_checkbox=show_hiragana_checkbox,
                    story_editor=story_editor,
                    api_client=api,
                )
            )

            # Assemble tab layout
            tab_layout.addWidget(QLabel(f"Batch {batch_num}"))
            tab_layout.addWidget(words_editor)
            tab_layout.addWidget(QLabel("Generated story:"))
            tab_layout.addWidget(show_hiragana_checkbox)
            tab_layout.addWidget(edit_prompt_button)
            tab_layout.addWidget(generate_story_button)
            tab_layout.addWidget(story_editor)

            tab_widget.setLayout(tab_layout)
            self.tabs.addTab(tab_widget, f"{batch_num}")

    def _on_edit_prompt_clicked(self, batch_index: int, prompt_list: list[str]):
        """
        Open a dialog to edit the prompt for a specific batch and update the list in place.
        """
        modified_prompt = PromptDialog.get_items(prompt=prompt_list[batch_index])
        if modified_prompt:
            prompt_list[batch_index] = modified_prompt

    def call_and_generate_text(
        self,
        batch_index: int,
        batch_words_list: list[list[tuple[str, str]]],
        prompt_list: list[str],
        model: str,
        show_hiragana_checkbox: QCheckBox,
        story_editor: QTextEdit,
        api_client: APICaller,
    ) -> None:
        """
        Generate a story for a specific batch of vocabulary.

        This method extracts the word batch and prompt corresponding to `batch_index`,
        then uses Anki's QueryOp to call the AI API in the background without blocking the UI.
        On success, `on_generation_done` updates the provided editor widget;
        on failure, `on_generation_error` displays the error.

        Args:
            batch_index: Index of the current batch (used to select from parallel lists).
            batch_words_list: List of batches, each batch being a list of (kanji, reading) tuples.
            prompt_list: List of prompt strings corresponding to each batch.
            model: AI model identifier to use (e.g., "gemini-2.0-flash").
            show_hiragana_checkbox: Checkbox controlling whether furigana should be displayed.
            editor_widget: QTextEdit where the generated story will be shown.
            api_client: Instance of APICaller used to make the API request.
        """
        if batch_index < 0 or batch_index >= len(batch_words_list):
            raise IndexError(
                f"batch_index {batch_index} out of range for batch_words_list"
            )

        current_batch = batch_words_list[batch_index]
        current_prompt = prompt_list[batch_index]
        kanjis = [kanji for kanji, reading in current_batch]

        op = QueryOp(
            parent=self,
            op=lambda col: api_client.call(kanjis, current_prompt, model),
            success=lambda text: self.on_generation_done(
                text, show_hiragana_checkbox, story_editor
            ),
        )
        op.failure(
            failure=lambda err: self.on_generation_error(
                err, show_hiragana_checkbox, story_editor
            )
        )

        op.with_progress().run_in_background()

    def on_generation_done(
        self,
        raw_response: str,
        show_hiragana_checkbox: QCheckBox,
        story_editor: QTextEdit,
    ) -> None:
        """
        Handle successful API response

        Args:
            raw_response: Full text returned by the API (should contain ##STORY## section).
            show_hiragana_checkbox: Checkbox controlling furigana visibility.
            story_editor: QTextEdit where the story will be set as HTML.
        """
        # Extract the story section from the structured API output
        parsed = parse_sections(raw_response)
        story_text = parsed.get("STORY", "")

        if not show_hiragana_checkbox.isChecked():
            story_text = remove_furigana(story_text)

        story_text = story_text.replace("\n\n", "<br><br>")

        story_editor.setHtml(story_text)

    def on_generation_error(
        self,
        error: Exception,
        show_hiragana_checkbox: QCheckBox,  # kept for signature consistency (unused)
        story_editor: QTextEdit,
    ) -> None:
        """
        Handle API error: display the error message in the editor.

        Args:
            error_message: The error string returned by the API or exception.
            show_hiragana_checkbox: Unused checkbox (kept for consistent callback signature).
            story_editor: QTextEdit where the error will be shown.
        """
        # Show the error directly in the editor (as plain text wrapped in <pre> or similar)
        story_editor.setHtml(f"<pre style='color: red;'>{error.message}</pre>")
