"""Main DeckTales window: the settings panel and one tab per batch of due cards."""

from functools import partial
from html import escape
from math import ceil
from typing import Callable

from aqt import Qt, mw
from aqt.operations import QueryOp
from aqt.qt import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QSlider,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from decktales.api import APICaller
from decktales.prompt import PromptGenerator
from decktales.utils import (
    APP_STYLESHEET,
    EDITOR_STYLESHEET,
    MultiSelectDialog,
    PromptDialog,
    format_words,
    get_due_words,
    make_help_label,
    parse_sections,
    remove_furigana,
)

# Models offered in the selector: (display name, API model identifier, description)
MODEL_OPTIONS = [
    (
        "Gemini 3.8",
        "gemini-3.8-flash",
        "Google's most capable free Flash model, but it can take longer to respond.",
    ),
    (
        "Gemini 3.6",
        "gemini-3.6-flash",
        "An earlier Flash model, and a good alternative if Gemini 3.8 is slow.",
    ),
    (
        "Gemini 3.5 Lite",
        "gemini-3.5-flash-lite",
        "A lightweight model designed for quick results.",
    ),
    (
        "Gemini 2",
        "gemini-2.5-flash",
        "An older model, only available to API keys that have used it before.",
    ),
]

MODEL_HELP_PREFIX = "The Gemini model that writes the story."

NO_FIELDS_MESSAGE = (
    "Choose a deck and its fields, then click Apply to create your stories."
)
NO_DUE_CARDS_MESSAGE = "No cards are due in this deck right now."


