import os
import sys

# import all of the Qt GUI library
from aqt.qt import (
    QObject,
    pyqtSignal,
)

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

from decktales.utils import DEBUG


class GeminiWorker(QObject):
    finished = pyqtSignal(str)  # Signal with the generated story
    error = pyqtSignal(str)  # Signal for errors

    def __init__(self, api, batch_words, prompt, model):
        super().__init__()
        self.api = api
        self.batch_words = batch_words
        self.prompt = prompt
        self.model = model

    def run(self):
        """This runs in the background thread"""
        try:
            # Your existing API call
            generated_text = self.api.call(self.batch_words, self.prompt, self.model)
            self.finished.emit(generated_text)
        except Exception as e:
            self.error.emit(str(e))


# model = "gemini-3-flash-preview"
# model = "gemini-2.5-flash"
# model = "gemini-2.5-flash-preview-09-2025"


class APICaller:
    def __init__(self):
        self.cach_data = {}

    def call(self, words: list[str], prompt: str, model: str) -> str:
        words_hash = hash(tuple(words))

        # API call if not cached yet
        if words_hash not in self.cach_data:
            if DEBUG:
                output = """##SELECTED_WORDS##
                選ぶ(えらぶ)
                景色(けしき)
                年寄り(としより)
                決める(きめる)
                迷う(まよう)
                秘密(ひみつ)
                残念(ざんねん)
                糸(いと)
                やり方(やりかた)
                人気(にんき)
                比べ(くらべ)
                伝える(つたえる)
                性格(せいかく)
                汚れる(よごれる)
                壊れる(こわれる)
                苛める(いじめる)
                悪戯(いたずら)
                細い(ほそい)
                探す(さがす)
                酷い(ひどい)
                狭い(せまい)
                西(にし)
                段々(だんだん)
                貸す(かす)

                ##THEME##
                人気の橋を壊す犯人探し

                ##STORY##
                ユキとケンタは酷い(ひどい)話(はなし)を聞(き)きました。公園(こうえん)の西(にし)にある人気(にんき)の小(ちい)さな橋(はし)が、段々(だんだん)と壊れる(こわれる)のです。誰(だれ)かが橋(はし)を苛める(いじめる)ような悪戯(いたずら)をしているのかもしれません。二人(ふたり)は探す(さがす)ことを決める(きめる)ために、現場(げんば)へ行(い)きました。

                橋(はし)のあたりは景色(けしき)が良(よ)く、細い(ほそい)道(みち)がある狭い(せまい)場所(ばしょ)でした。

                年寄り(としより)の女性(じょせい)がそこで釣(つ)りをしていました。ユキは彼女(かのじょ)に尋(たず)ねました。「何(なに)か変(へん)なことを見(み)ましたか。」彼女(かのじょ)の性格(せいかく)は優し(やさし)そうでしたが、質問(しつもん)に答(こた)えるのを迷う(まよう)様子(ようす)を見(み)せました。

                「私(わたし)には秘密(ひみつ)があります」と彼女(かのじょ)は小(ちい)さな声(こえ)で伝え(つたえる)ました。ケンタは足元(あしもと)を見(み)ました。橋(はし)の柱(はしら)に、汚れる(よごれる)た細い(ほそい)糸(いと)が巻(ま)き付(つ)いています。糸(いと)が強(つよ)い力(ちから)で柱(はしら)を引(ひ)っ張(ぱ)っていました。

                「おばあさん、これです！糸(いと)のやり方(やりかた)が変(へん)ですよ」とケンタは言(い)いました。

                年寄り(としより)は顔(かお)を赤(あか)くしました。「ごめんなさい。孫(まご)が貸す(かす)と言(い)った道具(どうぐ)で、どれが一番(いちばん)魚(さかな)を釣(つ)るか比べ(くらべ)ていたのです。この場所(ばしょ)しか選ぶ(えらぶ)ことができませんでした。」

                ユキはそれが酷い(ひどい)悪戯(いたずら)ではなかったことにホッとしました。橋(はし)が壊れる(こわれる)のは残念(ざんねん)ですが、原因(げんいん)はただの競争(きょうそう)でした。"""
                self.cach_data[words_hash] = output
            else:
                print("API call")

                load_dotenv()

                # The client gets the API key from the environment variable `GEMINI_API_KEY`.
                client = genai.Client()

                model_temperature = 1.1

                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=model_temperature),
                )

                self.cach_data[words_hash] = response.text

        return self.cach_data[words_hash]
