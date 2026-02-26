from functools import partial
from math import ceil

from aqt.qt import (
    QCheckBox,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QThread,
    QVBoxLayout,
    QWidget,
)

from decktales.api import APICaller, GeminiWorker
from decktales.utils import format_words, get_due_words, parse_sections, remove_furigana


class DecktalesWindow(QWidget):
    """
    This "window" is a QWidget. If it has no parent, it
    will appear as a free-floating window as we want.
    """

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.label = QLabel("Another Window")
        layout.addWidget(self.label)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMovable(True)

        deck = "Takoboto"
        due_words = get_due_words(deck=deck)
        vocab_level = "N4"

        batch_size = 30
        self.api = APICaller()

        for batch_num in range(ceil(len(due_words) / batch_size)):
            current_tab = QWidget()
            layout_tab = QVBoxLayout()
            batch_words = due_words[
                batch_num * batch_size : (batch_num + 1) * batch_size
            ]

            formatted_words = format_words(batch_words)
            editor = QTextEdit()
            editor.setStyleSheet("""
                QTextEdit {
                    font-family: "Hiragino Mincho ProN", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", "Noto Sans CJK JP", sans-serif;
                    font-size: 18pt;
                }
            """)
            editor.setReadOnly(True)
            editor.setFixedHeight(200)
            editor.setHtml(formatted_words)

            show_hiragana = QCheckBox("Show Hiragana")

            generate_button = QPushButton(f"Generate {batch_num}")

            layout_tab.addWidget(QLabel(f"words {batch_num}"))
            layout_tab.addWidget(editor)
            layout_tab.addWidget(QLabel("Generated text:"))
            layout_tab.addWidget(show_hiragana)
            layout_tab.addWidget(generate_button)

            editor_gen_text = QTextEdit()
            editor_gen_text.setStyleSheet("""
                QTextEdit {
                    font-family: "Hiragino Mincho ProN", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", "Noto Sans CJK JP", sans-serif;
                    font-size: 18pt;
                }
            """)
            editor_gen_text.setReadOnly(True)

            layout_tab.addWidget(editor_gen_text)

            batch_low_percent = int(len(batch_words) * 0.7) + 1
            batch_up_percent = int(len(batch_words) * 0.8) + 1
            text_scaling_factor = 14
            prompt = f"""# SYSTEM PROMPT
You are an experienced Japanese teacher who believes in immersion through reading. You also write short, engaging stories for learners ({vocab_level} level). Your stories are grammatically simple, use furigana for all kanji, and avoid gender/occupational stereotypes.

# USER PROMPT
I am an {vocab_level} learner using Anki. Today I have these {len(batch_words)} vocabulary cards.
**I do NOT expect you to use all of them.** Instead, please:

0. **Choose a fairy tail theme for an engaging story** then use this theme when you write the story.
1. **Select {batch_low_percent}-{batch_up_percent} words** from the list that can naturally appear together in one short story (e.g., around a single theme or location).
2. **Write a {batch_low_percent * text_scaling_factor}-{batch_up_percent * text_scaling_factor} word story** using those selected words.
3. The story must be **easy and engaging to read**, with **{vocab_level}‑level grammar** and **short sentences**.
4. Use the writing style of graded books such as tadoku graded books, satory reader and genki japanese reader.
5. **Furigana format**: For every kanji, write the reading in parentheses **immediately after** the kanji.
✅ Example: 私(わたし)は 昨日(きのう) 友達(ともだち)と 公園(こうえん)へ 行(い)きました。
❌ Wrong: only adding readings for target words, or putting readings only once.

---

### Vocabulary List (select {batch_low_percent}-{batch_up_percent} from here)
{batch_words[:]}
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
- **Select the words** from the list ({batch_low_percent}-{batch_up_percent} of them) – but you **do not** need to explain your choice. The selection is shown only in the `##SELECTED_WORDS##` section.
- **Write the story** under the `##STORY##` heading.

Now, generate your response following the **Output Format** exactly."""

            model = "gemini-3-flash-preview"
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

        layout.addWidget(self.tabs)

        self.setLayout(layout)

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
        # generated_text = self.api.call(
        #     [kanji for kanji, reading in batch_words], prompt=prompt
        # )
        # parsed_text = self._parse_sections(generated_text)
        # story = parsed_text["STORY"]
        #
        # if not show_hiragana.isChecked():
        #     story = remove_furigana(story)
        #
        # editor_gen_text.setHtml(story)
        # editor_gen_text.setHtml(generated_text)

    def on_generation_done(self, text, show_hiragana, editor):
        """This runs in the main thread - safe to update UI"""
        parsed_text = parse_sections(text)
        story = parsed_text["STORY"]
        if not show_hiragana.isChecked():
            story = remove_furigana(story)

        story = story.replace("\n\n", "<br><br>")

        editor.setHtml(story)
