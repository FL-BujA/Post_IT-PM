# AGENTS.md

Standing instructions. Read this first, every session.

## What this project is

Post_IT-PM: a project-management system built in portions ("cards").
Layered: core (pure values/enums/errors), data (repositories over
SQLite), services, api.

## Layout

    cards/          one card per portion of work — the spec
    contracts/      frozen architecture + interface documents
    core/           pure stdlib layer, no IO
    data/           repositories; tests in tests/data/
    tests/          mirrors the source tree

## Rules

1. The card is the spec. cards/P-XX.md wins over anything said in chat.
   If a chat instruction contradicts the card, follow the card and say so.

2. Stay inside "Files allowed". Each card names the files it may touch.
   Do not modify anything else. If the card cannot be completed within
   that set, stop and say why.

3. Edit files in place. Do not rewrite or regenerate an existing file.
   If a file the card refers to is missing, stop and say so rather than
   reconstructing it.

4. Never commit on red. Tests must pass first.

5. Do not commit or push unless that message explicitly says to.

6. Contracts are frozen. Changing anything under contracts/ requires its
   own amendment card (CC-xx).

7. Do not survey the codebase. Read the card, the contract sections it
   names, and the files it allows. If you cannot find something after one
   search, stop and ask.

## Commands

    test:    cd /workspace/project/Post_IT-PM && python -m pytest -q
    finish:  ./finish_card.sh "P-XX: <description from the card goal line>"

## Reporting

Show complete, unedited command output. Do not summarise test results.

## Current state

See contracts/BUILD_STATE.md.
