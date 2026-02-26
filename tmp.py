import re

from anki.collection import Collection


def clean_pitch(word: str) -> str:
    cleaned_word = re.sub(r"[ꜛꜜ]", "", word)

    return cleaned_word


dir_collection = (
    "/home/cheshirecat12/.var/app/net.ankiweb.Anki/data/Anki2/User 1/collection.anki2"
)


deck = "Takoboto"

col = Collection(dir_collection)
cardCount = col.card_count()
ids = col.find_cards(f"deck:{deck} is:due")

due_words = []
for id in ids:
    card = col.get_card(id)
    note = col.get_note(card.nid)

    current_word = []
    for key, value in note.items():
        if key in ["Japanese", "Reading"]:  # , "Meaning"]:
            current_word.append(clean_pitch(value))
    due_words.append(tuple(current_word))

vocab_level = "N4"

batch_size = 30

batch_num = 0

batch_words = due_words[batch_num * batch_size : (batch_num + 1) * batch_size]

batch_low_percent = int(len(batch_words) * 0.7) + 1
batch_up_percent = int(len(batch_words) * 0.8) + 1


prompt = f"""# SYSTEM PROMPT
You are an experienced Japanese teacher who believes in immersion through reading. You also write short, engaging stories for learners (N4 level). Your stories are grammatically simple, use furigana for all kanji, and avoid gender/occupational stereotypes.

# USER PROMPT
I am an {vocab_level} learner using Anki. Today I have these {len(batch_words)} vocabulary cards.
**I do NOT expect you to use all of them.** Instead, please:

1. **Select {batch_low_percent}-{batch_up_percent} words** from the list that can naturally appear together in one short story (e.g., around a single theme or location).
2. **Write a {batch_low_percent * 10}-{batch_up_percent * 10} word story** using ONLY those selected words.
3. The story must be **easy to read**, with **{vocab_level}‑level grammar** and **short sentences**.
4. Include a **small, satisfying twist** at the end.
5. Show **gender balance**: use gender‑neutral names (e.g., ユキ, アオイ, ケンタ) and give active roles to all characters regardless of gender.
6. **Furigana format**: For every kanji, write the reading in parentheses **immediately after** the kanji.
   ✅ Example: 私(わたし)は 昨日(きのう) 友達(ともだち)と 公園(こうえん)へ 行(い)きました。
   ❌ Wrong: only adding readings for target words, or putting readings only once.

---

### Vocabulary List (select {batch_low_percent}-{batch_up_percent} from here)
{batch_words}
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
   - The full story, with furigana for **all** kanji as specified in rule 6.
   - The story must be written as plain text, with normal spacing and punctuation.
   - Do **not** add extra line breaks inside the story unless they are part of the paragraph structure.

---

### Before writing the story, you will still:
- **Select the words** from the list ({batch_low_percent}-{batch_up_percent} of them) – but you **do not** need to explain your choice. The selection is shown only in the `##SELECTED_WORDS##` section.
- **Write the story** under the `##STORY##` heading.

Now, generate your response following the **Output Format** exactly.
"""

breakpoint()
#
#
# load_dotenv()
#
# # The client gets the API key from the environment variable `GEMINI_API_KEY`.
# client = genai.Client()
#
# # model = "gemini-3-flash-preview"
# # model = "gemini-2.5-flash"
# model = "gemini-2.5-flash-preview-09-2025"
#
# # response = client.models.generate_content(model=model, contents=prompt)
# # print(response.text)
#
#
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
# print(output)
