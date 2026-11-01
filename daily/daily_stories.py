#!/usr/bin/env python3
"""
Email a set of DeckTales stories built from today's due cards.

Meant to run once a day on an always-on machine such as a Raspberry Pi, without
desktop Anki. See README.md for setup. It only ever downloads your collection from
AnkiWeb: nothing here can upload to AnkiWeb or change your cards there.

Commands:
    login       Log in to AnkiWeb once and save the resulting token.
    run         Download the collection, generate the stories, and email them.
    run --dry-run   The same, but save the email as an HTML file instead of sending it.
    test-email  Send a short email to check the Gmail settings.
"""

import argparse
import getpass
import json
import os
import smtplib
import socket
import sys
import time
import tomllib
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from email.message import EmailMessage
from html import escape
from math import ceil
from pathlib import Path
from typing import Callable

# core.py and prompt.py live in the folder above this one
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anki.collection import Collection
from anki.errors import SyncError, SyncErrorKind
from anki.sync_pb2 import SyncAuth, SyncStatusResponse

from core import collect_due_words, parse_sections, remove_furigana
from prompt import PromptGenerator

CONFIG_DIR = Path.home() / ".config" / "decktales"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.toml"
DEFAULT_SECRETS_PATH = CONFIG_DIR / "secrets.env"
COLLECTION_PATH = Path.home() / ".local" / "share" / "decktales" / "collection.anki2"

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_TIMEOUT_SECONDS = 300  # some models took minutes to answer even short requests
GEMINI_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}  # rate limits and temporary failures
RETRY_DELAYS_SECONDS = (60, 300)  # waits between attempts, so 3 attempts in total
PAUSE_BETWEEN_STORIES_SECONDS = 15  # stays gentle on the free tier's rate limits


class TemporaryError(Exception):
    """A failure that is worth retrying, such as a rate limit or a network problem."""


def retry(action: Callable, description: str):
    """Run `action`, retrying after each TemporaryError until the attempts run out."""
    for delay_seconds in RETRY_DELAYS_SECONDS:
        try:
            return action()
        except TemporaryError as error:
            print(f"{description} failed ({error}), retrying in {delay_seconds}s", flush=True)
            time.sleep(delay_seconds)
    return action()


def load_config(path: Path) -> dict:
    """Read the settings file."""
    if not path.exists():
        raise SystemExit(f"Settings file not found: {path}\nSee README.md to create it.")
    with open(path, "rb") as config_file:
        return tomllib.load(config_file)


def load_secrets(path: Path) -> dict:
    """Read KEY=VALUE lines from the secrets file. Environment variables take priority."""
    secrets = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                secrets[key.strip()] = value.strip().strip("'\"")
    for key in ("ANKIWEB_HKEY", "GEMINI_API_KEY", "GMAIL_APP_PASSWORD"):
        if key in os.environ:
            secrets[key] = os.environ[key]
    return secrets


def require_secret(secrets: dict, key: str) -> str:
    """Return a secret, or stop with a message naming the missing one."""
    if not secrets.get(key):
        raise RuntimeError(f"{key} is missing from the secrets file")
    return secrets[key]


