# DeckTales daily stories

Runs on an always-on Linux machine such as a Raspberry Pi. Every morning it downloads your
collection from AnkiWeb, writes stories from your due cards, and emails them to you.

It only ever downloads from AnkiWeb, so it can't change your cards there. Sync on your
computer or phone after studying, so that the next run sees your latest reviews.

## Setup

These steps assume a 64-bit OS and that you run them as your normal user.

1. **Copy the code to the Pi.** Run this on your computer, replacing `pi@raspberrypi`:

   ```sh
   ssh pi@raspberrypi 'mkdir -p ~/decktales'
   rsync -a --exclude .venv core.py prompt.py daily pi@raspberrypi:~/decktales/
   ```

2. **Install it on the Pi:**

   ```sh
   cd ~/decktales/daily
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

3. **Add your settings:**

   ```sh
   mkdir -p ~/.config/decktales
   cp config.example.toml ~/.config/decktales/config.toml
   nano ~/.config/decktales/config.toml
   ```

4. **Add your secrets.** Create a Gmail [app password](https://myaccount.google.com/apppasswords),
   which needs 2-Step Verification on the account. Then run this, pasting your values:

   ```sh
   install -m 600 /dev/null ~/.config/decktales/secrets.env
   nano ~/.config/decktales/secrets.env
   ```

   ```
   GEMINI_API_KEY=your_gemini_key
   GMAIL_APP_PASSWORD=your_app_password
   ```

5. **Log in to AnkiWeb.** Your password is used once and only a token is saved:

   ```sh
   .venv/bin/python daily_stories.py login
   ```

6. **Test it:**

   ```sh
   .venv/bin/python daily_stories.py test-email
   .venv/bin/python daily_stories.py run --dry-run   # uses Gemini, but sends no email
   .venv/bin/python daily_stories.py run
   ```

7. **Schedule it.** `enable-linger` lets it run while you aren't logged in:

   ```sh
   mkdir -p ~/.config/systemd/user
   cp decktales-daily.service decktales-daily.timer ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now decktales-daily.timer
   sudo loginctl enable-linger "$USER"
   ```

## Everyday use

| To do this | Run |
|---|---|
| See the next run | `systemctl --user list-timers decktales-daily.timer` |
| Run it now | `systemctl --user start decktales-daily.service` |
| Read the logs | `journalctl --user -u decktales-daily.service -e` |

To change the time, edit `OnCalendar` in the timer, then run `daemon-reload` and restart the timer.

## Good to know

- If the job fails, it tries to email you the error.
- Every due card in the deck needs all the fields in `fields`. A card without them fails the run.
- If Anki says the collection is too new or too old, upgrade with
  `.venv/bin/pip install -U anki`.
