# DeckTales

DeckTales is an open‑source Anki add‑on that turns your daily vocabulary cards into short, engaging stories. Instead of memorising words in isolation, you see them used in context.

---

## Why DeckTales?

Spaced repetition is great for memorising facts, but words learned without context are harder to remember and apply. DeckTales bridges that gap by taking the words you’re about to review and weaving them into a coherent narrative. You get to see how each word behaves in real sentences, which helps with meaning, nuance, and grammar.

---

## How it works

1. You select an Anki deck and the fields you want to use (for example, “Kanji” and “Furigana”).
2. DeckTales gathers all the cards that are due for review from that deck (including subdecks).
3. It sends the words to the Gemini API, asking it to write a short story that includes those words.
4. The story appears in a new tab, with furigana shown directly under the kanji. You can toggle the furigana on or off.
5. If you’re not happy with the story, you can tweak the prompt and generate it again.

---

## Features

- **Context‑first learning** – vocabulary is never alone.
- **Works with any deck** – just pick a deck and the fields you want to use.
- **Batch generation** – if you have many due cards, they are split into several stories, each in its own tab.
- **Furigana toggle** – show or hide readings below the kanji.
- **Editable prompts** – if you’d like to change the style or theme of the story, you can modify the prompt before generating.

---

## Configuration

### API Key

DeckTales uses the Google Gemini API. You’ll need an API key:

1. Go to [Google AI Studio](https://aistudio.google.com/) and get a free API key.
2. In Anki you can create a file named `.env` inside the add‑on folder with the line:

```
GOOGLE_API_KEY=your_key_here
```

### Selecting a deck and fields

1. After installation, a new item “DeckTales” appears in the Anki tools menu. Click it.
2. In the left panel, choose a deck from the dropdown.
3. A dialog will show you all the fields (note types) that exist in that deck. Pick the fields you want to use – typically “Kanki” and “Furigana” (or “Front” / “Back”).
4. Adjust the other settings (model, batch size, etc.) and click **Apply**.

---

## Usage

Once you click **Apply**, DeckTales creates one tab for every batch of due cards. Each tab contains:

- The list of words (the batch)
- A checkbox to show/hide furigana
- A button to edit the prompt before generating
- A button to start generation
- A text area where the finished story will appear

You can switch between tabs and generate stories for each batch independently. If you change your deck or settings, click **Apply** again – the old tabs will be replaced.

---

## Feedback & Contributing

DeckTales is under active development. If you find a bug, have a suggestion, please open an issue on [GitHub](https://github.com/CheshireCat12/DeckTales).

Pull requests are very welcome – whether it’s a code improvement, a better default prompt, or a translation.

---

## License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.