def save_secret(path: Path, key: str, value: str) -> None:
    """Add or replace one secret, keeping the file readable only by this user."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if not line.startswith(f"{key}=")
        ]
    lines.append(f"{key}={value}")
    # The mode only applies to a new file, so existing files are restricted separately
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as secrets_file:
        secrets_file.write("\n".join(lines) + "\n")
    os.chmod(path, 0o600)


def make_sync_auth(hkey: str, config: dict) -> SyncAuth:
    """Build the sync credentials. `endpoint` is only set for a self-hosted sync server."""
    endpoint = config.get("anki", {}).get("endpoint")
    return SyncAuth(hkey=hkey, endpoint=endpoint) if endpoint else SyncAuth(hkey=hkey)


def login(config: dict, secrets_path: Path) -> None:
    """Exchange an AnkiWeb username and password for a token, and save only the token."""
    username = input("AnkiWeb email: ").strip()
    password = getpass.getpass("AnkiWeb password (not saved): ")

    COLLECTION_PATH.parent.mkdir(parents=True, exist_ok=True)

    def log_in() -> SyncAuth:
        col = Collection(str(COLLECTION_PATH))
        try:
            return col.sync_login(username, password, config.get("anki", {}).get("endpoint"))
        finally:
            col.close()

    # On a worker thread for the same reason as in main()
    with ThreadPoolExecutor(max_workers=1) as executor:
        auth = executor.submit(log_in).result()

    save_secret(secrets_path, "ANKIWEB_HKEY", auth.hkey)
    print(f"Logged in. Token saved to {secrets_path}")


def open_latest_collection(auth: SyncAuth) -> Collection:
    """
    Replace the local collection with AnkiWeb's copy, and return it opened.

    This deliberately doesn't use Anki's normal sync, which can upload changes. The only
    transfer made here is a full download, so the copy on AnkiWeb can't be affected. It
    downloads on every run so that the stories always come from AnkiWeb's latest copy, and
    an unreachable server fails the run instead of reusing an old one.
    """
    COLLECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    col = Collection(str(COLLECTION_PATH))

    try:
        # AnkiWeb can direct an account to a specific server, and only sync_status reveals
        # which. It only contacts AnkiWeb if the local copy looks unchanged, so mark this
        # disposable copy as fully synced. The download below replaces it anyway.
        col.db.execute("update col set ls = max(mod, scm)")
        status = col.sync_status(auth)
        if status.new_endpoint:
            auth.endpoint = status.new_endpoint

        print("Downloading collection", flush=True)
        col.close_for_full_sync()
        try:
            col.full_upload_or_download(auth=auth, server_usn=None, upload=False)
        finally:
            col.reopen(after_full_sync=True)
        return col
    except Exception:
        col.close()
        raise


def download_collection(auth: SyncAuth) -> Collection:
    """Run open_latest_collection, retrying network problems such as a slow start after a reboot."""

    def attempt() -> Collection:
        try:
            return open_latest_collection(auth)
        except SyncError as error:
            # A rejected token won't start working by itself, so don't retry
            if error.kind is SyncErrorKind.AUTH:
                raise RuntimeError(
                    "AnkiWeb rejected the saved token. Run: daily_stories.py login"
                ) from error
            raise TemporaryError(error) from error
        except Exception as error:
            raise TemporaryError(error) from error

    return retry(attempt, "Collection download")


def call_gemini(prompt: str, model: str, api_key: str) -> str:
    """Send a prompt to Gemini and return the text of its answer."""
    request = urllib.request.Request(
        GEMINI_URL.format(model=model),
        data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8"),
        # Sent as a header so that the key can't appear in a logged URL
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=GEMINI_TIMEOUT_SECONDS) as response:
            answer = json.load(response)
    except urllib.error.HTTPError as error:
        message = f"Gemini returned HTTP {error.code} {error.reason}"
        if error.code in GEMINI_RETRY_STATUS_CODES:
            raise TemporaryError(message) from error
        raise RuntimeError(message) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        raise TemporaryError(f"could not reach Gemini: {error}") from error

    candidates = answer.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no answer: {answer.get('promptFeedback', 'no details')}")

    parts = candidates[0].get("content", {}).get("parts", [])
    # Parts marked as thoughts are the model's reasoning, not its answer
    return "".join(part.get("text", "") for part in parts if not part.get("thought"))


def generate_story(prompt: str, model: str, api_key: str) -> dict:
    """Return the sections of a new story, treating an answer with no story as a failure."""

    def attempt() -> dict:
        sections = parse_sections(call_gemini(prompt, model, api_key))
        if not sections["STORY"]:
            raise TemporaryError("the answer had no ##STORY## section")
        return sections

    return retry(attempt, "Story generation")


def generate_stories(due_words: list, config: dict, api_key: str) -> list[dict]:
    """
    Generate one story per batch of words.

    A failed batch is recorded rather than raised, so that one failure doesn't lose the
    other stories. Each result holds "words" and either "theme" and "story", or "error".
    """
    story_settings = config["story"]
    batch_size = story_settings["batch_size"]
    prompt_generator = PromptGenerator(
        vocab_level=story_settings["vocab_level"],
        story_theme="",
        story_length_factor=story_settings["story_length_factor"],
        selection_ratio=story_settings["selection_ratio"],
    )

    stories = []
    batch_count = ceil(len(due_words) / batch_size)
    for batch_index in range(batch_count):
        if batch_index > 0:
            time.sleep(PAUSE_BETWEEN_STORIES_SECONDS)

        batch_words = due_words[batch_index * batch_size : (batch_index + 1) * batch_size]
        print(f"Generating story {batch_index + 1} of {batch_count}", flush=True)
        try:
            sections = generate_story(
                prompt_generator.generate(words=batch_words),
                story_settings["model"],
                api_key,
            )
            stories.append(
                {"words": batch_words, "theme": sections["THEME"], "story": sections["STORY"]}
            )
        except (TemporaryError, RuntimeError) as error:
            print(f"Story {batch_index + 1} failed: {error}", flush=True)
            stories.append({"words": batch_words, "error": str(error)})
    return stories


def format_word_line(word_fields: tuple) -> str:
    """Format a card as plain text: the word, then its reading if it has one."""
    word = word_fields[0]
    reading = word_fields[1] if len(word_fields) > 1 else ""
    return f"{word} ({reading})" if reading else word


def story_text_for_email(story: dict, show_furigana: bool) -> str:
    """Return a story's text with or without its furigana."""
    return story["story"] if show_furigana else remove_furigana(story["story"])


