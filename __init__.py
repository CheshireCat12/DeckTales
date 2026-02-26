import os
import re
import sys
from functools import partial
from math import ceil
from time import sleep

from aqt import mw

# import all of the Qt GUI library
from aqt.qt import (
    QAction,
    QCheckBox,
    QLabel,
    QObject,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QThread,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

# import the "show info" tool from utils.py
from aqt.utils import qconnect

# Add the 'vendor' folder to Python's search path
addon_dir = os.path.dirname(__file__)
vendor_dir = os.path.join(addon_dir, "vendor")
if vendor_dir not in sys.path:
    sys.path.insert(0, vendor_dir)

# If google was already imported, remove it from cache
if "google" in sys.modules:
    del sys.modules["google"]

from dotenv import load_dotenv
from google import genai
from google.genai import types


class GeminiWorker(QObject):
    finished = pyqtSignal(str)  # Signal with the generated story
    error = pyqtSignal(str)  # Signal for errors

    def __init__(self, api, batch_words, prompt):
        super().__init__()
        self.api = api
        self.batch_words = batch_words
        self.prompt = prompt

    def run(self):
        """This runs in the background thread"""
        try:
            # Your existing API call
            generated_text = self.api.call(self.batch_words, self.prompt)
            self.finished.emit(generated_text)
        except Exception as e:
            self.error.emit(str(e))


class APICaller:
    def __init__(self):
        self.cach_data = {}
        self.counter = 0

    def call(self, words: list[str], prompt: str) -> str:
        words_hash = hash(tuple(words))
        print(words_hash)

        if words_hash not in self.cach_data:
            print("API call")
            # print(prompt)
            # API call

            load_dotenv()

            # The client gets the API key from the environment variable `GEMINI_API_KEY`.
            client = genai.Client()

            model = "gemini-3-flash-preview"
            # model = "gemini-2.5-flash"
            # model = "gemini-2.5-flash-preview-09-2025"

            generation_config = {
                "temperature": 0.8,  # Recommended default for Gemini 3
                "top_p": 0.95,
            }

            model_temperature = 1.1

            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=model_temperature),
            )

            print(response)

            self.cach_data[words_hash] = f"""##VAL## {self.counter} """ + str(
                response.text
            )

            # output = """##SELECTED_WORDS##
            # 選ぶ(えらぶ)
            # 景色(けしき)
            # 年寄り(としより)
            # 決める(きめる)
            # 迷う(まよう)
            # 秘密(ひみつ)
            # 残念(ざんねん)
            # 糸(いと)
            # やり方(やりかた)
            # 人気(にんき)
            # 比べ(くらべ)
            # 伝える(つたえる)
            # 性格(せいかく)
            # 汚れる(よごれる)
            # 壊れる(こわれる)
            # 苛める(いじめる)
            # 悪戯(いたずら)
            # 細い(ほそい)
            # 探す(さがす)
            # 酷い(ひどい)
            # 狭い(せまい)
            # 西(にし)
            # 段々(だんだん)
            # 貸す(かす)
            #
            # ##THEME##
            # 人気の橋を壊す犯人探し
            #
            # ##STORY##
            # ユキとケンタは酷い(ひどい)話(はなし)を聞(き)きました。公園(こうえん)の西(にし)にある人気(にんき)の小(ちい)さな橋(はし)が、段々(だんだん)と壊れる(こわれる)のです。誰(だれ)かが橋(はし)を苛める(いじめる)ような悪戯(いたずら)をしているのかもしれません。二人(ふたり)は探す(さがす)ことを決める(きめる)ために、現場(げんば)へ行(い)きました。
            #
            # 橋(はし)のあたりは景色(けしき)が良(よ)く、細い(ほそい)道(みち)がある狭い(せまい)場所(ばしょ)でした。
            #
            # 年寄り(としより)の女性(じょせい)がそこで釣(つ)りをしていました。ユキは彼女(かのじょ)に尋(たず)ねました。「何(なに)か変(へん)なことを見(み)ましたか。」彼女(かのじょ)の性格(せいかく)は優し(やさし)そうでしたが、質問(しつもん)に答(こた)えるのを迷う(まよう)様子(ようす)を見(み)せました。
            #
            # 「私(わたし)には秘密(ひみつ)があります」と彼女(かのじょ)は小(ちい)さな声(こえ)で伝え(つたえる)ました。ケンタは足元(あしもと)を見(み)ました。橋(はし)の柱(はしら)に、汚れる(よごれる)た細い(ほそい)糸(いと)が巻(ま)き付(つ)いています。糸(いと)が強(つよ)い力(ちから)で柱(はしら)を引(ひ)っ張(ぱ)っていました。
            #
            # 「おばあさん、これです！糸(いと)のやり方(やりかた)が変(へん)ですよ」とケンタは言(い)いました。
            #
            # 年寄り(としより)は顔(かお)を赤(あか)くしました。「ごめんなさい。孫(まご)が貸す(かす)と言(い)った道具(どうぐ)で、どれが一番(いちばん)魚(さかな)を釣(つ)るか比べ(くらべ)ていたのです。この場所(ばしょ)しか選ぶ(えらぶ)ことができませんでした。」
            #
            # ユキはそれが酷い(ひどい)悪戯(いたずら)ではなかったことにホッとしました。橋(はし)が壊れる(こわれる)のは残念(ざんねん)ですが、原因(げんいん)はただの競争(きょうそう)でした。"""
            # self.cach_data[words_hash] = (
            #     f"""##VAL##
            # {self.counter}
            # """
            #     + output
            # )
            self.counter += 1

        return self.cach_data[words_hash]


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


