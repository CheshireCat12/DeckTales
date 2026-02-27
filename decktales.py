from functools import partial
from math import ceil

from aqt import Qt, mw
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
    QThread,
    QVBoxLayout,
    QWidget,
)

from decktales.api import APICaller, GeminiWorker
from decktales.utils import format_words, get_due_words, parse_sections, remove_furigana

EDITOR_SETTING = """
    QTextEdit {
        font-family: "Hiragino Mincho ProN", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", "Noto Sans CJK JP", sans-serif;
        font-size: 18pt;
    }
"""


class Prompt:
    def __init__(
        self,
        vocab_level: str,
        story_theme: str,
        scaling_factor: int,
        percentage_selection: float,
    ) -> None:
        self.vocab_level = vocab_level
        self.story_theme = story_theme
        self.scaling_factor = scaling_factor
        self.percentage_selection = percentage_selection

    def generate(self, words: list) -> str:

        percent_words = min(int(len(words) * self.percentage_selection), 1)

        prompt = f"""# SYSTEM PROMPT
You are an experienced Japanese teacher who believes in immersion through reading. You also write short, engaging stories for learners ({self.vocab_level} level). Your stories are grammatically simple, use furigana for all kanji, and avoid gender/occupational stereotypes.

# USER PROMPT
I am an {self.vocab_level} learner using Anki. Today I have these {len(words)} vocabulary cards.
**I do NOT expect you to use all of them.** Instead, please:

0. **Choose a theme for an engaging story** then use this theme when you write the story.
1. **Select about {percent_words} words** from the list that can naturally appear together in one short story (e.g., around a single theme or location).
2. **Write a {percent_words * self.scaling_factor} word story** using those selected words.
3. The story must be **easy and engaging to read**, with **{self.vocab_level}‑level grammar** and **short sentences**.
4. Use the writing style of graded books such as tadoku graded books, satory reader and genki japanese reader.
5. **Furigana format**: For every kanji, write the reading in parentheses **immediately after** the kanji.
✅ Example: 私(わたし)は 昨日(きのう) 友達(ともだち)と 公園(こうえん)へ 行(い)きました。
❌ Wrong: only adding readings for target words, or putting readings only once.

---

### Vocabulary List (select about {percent_words} from here)
{words[:]}
---

### Output Format – STRICT REQUIREMENTS

Your entire response must consist **exactly** of the three sections below, in this order, with **no additional text, explanations, greetings, or commentary**.

1. **`##SELECTED_WORDS##`**
- One word per line, **only** the kanji followed immediately by its reading in parentheses.
- Do **not** add numbers, bullet points, dashes, or descriptions.
- Example:
 ```
 景色(けしき)
 細い(ほそい)
 ```

2. **`##THEME##`**
- A single line describing the theme or setting of the story.
- Example: `池のほとりの小さな謎`

3. **`##STORY##`**
- The full story, with furigana for **all** kanji as specified in rule 5.
- The story must be written as plain text, with normal spacing and punctuation.
- Do **not** add extra line breaks inside the story unless they are part of the paragraph structure.

---

### Before writing the story, you will still:
- **Select the words** from the list ({percent_words} of them) – but you **do not** need to explain your choice. The selection is shown only in the `##SELECTED_WORDS##` section.
- **Write the story** under the `##STORY##` heading.

Now, generate your response following the **Output Format** exactly."""
        return prompt


