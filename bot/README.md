# Xutrix Lichess Bot

Local lichess-bot bridge for running Xutrix as an official Lichess BOT account.

## Files

- `config.xutrix.example.yml`: safe template committed to the repo.
- `config.yml`: local real config, ignored by git because it contains the bot token.
- `lichess-bot/`: local clone of lichess-bot, ignored by git.
- `venv/`: local Python virtual environment, ignored by git.

## First Run

Copy the template:

```powershell
Copy-Item .\bot\config.xutrix.example.yml .\bot\config.yml
```

Edit `bot\config.yml` and replace:

```text
PASTE_LICHESS_BOT_TOKEN_HERE
```

Run the bot:

```powershell
powershell -ExecutionPolicy Bypass -File .\bot\run.ps1
```

The default config accepts only standard casual challenges, runs one game at a
time, and lets Xutrix search up to depth 13 under Lichess clock control using
16 threads. The engine's built-in opening book is enabled by default through
the UCI `OwnBook` / `BookMaxPly` options.