def build_plain_body(stories: list[dict], show_furigana: bool) -> str:
    """Build the plain text version of the email."""
    blocks = []
    for number, story in enumerate(stories, start=1):
        words = "、".join(format_word_line(word_fields) for word_fields in story["words"])
        if "error" in story:
            blocks.append(f"Story {number}: could not be generated\n{story['error']}\n\nWords: {words}")
        else:
            text = story_text_for_email(story, show_furigana)
            blocks.append(f"Story {number}: {story['theme']}\n\n{text}\n\nWords: {words}")
    return "\n\n----------\n\n".join(blocks)


def build_html_body(stories: list[dict], show_furigana: bool) -> str:
    """Build the HTML version of the email. All text is escaped, as cards can contain markup."""
    blocks = []
    for number, story in enumerate(stories, start=1):
        words = "、".join(escape(format_word_line(word_fields)) for word_fields in story["words"])
        words_html = f"<p style='color:#666;font-size:14px;'>{words}</p>"
        if "error" in story:
            blocks.append(
                f"<h2 style='font-size:18px;'>Story {number}: could not be generated</h2>"
                f"<p style='color:#b00020;'>{escape(story['error'])}</p>{words_html}"
            )
        else:
            paragraphs = story_text_for_email(story, show_furigana).split("\n\n")
            story_html = "".join(
                f"<p style='font-size:18px;line-height:1.8;'>{escape(paragraph)}</p>"
                for paragraph in paragraphs
            )
            blocks.append(
                f"<h2 style='font-size:18px;'>Story {number}: {escape(story['theme'])}</h2>"
                f"{story_html}{words_html}"
            )
    return f"<html><body>{'<hr>'.join(blocks)}</body></html>"


