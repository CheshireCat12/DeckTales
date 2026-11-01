"""Builds the prompt that asks the AI for a story from a batch of vocabulary."""


class PromptGenerator:
    """Generates story prompts using the same settings for every batch."""

    def __init__(
        self,
        vocab_level: str,
        story_theme: str,
        story_length_factor: int,
        selection_ratio: float,
    ) -> None:
        """
        Args:
            vocab_level: JLPT level used for the story, like "N4".
            story_theme: Currently unused: the prompt asks the AI to choose a theme.
            story_length_factor: Requested story length, in words per vocabulary card.
            selection_ratio: Fraction (0..1) of the words the AI should use in the story.
        """
        self.vocab_level = vocab_level
        self.story_theme = story_theme
        self.story_length_factor = story_length_factor
        self.selection_ratio = selection_ratio

    def generate(self, words: list) -> str:
        """Return the full prompt for a batch of words, as tuples of field values."""

        # Always ask for at least one word, even for small batches or low ratios
        target_word_count = max(int(len(words) * self.selection_ratio), 1)

        prompt = f"""# SYSTEM PROMPT
You are an experienced Japanese teacher who believes in immersion through reading. You also write short, engaging stories for learners ({self.vocab_level} level). Your stories are grammatically simple, use furigana for all kanji, and avoid gender/occupational stereotypes.

# USER PROMPT
I am an {self.vocab_level} learner using Anki. Today I have these {len(words)} vocabulary cards.
**I do NOT expect you to use all of them.** Instead, please:

0. **Choose a theme for an engaging story** then use this theme when you write the story.
1. **Select about {target_word_count} words** from the list that can naturally appear together in one short story (e.g., around a single theme or location).
2. **Write a {len(words) * self.story_length_factor} word story** using those selected words.
3. The story must be **easy and engaging to read**, with **{self.vocab_level}‑level grammar** and **short sentences**.
4. Use the writing style of graded books such as tadoku graded books, satory reader and genki japanese reader.
5. **Furigana format**: For every kanji, write the reading in parentheses **immediately after** the kanji.
✅ Example: 私(わたし)は 昨日(きのう) 友達(ともだち)と 公園(こうえん)へ 行(い)きました。
❌ Wrong: only adding readings for target words, or putting readings only once.

---

### Vocabulary List (select about {target_word_count} from here)
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
- **Select the words** from the list ({target_word_count} of them) – but you **do not** need to explain your choice. The selection is shown only in the `##SELECTED_WORDS##` section.
- **Write the story** under the `##STORY##` heading.

Now, generate your response following the **Output Format** exactly."""
        return prompt
