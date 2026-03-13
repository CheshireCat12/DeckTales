class PromptGenerator:
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

        percent_words = max(int(len(words) * self.percentage_selection), 1)

        prompt = f"""# SYSTEM PROMPT
You are an experienced Japanese teacher who believes in immersion through reading. You also write short, engaging stories for learners ({self.vocab_level} level). Your stories are grammatically simple, use furigana for all kanji, and avoid gender/occupational stereotypes.

# USER PROMPT
I am an {self.vocab_level} learner using Anki. Today I have these {len(words)} vocabulary cards.
**I do NOT expect you to use all of them.** Instead, please:

0. **Choose a theme for an engaging story** then use this theme when you write the story.
1. **Select about {percent_words} words** from the list that can naturally appear together in one short story (e.g., around a single theme or location).
2. **Write a {len(words) * self.scaling_factor} word story** using those selected words.
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