def send_email(config: dict, app_password: str, subject: str, plain: str, html: str | None = None) -> None:
    """Send an email through Gmail."""
    email_settings = config["email"]

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = email_settings["from"]
    message["To"] = email_settings["to"]
    message.set_content(plain)
    if html:
        message.add_alternative(html, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
        smtp.login(email_settings["from"], app_password)
        smtp.send_message(message)


def run_job(config: dict, secrets: dict, dry_run: bool) -> int:
    """Do the daily work and return the exit code: 1 if any story failed, otherwise 0."""
    today = date.today().isoformat()
    api_key = require_secret(secrets, "GEMINI_API_KEY")
    auth = make_sync_auth(require_secret(secrets, "ANKIWEB_HKEY"), config)

    col = download_collection(auth)
    try:
        due_words = collect_due_words(col, config["anki"]["deck"], config["anki"]["fields"])
    finally:
        col.close()

    # Cards from the same note can be due together, so remove repeated words
    due_words = list(dict.fromkeys(due_words))
    due_count = len(due_words)
    max_cards = config["story"]["max_cards"]
    due_words = due_words[:max_cards]
    print(f"{due_count} words due, using {len(due_words)}", flush=True)

    if due_words:
        stories = generate_stories(due_words, config, api_key)
        generated_count = sum("error" not in story for story in stories)
        subject = f"DeckTales {today}: {generated_count} of {len(stories)} stories"
        show_furigana = config["story"].get("show_furigana", True)
        plain = build_plain_body(stories, show_furigana)
        html = build_html_body(stories, show_furigana)
        if due_count > len(due_words):
            note = f"{due_count} words were due. This email covers the first {max_cards} (max_cards)."
            plain = f"{note}\n\n{plain}"
            html = html.replace("<body>", f"<body><p>{escape(note)}</p>", 1)
        exit_code = 0 if generated_count == len(stories) else 1
    else:
        subject = f"DeckTales {today}: nothing due"
        plain = f"No cards are due in {config['anki']['deck']} today."
        html = None
        exit_code = 0

    if dry_run:
        output_path = COLLECTION_PATH.parent / f"dry-run-{today}.html"
        output_path.write_text(html or plain, encoding="utf-8")
        print(f"Dry run: not sent. Subject: {subject}\nSaved to {output_path}")
    else:
        send_email(config, require_secret(secrets, "GMAIL_APP_PASSWORD"), subject, plain, html)
        print(f"Sent: {subject}")
    return exit_code


def run_with_failure_email(config: dict, secrets: dict, dry_run: bool) -> int:
    """Run the job, and try to send an email if it fails, so that a failure doesn't go unnoticed."""
    try:
        return run_job(config, secrets, dry_run)
    except Exception as error:
        print(f"Daily stories failed: {type(error).__name__}: {error}", flush=True)
        if not dry_run and secrets.get("GMAIL_APP_PASSWORD"):
            try:
                send_email(
                    config,
                    secrets["GMAIL_APP_PASSWORD"],
                    f"DeckTales {date.today().isoformat()}: failed",
                    f"Today's stories could not be created.\n\n{type(error).__name__}: {error}",
                )
            except Exception as email_error:
                print(f"The failure email also failed: {email_error}", flush=True)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Email DeckTales stories for today's due cards.")
    parser.add_argument("command", choices=["login", "run", "test-email"])
    parser.add_argument("--dry-run", action="store_true", help="save the email instead of sending it")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--secrets", type=Path, default=DEFAULT_SECRETS_PATH)
    arguments = parser.parse_args()

    config = load_config(arguments.config)

    if arguments.command == "login":
        login(config, arguments.secrets)
        return 0

    secrets = load_secrets(arguments.secrets)

    if arguments.command == "test-email":
        send_email(
            config,
            require_secret(secrets, "GMAIL_APP_PASSWORD"),
            "DeckTales test email",
            "Your Gmail settings work.",
        )
        print("Test email sent")
        return 0

    # Anki prints a stack trace for slow calls on the main thread, which would clutter the logs
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(run_with_failure_email, config, secrets, arguments.dry_run).result()


if __name__ == "__main__":
    sys.exit(main())