class DecktalesWindow(QWidget):
    """
    This "window" is a QWidget. If it has no parent, it
    will appear as a free-floating window as we want.
    """

    def __init__(self):
        super().__init__()

        self.api = APICaller()

        self.main_layout = QHBoxLayout()

        menu_container = QWidget()
        menu_container.setMaximumWidth(300)
        self.menu_layout = QFormLayout(menu_container)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMovable(True)
        self.app_layout = QVBoxLayout()

        self.init_menu()

        self.main_layout.addWidget(menu_container)
        # self.main_layout.addLayout(self.menu_layout)
        self.main_layout.addLayout(self.app_layout)

        self.setLayout(self.main_layout)

    def init_menu(self):

        label = QLabel("Another Window")

        deck_combobox = QComboBox()
        decks = set([d.name.split("::")[0] for d in mw.col.decks.all_names_and_ids()])
        for deck in decks:
            deck_combobox.addItem(deck)

        model_combobox = QComboBox()
        model_combobox.addItem("Gemini 3", "gemini-3-flash-preview")
        model_combobox.addItem("Gemini 2", "gemini-2.5-flash")

        vocab_lvl_combobox = QComboBox()
        for i in range(1, 6):
            vocab_lvl_combobox.addItem(f"N{i}")

        size_corpus_slider = QSlider(Qt.Orientation.Horizontal, self)
        size_corpus_slider.setRange(5, 40)
        size_corpus_slider.setValue(20)
        size_corpus_label = QLabel(f"Size Corpus: {size_corpus_slider.value()}")
        size_corpus_slider.valueChanged.connect(
            lambda value: size_corpus_label.setText(f"Size Corpus: {value}")
        )

        percentage_corpus_slider = QSlider(Qt.Orientation.Horizontal, self)
        percentage_corpus_slider.setRange(1, 100)
        percentage_corpus_slider.setValue(90)
        percentage_corpus_label = QLabel(
            f"Percentage Corpus: {percentage_corpus_slider.value() / 100}"
        )
        percentage_corpus_slider.valueChanged.connect(
            lambda value: percentage_corpus_label.setText(
                f"Percentage Corpus: {percentage_corpus_slider.value() / 100}"
            )
        )

        scaling_factor_slider = QSlider(Qt.Orientation.Horizontal, self)
        scaling_factor_slider.setRange(1, 20)
        scaling_factor_slider.setValue(10)
        scaling_factor_label = QLabel(
            f"Text Scaling Factor: {scaling_factor_slider.value()}"
        )
        scaling_factor_slider.valueChanged.connect(
            lambda value: scaling_factor_label.setText(
                f"Text Scaling Factor: {scaling_factor_slider.value()}"
            )
        )

        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(
            lambda x: self.init_app(
                deck=deck_combobox.currentText(),
                model=model_combobox.currentData(),
                vocab_level=vocab_lvl_combobox.currentText(),
                batch_size=size_corpus_slider.value(),
                percentage_selection=percentage_corpus_slider.value(),
                text_scaling_factor=scaling_factor_slider.value(),
            )
        )

        self.menu_layout.addRow(label)
        self.menu_layout.addRow(QLabel("Deck"))
        self.menu_layout.addRow(deck_combobox)
        self.menu_layout.addRow(QLabel("LLM Model"))
        self.menu_layout.addRow(model_combobox)
        self.menu_layout.addRow(QLabel("Level Vocabulary"))
        self.menu_layout.addRow(vocab_lvl_combobox)
        self.menu_layout.addRow(size_corpus_label)
        self.menu_layout.addRow(size_corpus_slider)
        self.menu_layout.addRow(percentage_corpus_label)
        self.menu_layout.addRow(percentage_corpus_slider)
        self.menu_layout.addRow(scaling_factor_label)
        self.menu_layout.addRow(scaling_factor_slider)
        self.menu_layout.addRow(apply_button)

    def init_app(
        self,
        deck: str,
        model: str,
        vocab_level: str,
        batch_size: int,
        percentage_selection: float,
        text_scaling_factor: int,
    ):

        self.tabs.deleteLater()

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMovable(True)
        self.app_layout.addWidget(self.tabs)

        due_words = get_due_words(deck=deck)

        story_theme = ""

        for batch_num in range(ceil(len(due_words) / batch_size)):
            batch_words = due_words[
                batch_num * batch_size : (batch_num + 1) * batch_size
            ]
            new_prompt = Prompt(
                vocab_level=vocab_level,
                story_theme=story_theme,
                scaling_factor=text_scaling_factor,
                percentage_selection=percentage_selection,
            )
            prompt = new_prompt.generate(words=batch_words)

            formatted_words = format_words(batch_words)

            current_tab = QWidget()
            layout_tab = QVBoxLayout()

            editor = QTextEdit()
            editor.setStyleSheet(EDITOR_SETTING)
            editor.setReadOnly(True)
            editor.setFixedHeight(200)
            editor.setHtml(formatted_words)

            show_hiragana = QCheckBox("Show Hiragana")

            generate_button = QPushButton(f"Generate {batch_num}")

            editor_gen_text = QTextEdit()
            editor_gen_text.setStyleSheet(EDITOR_SETTING)
            editor_gen_text.setReadOnly(True)

            layout_tab.addWidget(QLabel(f"words {batch_num}"))
            layout_tab.addWidget(editor)
            layout_tab.addWidget(QLabel("Generated text:"))
            layout_tab.addWidget(show_hiragana)
            layout_tab.addWidget(generate_button)
            layout_tab.addWidget(editor_gen_text)

            generate_button.clicked.connect(
                partial(
                    self.call_and_generate_text,
                    batch_words[:],
                    prompt[:],
                    model,
                    show_hiragana,
                    editor_gen_text,
                )
            )

            current_tab.setLayout(layout_tab)
            self.tabs.addTab(current_tab, f"{batch_num}")

    def call_and_generate_text(
        self,
        batch_words: list[tuple[str, str]],
        prompt: str,
        model: str,
        show_hiragana: QCheckBox,
        editor_gen_text: QTextEdit,
    ):
        kanjis = [kanji for kanji, reading in batch_words]

        # Setup thread and worker
        self.thread = QThread()
        self.worker = GeminiWorker(self.api, kanjis, prompt, model)
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(
            lambda text: self.on_generation_done(text, show_hiragana, editor_gen_text)
        )
        self.worker.error.connect(
            lambda err: self.on_generation_error(err, show_hiragana, editor_gen_text)
        )
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        # Start the thread
        self.thread.start()

    def on_generation_done(self, text, show_hiragana, editor):
        """This runs in the main thread - safe to update UI"""
        parsed_text = parse_sections(text)
        story = parsed_text["STORY"]
        if not show_hiragana.isChecked():
            story = remove_furigana(story)

        story = story.replace("\n\n", "<br><br>")

        editor.setHtml(story)

    def on_generation_error(self, err, show_hiragana, editor):
        """This runs in the main thread - safe to update UI"""

        editor.setHtml(err)


