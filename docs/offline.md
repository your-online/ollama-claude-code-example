# Offline walkthrough

## Prepare while online

Follow the README quick start through `check`. Install all software and download the
weights before disconnecting. Start only one Claude Code session. Do not start a
second automated model test alongside it.

## Disconnect deliberately

Turn Wi-Fi off yourself, unplug Ethernet and disable tethering if applicable. This
may interrupt other applications. `localhost` and `127.0.0.1` remain available.

On macOS, inspect `scutil --nwi`: it should report no active network information.
On Linux, inspect `ip route` and `ip -6 route`, and ensure there is no usable external
route. A single failed ping or blocked website is not sufficient proof of being offline.

This repository never modifies network settings for you. Reconnect using the same
OS controls afterwards.

## Generate an answer the model has not seen

In a second terminal, from the repository root:

```bash
python3 -m local_demo challenge
```

This replaces only the `fresh-proof` row in `audit_challenges` with a new random value
and prints a retrieval prompt **without the value**. Paste that prompt into the
Claude Code session. Observe the real Bash call and `sqlite3 -readonly` output.

Then check the model's answer in the second terminal:

```bash
python3 -m local_demo check-code PASTE_THE_RETURNED_CODE_HERE
```

`PASS` verifies that the returned code equals the current value in SQLite. This is
an exact comparison, without a model. Run `challenge` again to invalidate the previous
answer. A PASS alone does not attest network state: combine it with actually
disconnecting and observing the native tool call.

## What has been tested?

The predecessor harness retrieved a fresh code successfully while connected to the
internet. The offline disconnection procedure is provided for a user-operated test;
we do not claim that an offline experiment was performed as part of packaging or CI.
