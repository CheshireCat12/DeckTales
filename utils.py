import re

from aqt import mw

DEBUG = False


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

    if DEBUG:
        due_words = [
            ("選ぶ", "えらぶ"),
            ("政府", "せいふ"),
            ("授業", "じゅぎょう"),
            ("景色", "けしき"),
            ("家来", "けらい"),
            ("年寄り", "としより"),
            ("決める", "きめる"),
            ("迷う", "まよう"),
            ("秘密", "ひみつ"),
            ("残念", "ざんねん"),
            ("糸", "いと"),
            ("やり方", "やりかた"),
            ("人気", "にんき"),
            ("比べ", "くらべ"),
            ("汚れる", "よごれる"),
            ("亡くなる", "なくなる"),
            ("壊れる", "こわれる"),
            ("苛める", "いじめる"),
            ("悪戯", "いたずら"),
            ("細い", "ほそい"),
            ("探す", "さがす"),
            ("酷い", "ひどい"),
            ("湯船", "ゆぶね"),
            ("狭い", "せまい"),
            ("西", "にし"),
            ("段々", "だんだん"),
            ("貸す", "かす"),
            ("儲ける", "もうける"),
            ("隠す", "かくす"),
            ("負んぶ", "おんぶ"),
            ("酢", "す"),
            ("薄い", "うすい"),
            ("注文", "ちゅうもん"),
            ("仕方", "しかた"),
            ("屹度", "きっと"),
            ("天皇", "てんのう"),
            ("真珠", "しんじゅ"),
            ("匂い", "におい"),
            ("蓮", "はす"),
            ("揺れる", "ゆれる"),
            ("複雑", "ふくざつ"),
            ("大違い", "おおちがい"),
            ("伸ばす", "のばす"),
            ("すっかり", ""),
            ("つっと", ""),
            ("然も", "しかも"),
            ("触る", "さわる"),
            ("柔らかい", "やわらかい"),
            ("必ず", "かならず"),
            ("板", "いた"),
            ("別", "べつ"),
            ("混む", "こむ"),
            ("照らす", "てらす"),
        ]

    return due_words


def format_words(words: list[tuple[str, str]]) -> str:
    # <b>{kanji}</b> <span style='font-size: smaller;'>({reading})</span>
    return "".join(
        [f"{w[0]}<span style='font-size: 12pt;'>({w[1]})</span>, " for w in words]
    )[:-2]


def parse_sections(text):
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