#             batch_low_percent = int(len(batch_words) * 0.7) + 1
#             batch_up_percent = int(len(batch_words) * 0.8) + 1
#             prompt = f"""# SYSTEM PROMPT
# You are an experienced Japanese teacher who believes in immersion through reading. You also write short, engaging stories for learners ({vocab_level} level). Your stories are grammatically simple, use furigana for all kanji, and avoid gender/occupational stereotypes.
#
# # USER PROMPT
# I am an {vocab_level} learner using Anki. Today I have these {len(batch_words)} vocabulary cards.
# **I do NOT expect you to use all of them.** Instead, please:
#
# 0. **Choose a fairy tail theme for an engaging story** then use this theme when you write the story.
# 1. **Select {batch_low_percent}-{batch_up_percent} words** from the list that can naturally appear together in one short story (e.g., around a single theme or location).
# 2. **Write a {batch_low_percent * text_scaling_factor}-{batch_up_percent * text_scaling_factor} word story** using those selected words.
# 3. The story must be **easy and engaging to read**, with **{vocab_level}‑level grammar** and **short sentences**.
# 4. Use the writing style of graded books such as tadoku graded books, satory reader and genki japanese reader.
# 5. **Furigana format**: For every kanji, write the reading in parentheses **immediately after** the kanji.
# ✅ Example: 私(わたし)は 昨日(きのう) 友達(ともだち)と 公園(こうえん)へ 行(い)きました。
# ❌ Wrong: only adding readings for target words, or putting readings only once.
#
# ---
#
# ### Vocabulary List (select {batch_low_percent}-{batch_up_percent} from here)
# {batch_words[:]}
# ---
#
# ### Output Format – STRICT REQUIREMENTS
#
# Your entire response must consist **exactly** of the three sections below, in this order, with **no additional text, explanations, greetings, or commentary**.
#
# 1. **`##SELECTED_WORDS##`**
# - One word per line, **only** the kanji followed immediately by its reading in parentheses.
# - Do **not** add numbers, bullet points, dashes, or descriptions.
# - Example:
#  ```
#  景色(けしき)
#  細い(ほそい)
#  ```
#
# 2. **`##THEME##`**
# - A single line describing the theme or setting of the story.
# - Example: `池のほとりの小さな謎`
#
# 3. **`##STORY##`**
# - The full story, with furigana for **all** kanji as specified in rule 5.
# - The story must be written as plain text, with normal spacing and punctuation.
# - Do **not** add extra line breaks inside the story unless they are part of the paragraph structure.
#
# ---
#
# ### Before writing the story, you will still:
# - **Select the words** from the list ({batch_low_percent}-{batch_up_percent} of them) – but you **do not** need to explain your choice. The selection is shown only in the `##SELECTED_WORDS##` section.
# - **Write the story** under the `##STORY##` heading.
#
# Now, generate your response following the **Output Format** exactly."""