# We're going to add a menu item below. First we want to create a function to
# be called when the menu item is activated.
class AnotherWindow(QWidget):
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

            generate_button.clicked.connect(
                partial(
                    self.call_and_generate_text,
                    batch_words[:],
                    prompt[:],
                    show_hiragana,
                    editor_gen_text,
                )
            )

            current_tab.setLayout(layout_tab)
            self.tabs.addTab(current_tab, f"{batch_num}")

        layout.addWidget(self.tabs)

        self.setLayout(layout)

    def _parse_sections(self, text):
        """Parse your ##SECTION## delimited format."""

        sections = {"VAL": "", "SELECTED_WORDS": "", "THEME": "", "STORY": ""}

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

    def call_and_generate_text(
        self,
        batch_words: list[tuple[str, str]],
        prompt: str,
        show_hiragana: QCheckBox,
        editor_gen_text: QTextEdit,
    ):
        kanjis = [kanji for kanji, reading in batch_words]
        # Setup thread and worker
        self.thread = QThread()
        self.worker = GeminiWorker(self.api, kanjis, prompt)
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
        parsed_text = self._parse_sections(text)
        story = parsed_text["STORY"]
        if not show_hiragana.isChecked():
            story = remove_furigana(story)

        story = story.replace("\n\n", "<br><br>")

        editor.setHtml(story)


def testFunction() -> None:
    mw.w = AnotherWindow()
    mw.w.show()


# create a new menu item, "test"
action = QAction("window", mw)
# set it to call testFunction when it's clicked
qconnect(action.triggered, testFunction)
# and add it to the tools menu
mw.form.menuTools.addAction(action)

#             generated_text = """ユキとケンタは酷い(ひどい)話(はなし)を聞(き)きました。公園(こうえん)の西(にし)にある人気(にんき)の小(ちい)さな橋(はし)が、段々(だんだん)と壊れる(こわれる)のです。誰(だれ)かが橋(はし)を苛める(いじめる)ような悪戯(いたずら)をしているのかもしれません。二人(ふたり)は探す(さがす)ことを決める(きめる)ために、現場(げんば)へ行(い)きました。
#
# 橋(はし)のあたりは景色(けしき)が良(よ)く、細い(ほそい)道(みち)がある狭い(せまい)場所(ばしょ)でした。
#
# 年寄り(としより)の女性(じょせい)がそこで釣(つ)りをしていました。ユキは彼女(かのじょ)に尋(たず)ねました。「何(なに)か変(へん)なことを見(み)ましたか。」彼女(かのじょ)の性格(せいかく)は優し(やさし)そうでしたが、質問(しつもん)に答(こた)えるのを迷う(まよう)様子(ようす)を見(み)せました。
#
# 「私(わたし)には秘密(ひみつ)があります」と彼女(かのじょ)は小(ちい)さな声(こえ)で伝え(つたえる)ました。ケンタは足元(あしもと)を見(み)ました。橋(はし)の柱(はしら)に、汚れる(よごれる)た細い(ほそい)糸(いと)が巻(ま)き付(つ)いています。糸(いと)が強(つよ)い力(ちから)で柱(はしら)を引(ひ)っ張(ぱ)っていました。
#
# 「おばあさん、これです！糸(いと)のやり方(やりかた)が変(へん)ですよ」とケンタは言(い)いました。
#
# 年寄り(としより)は顔(かお)を赤(あか)くしました。「ごめんなさい。孫(まご)が貸す(かす)と言(い)った道具(どうぐ)で、どれが一番(いちばん)魚(さかな)を釣(つ)るか比べ(くらべ)ていたのです。この場所(ばしょ)しか選ぶ(えらぶ)ことができませんでした。」
#
#