class DecktalesWindow(QWidget):
    """
    Main window for the Decktales Anki add‑on.

    Provides a settings panel (left) to select a deck, fields, model, and generation parameters.
    After clicking "Apply", it creates a tab for each batch of due cards, where each tab
    displays the vocabulary and a button to generate a story via an AI model.
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("DeckTales")
        self.resize(1180, 800)
        self.setStyleSheet(APP_STYLESHEET)

        # Main horizontal layout: settings panel (left) + batch tabs (right)
        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(12, 16, 16, 16)
        self.main_layout.setSpacing(16)  # gap between the settings and the tab area

        # Left panel – fixed width, with its cards in a scroll area so that
        # the Apply button stays visible on small screens
        settings_panel = QWidget()
        settings_panel.setFixedWidth(352)
        settings_panel_layout = QVBoxLayout(settings_panel)
        settings_panel_layout.setContentsMargins(0, 0, 0, 0)
        settings_panel_layout.setSpacing(12)

        settings_cards = QWidget()
        settings_cards.setObjectName("settingsCards")
        self.settings_layout = QVBoxLayout(settings_cards)
        self.settings_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_layout.setSpacing(10)

        settings_scroll_area = QScrollArea()
        settings_scroll_area.setWidgetResizable(True)
        settings_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        settings_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        settings_scroll_area.setWidget(settings_cards)

        # The scrollbar gets its own column beside the cards: some styles float a scroll
        # area's built-in scrollbar on top of the content, which would hide part of the cards
        settings_scroll_bar = self._make_external_scroll_bar(settings_scroll_area)

        settings_scroll_row = QHBoxLayout()
        settings_scroll_row.setSpacing(6)
        settings_scroll_row.addWidget(settings_scroll_area, stretch=1)
        settings_scroll_row.addWidget(settings_scroll_bar)

        # Placeholder tab widget: init_app() replaces it and adds the new one to the layout
        self.batch_tabs = QTabWidget()
        self.batch_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.batch_tabs.setMovable(True)

        # Right area – a message until "Apply" has been clicked, then the batch tabs
        self.batch_tabs_layout = QVBoxLayout()
        self.empty_state_label = QLabel(NO_FIELDS_MESSAGE)
        self.empty_state_label.setObjectName("emptyState")
        self.empty_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state_label.setWordWrap(True)
        self.batch_tabs_layout.addWidget(self.empty_state_label)

        # Title label
        title_label = QLabel("Settings")
        title_label.setObjectName("panelTitle")
        settings_panel_layout.addWidget(title_label)
        settings_panel_layout.addLayout(settings_scroll_row, stretch=1)

        # Build the settings menu
        self._init_menu()

        # ===== Apply button (outside the scroll area) =====
        settings_panel_layout.addWidget(
            make_help_label(
                "Creates one tab per batch. Applying again replaces the tabs and "
                "their stories, so use it after changing any setting."
            )
        )
        # Stays disabled until there are fields to read from the deck's cards
        self.apply_button = QPushButton("Apply")
        self.apply_button.setObjectName("primaryButton")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._on_apply_clicked)
        settings_panel_layout.addWidget(self.apply_button)

        # Assemble main layout
        self.main_layout.addWidget(settings_panel)
        self.main_layout.addLayout(self.batch_tabs_layout, stretch=1)

        self.setLayout(self.main_layout)

    def _make_external_scroll_bar(self, scroll_area: QScrollArea) -> QScrollBar:
        """
        Return a separate vertical scrollbar kept in sync with a scroll area.

        The area's built-in scrollbar stays hidden but keeps working behind the scenes,
        tracking the content's size and the mouse wheel, so this one simply mirrors it.
        """
        built_in_bar = scroll_area.verticalScrollBar()

        external_bar = QScrollBar(Qt.Orientation.Vertical)
        external_bar.setObjectName("settingsScrollBar")
        external_bar.setFixedWidth(8)
        external_bar.hide()  # shown once the content is too tall to fit

        def on_range_changed(minimum: int, maximum: int) -> None:
            external_bar.setRange(minimum, maximum)
            # Qt updates the built-in bar's page step after its range, so read the height directly
            external_bar.setPageStep(scroll_area.viewport().height())
            external_bar.setVisible(maximum > minimum)

        built_in_bar.rangeChanged.connect(on_range_changed)
        built_in_bar.valueChanged.connect(external_bar.setValue)
        external_bar.valueChanged.connect(built_in_bar.setValue)
        return external_bar

    def _add_setting_card(
        self,
        title: str,
        help_text: str,
        *widgets: QWidget,
        value_label: QLabel | None = None,
    ) -> QLabel:
        """
        Add a card to the settings panel: title, control widgets, then an explanation.

        Args:
            title: Name of the setting.
            help_text: Explanation of what the setting is for, always visible.
            widgets: Widgets placed between the title and the explanation.
            value_label: Optional label showing the current value, beside the title.

        Returns:
            The label holding the explanation, in case it needs updating later.
        """
        card = QFrame()
        card.setObjectName("settingCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("settingTitle")

        header_layout = QHBoxLayout()
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        if value_label is not None:
            value_label.setObjectName("settingValue")
            header_layout.addWidget(value_label)
        card_layout.addLayout(header_layout)

        for widget in widgets:
            card_layout.addWidget(widget)
        help_label = make_help_label(help_text)
        card_layout.addWidget(help_label)

        self.settings_layout.addWidget(card)
        return help_label

    def _add_slider_setting(
        self,
        title: str,
        help_text: str,
        value_range: tuple[int, int],
        initial_value: int,
        format_value: Callable[[int], str],
    ) -> QSlider:
        """
        Add a card holding a slider whose current value is displayed beside the title.

        Args:
            title: Name of the setting.
            help_text: Explanation of what the setting is for.
            value_range: Lowest and highest slider values.
            initial_value: Slider value when the window opens.
            format_value: Converts a slider value into the text to display.

        Returns:
            The slider, so its value can be read when "Apply" is clicked.
        """
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(*value_range)
        slider.setValue(initial_value)

        value_label = QLabel(format_value(initial_value))
        slider.valueChanged.connect(
            lambda slider_value: value_label.setText(format_value(slider_value))
        )

        self._add_setting_card(title, help_text, slider, value_label=value_label)
        return slider

    def _init_menu(self):
        """
        Create and arrange all control widgets in the left settings panel.
        Includes deck selection, field selection, model, vocabulary level, and sliders.
        """

        # ===== Deck selection =====
        self.deck_combobox = QComboBox()
        self.deck_combobox.setPlaceholderText("Choose a deck")

        # Only list top‑level decks (the part before "::"); subdecks are searched with their parent
        top_level_deck_names = {
            deck.name.split("::")[0] for deck in mw.col.decks.all_names_and_ids()
        }
        for deck_name in sorted(top_level_deck_names):
            self.deck_combobox.addItem(deck_name)
        self.deck_combobox.setCurrentIndex(-1)  # nothing selected initially

        self._add_setting_card(
            "Deck",
            "The deck to study. Its due cards, including those in subdecks, supply "
            "the vocabulary. Choosing a deck opens the field picker.",
            self.deck_combobox,
        )

        # ===== Field selection (dialog opens once a deck is chosen) =====
        self.selected_field_names = []  # names of the note fields chosen by the user
        self.selected_fields_label = QLabel("None selected yet")
        self.selected_fields_label.setWordWrap(True)

        self._add_setting_card(
            "Fields",
            "The card fields sent to the model. The first one you click is the word. "
            "The second is an optional reading, which tells the model which word you "
            "mean when it has several readings. Any others, such as a meaning, are "
            "sent to the model but not displayed.",
            self.selected_fields_label,
        )

        # Connect deck change to field selection dialog
        self.deck_combobox.currentTextChanged.connect(self._on_deck_selected)

        # ===== LLM model selection =====
        # Each item stores a display name and, as item data, the API model identifier
        self.model_combobox = QComboBox()
        for model_name, model_id, model_description in MODEL_OPTIONS:
            self.model_combobox.addItem(model_name, model_id)
            self.model_combobox.setItemData(
                self.model_combobox.count() - 1,
                model_description,
                Qt.ItemDataRole.ToolTipRole,
            )

        model_help_label = self._add_setting_card(
            "LLM Model",
            f"{MODEL_HELP_PREFIX} {MODEL_OPTIONS[0][2]}",
            self.model_combobox,
        )

        # The explanation describes whichever model is currently selected
        self.model_combobox.currentIndexChanged.connect(
            lambda model_index: model_help_label.setText(
                f"{MODEL_HELP_PREFIX} {MODEL_OPTIONS[model_index][2]}"
            )
        )

        # ===== Vocabulary level (JLPT N1 to N5) =====
        self.vocab_level_combobox = QComboBox()
        for jlpt_level in range(1, 6):
            self.vocab_level_combobox.addItem(f"N{jlpt_level}")

        self._add_setting_card(
            "Level Vocabulary",
            "Your JLPT level, which sets how difficult the story's grammar should be, "
            "from N5 (easiest) to N1 (hardest).",
            self.vocab_level_combobox,
        )

        # ===== Sliders =====
        self.batch_size_slider = self._add_slider_setting(
            "Batch Size",
            "How many due cards go into each story. Each batch gets its own tab, so "
            "50 due cards at a size of 20 make 3 tabs.",
            value_range=(5, 40),
            initial_value=20,
            format_value=lambda slider_value: f"{slider_value} cards",
        )

        # The slider works in whole percents; the value is divided by 100 when applied
        self.selection_percentage_slider = self._add_slider_setting(
            "Word Selection",
            "How many of the batch's words the model should use. At 90%, a batch of "
            "20 cards asks for about 18, leaving out words that don't fit the story.",
            value_range=(1, 100),
            initial_value=90,
            format_value=lambda slider_value: f"{slider_value}%",
        )

        self.text_scaling_slider = self._add_slider_setting(
            "Story Length",
            "The target length is the number of cards in the batch times this value: "
            "20 cards at 10 words per card ask for a 200-word story.",
            value_range=(1, 20),
            initial_value=10,
            format_value=lambda slider_value: f"{slider_value} words per card",
        )

        self.settings_layout.addStretch()

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
            # No cards at all – clear the selection and say so in the label
            self.selected_field_names = []
            self.selected_fields_label.setText("This deck has no cards")
            self.apply_button.setEnabled(False)
            return

        # The first card's note supplies the field names, so this assumes
        # that the whole deck uses a single note type
        card = mw.col.get_card(card_ids[0])
        note = mw.col.get_note(card.nid)
        field_names = list(note.keys())

        # Open multi‑selection dialog
        chosen_fields = MultiSelectDialog.get_items(
            field_names,
            title="Choose fields to process",
            parent=self,
            help_text=(
                "Click the word field first, then its reading if you have one. "
                "Fields are used in the order you click them."
            ),
        )

        if chosen_fields:
            self.selected_field_names = chosen_fields
        else:
            # Default to the first field if nothing was selected or the dialog was cancelled
            self.selected_field_names = [field_names[0]]

        # Update the label
        self.selected_fields_label.setText(", ".join(self.selected_field_names))
        self.apply_button.setEnabled(True)

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
            story_length_factor=self.text_scaling_slider.value(),
        )

    def init_app(
        self,
        deck_name: str,
        field_names: list[str],
        model: str,
        vocab_level: str,
        batch_size: int,
        selection_ratio: float,
        story_length_factor: int,
    ):
        """
        (Re)build the tab area with one tab per batch of due cards from the chosen deck.

        For each batch, a tab is created showing the vocabulary words and a button to
        generate a story. The generation uses the selected AI model and settings.

        Args:
            deck_name: Name of the Anki deck (including subdecks automatically).
            field_names: Note fields to extract from each card: the word, then optionally
                its reading. All of them are sent to the AI, but only those two are displayed.
            model: Identifier of the AI model to use.
            vocab_level: String like "N4" for the prompt.
            batch_size: Number of cards per batch.
            selection_ratio: Fraction (0..1) of words to be used in the story (passed to prompt generator).
            story_length_factor: Requested story length in words per card (passed to prompt generator).
        """
        # Remove old tabs (if any) – the old QTabWidget will be deleted later
        self.batch_tabs.deleteLater()

        # Create a fresh tab widget
        self.batch_tabs = QTabWidget()
        self.batch_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.batch_tabs.setMovable(True)
        self.batch_tabs_layout.addWidget(self.batch_tabs)

        # API caller instance (synchronous, but used via background threads)
        api_client = APICaller()

        # Retrieve all due words from the deck
        due_words = get_due_words(deck_name=deck_name, field_names=field_names)

        # Show either the tabs or, when nothing is due, a message saying so
        self.batch_tabs.setVisible(bool(due_words))
        self.empty_state_label.setVisible(not due_words)
        self.empty_state_label.setText(NO_DUE_CARDS_MESSAGE)

        # Prompt generator (builds the text prompt for the AI)
        prompt_generator = PromptGenerator(
            vocab_level=vocab_level,
            story_theme="",
            story_length_factor=story_length_factor,
            selection_ratio=selection_ratio,
        )

        # Prompt to send for each batch, shared by every tab's callbacks.
        # Filled as the loop runs, and updated in place when a prompt is edited.
        batch_prompts = []

        # Split due words into batches and build one tab for each
        batch_count = ceil(len(due_words) / batch_size)
        for batch_index in range(batch_count):
            batch_start = batch_index * batch_size
            batch_end = (batch_index + 1) * batch_size
            batch_words = due_words[batch_start:batch_end]

            batch_prompts.append(prompt_generator.generate(words=batch_words))

            # Create a new tab for this batch
            tab_widget = QWidget()
            tab_layout = QVBoxLayout()
            tab_layout.setContentsMargins(14, 14, 14, 14)
            tab_layout.setSpacing(8)

            # Editor showing the vocabulary words of this batch
            words_title_label = QLabel(f"Vocabulary ({len(batch_words)} cards)")
            words_title_label.setObjectName("settingTitle")

            words_editor = QTextEdit()
            words_editor.setStyleSheet(EDITOR_STYLESHEET)
            words_editor.setReadOnly(True)
            words_editor.setFixedHeight(160)
            words_editor.setHtml(format_words(batch_words))

            # Toggle button showing or hiding the furigana of the displayed story
            show_furigana_button = QPushButton("Show Hiragana")
            show_furigana_button.setObjectName("toggleButton")
            show_furigana_button.setCheckable(True)
            show_furigana_button.setToolTip(
                "Show or hide the reading after each kanji in the story."
            )

            # Button to edit the prompt manually
            edit_prompt_button = QPushButton("Edit Prompt")
            edit_prompt_button.setToolTip(
                "Change the instructions sent to the model for this batch."
            )

            # Connect prompt edit button – modifies batch_prompts in place.
            # partial() binds this iteration's values; a plain lambda would see the last batch.
            edit_prompt_button.clicked.connect(
                partial(
                    self._on_edit_prompt_clicked,
                    batch_index=batch_index,
                    batch_prompts=batch_prompts,
                )
            )

            # Button to generate the story
            generate_story_button = QPushButton("Generate Story")
            generate_story_button.setObjectName("primaryButton")
            generate_story_button.setToolTip(
                "Ask the model to write a story from this batch."
            )

            # Row holding the story controls
            story_controls_layout = QHBoxLayout()
            story_controls_layout.addWidget(show_furigana_button)
            story_controls_layout.addStretch()
            story_controls_layout.addWidget(edit_prompt_button)
            story_controls_layout.addWidget(generate_story_button)

            # Editor that will display the generated story
            story_title_label = QLabel("Story")
            story_title_label.setObjectName("settingTitle")

            story_editor = QTextEdit()
            story_editor.setStyleSheet(EDITOR_STYLESHEET)
            story_editor.setReadOnly(True)
            story_editor.setPlaceholderText("Your story will appear here.")

            # The toggle's new state is passed as the last argument, show_furigana
            show_furigana_button.toggled.connect(
                partial(self._display_story, story_editor)
            )

            # Connect generate button – launches background API call
            generate_story_button.clicked.connect(
                partial(
                    self.call_and_generate_text,
                    batch_index=batch_index,
                    batch_prompts=batch_prompts,
                    model=model,
                    show_furigana_button=show_furigana_button,
                    story_editor=story_editor,
                    api_client=api_client,
                )
            )

            # Assemble tab layout
            tab_layout.addWidget(words_title_label)
            tab_layout.addWidget(words_editor)
            tab_layout.addLayout(story_controls_layout)
            tab_layout.addWidget(story_title_label)
            tab_layout.addWidget(story_editor, stretch=1)

            tab_widget.setLayout(tab_layout)
            self.batch_tabs.addTab(tab_widget, f"Batch {batch_index + 1}")

    def _on_edit_prompt_clicked(self, batch_index: int, batch_prompts: list[str]):
        """
        Open a dialog to edit the prompt for a specific batch and update the list in place.
        """
        modified_prompt = PromptDialog.get_items(prompt=batch_prompts[batch_index])
        if modified_prompt:
            batch_prompts[batch_index] = modified_prompt

    def call_and_generate_text(
        self,
        batch_index: int,
        batch_prompts: list[str],
        model: str,
        show_furigana_button: QPushButton,
        story_editor: QTextEdit,
        api_client: APICaller,
    ) -> None:
        """
        Generate a story for a specific batch of vocabulary.

        This method extracts the prompt corresponding to `batch_index`,
        then uses Anki's QueryOp to call the AI API in the background without blocking the UI.
        On success, `on_generation_done` updates the provided editor widget;
        on failure, `on_generation_error` displays the error.

        Args:
            batch_index: Index of the current batch in `batch_prompts`.
            batch_prompts: List of prompt strings corresponding to each batch.
            model: AI model identifier to use (e.g., "gemini-2.0-flash").
            show_furigana_button: Toggle button controlling whether furigana should be displayed.
            story_editor: QTextEdit where the generated story will be shown.
            api_client: Instance of APICaller used to make the API request.
        """
        if batch_index < 0 or batch_index >= len(batch_prompts):
            raise IndexError(
                f"batch_index {batch_index} out of range for batch_prompts"
            )

        batch_prompt = batch_prompts[batch_index]

        # `op` runs on a background thread; `success` and `failure` run back on the UI thread
        story_query_op = QueryOp(
            parent=self,
            op=lambda col: api_client.call(batch_prompt, model),
            success=lambda text: self.on_generation_done(
                text, show_furigana_button, story_editor
            ),
        )
        story_query_op.failure(
            failure=lambda err: self.on_generation_error(
                err, show_furigana_button, story_editor
            )
        )

        story_query_op.with_progress().run_in_background()

    def on_generation_done(
        self,
        raw_response: str,
        show_furigana_button: QPushButton,
        story_editor: QTextEdit,
    ) -> None:
        """
        Handle successful API response

        Args:
            raw_response: Full text returned by the API (should contain ##STORY## section).
            show_furigana_button: Toggle button controlling furigana visibility.
            story_editor: QTextEdit where the story will be set as HTML.
        """
        # Extract the story section from the structured API output
        sections = parse_sections(raw_response)

        # Keep the full story on the editor so the toggle can redisplay it without a new API call
        story_editor.setProperty("story_text", sections.get("STORY", ""))
        self._display_story(story_editor, show_furigana_button.isChecked())

    def _display_story(self, story_editor: QTextEdit, show_furigana: bool) -> None:
        """
        Display the story stored on the editor, with or without its furigana.

        Does nothing if the editor holds no story, so that an error message stays visible.

        Args:
            story_editor: QTextEdit where the story will be set as HTML.
            show_furigana: Whether to keep the reading after each kanji.
        """
        story_text = story_editor.property("story_text")
        if not story_text:
            return

        if not show_furigana:
            story_text = remove_furigana(story_text)

        # The editor renders HTML, where plain newlines would not create paragraph breaks
        story_text = story_text.replace("\n\n", "<br><br>")

        story_editor.setHtml(story_text)

    def on_generation_error(
        self,
        error: Exception,
        show_furigana_button: QPushButton,  # kept for signature consistency (unused)
        story_editor: QTextEdit,
    ) -> None:
        """
        Handle API error: display the error message in the editor.

        Args:
            error: The exception raised during the API call.
            show_furigana_button: Unused toggle button (kept for consistent callback signature).
            story_editor: QTextEdit where the error will be shown.
        """
        # Forget any earlier story, so that the toggle can't replace the error with it
        story_editor.setProperty("story_text", "")

        # Show the error directly in the editor, in red. str() works for every exception
        # (not all have .message), and escape() stops the text being read as HTML.
        story_editor.setHtml(f"<pre style='color: red;'>{escape(str(error))}</pre>")
