# Desktop Watcher

Source: [`integrations/desktop/`](../../integrations/desktop/), [`packaging/junas-local.spec`](../../packaging/junas-local.spec), [`packaging/macos/`](../../packaging/macos/)

Compatibility path: `src/junas/desktop/`

Maturity: `experimental-local-fallback`

Runtime target: macOS local watcher and packaged local daemon.

`junas-watch` remains a packaged console script for explicit opt-in local review. Its
maturity is `experimental-local-fallback`; do not present it as production endpoint
enforcement.

## Intended Use

Use the desktop watcher for offline local fallback, demos, and power users who
explicitly choose local file, folder, or clipboard review. Do not use it as enterprise
enforcement, fleet policy, endpoint DLP, or proof that every local workflow was
reviewed. Enforced production workflows should use direct API integration, Outlook Smart
Alerts, DMS hooks, or managed browser adapters.

Build:

```sh
uv sync --extra local --extra packaging
uv run python -m spacy download en_core_web_sm
./scripts/package_macos_desktop.sh
```

Run packaged daemon:

```sh
./dist/junas-local/junas-local
curl http://127.0.0.1:8765/ready
```

## Optional LaunchAgent Install

`packaging/macos/install.sh` installs a LaunchAgent with `RunAtLoad` and `KeepAlive`.
Treat it as optional and admin-controlled, not a default developer quickstart path. For
developer smoke tests, run `./dist/junas-local/junas-local` directly and install the
LaunchAgent only when an operator has approved auto-start behavior for that profile.

```sh
packaging/macos/install.sh
```

Current behavior:

- Local daemon binds `127.0.0.1:8765` by default.
- `junas.desktop.watch` can review watched files and optional clipboard content.
- `--anonymize-output-dir` writes anonymized copies only when explicitly configured.
- File and watched-folder review skip files above the default `--max-file-bytes`
  cap of `5242880` bytes; override with `--max-file-bytes` or
  `JUNAS_WATCH_MAX_FILE_BYTES`.
- Supported default file suffixes are `.txt`, `.md`, `.csv`, `.json`, and `.eml`.

## Opt-In Local Fallback Flow

The watcher runs only when a user or operator starts it with an explicit source:

```sh
uv run junas-watch ./draft.txt --base-url http://127.0.0.1:8765
uv run junas-watch --watch-folder ./drop --once --base-url http://127.0.0.1:8765
uv run junas-watch ./large-draft.txt --max-file-bytes 10485760 --base-url http://127.0.0.1:8765
uv run junas-watch --clipboard --once --base-url http://127.0.0.1:8765
uv run junas-watch --clipboard --once --copy-anonymized-clipboard --base-url http://127.0.0.1:8765
```

If no file path, `--watch-folder`, or `--clipboard` is provided, the CLI exits with an argument error. Clipboard polling is never enabled by default.

Foreground app profile selection is macOS-first and enabled by default through
`--foreground-profile auto`. The watcher uses the foreground app name/bundle id to set
the `/review` `document_type`, `surface`, `workflow`, and `review_profile` metadata:

| Foreground apps | Profile | Review metadata |
|---|---|---|
| Terminal, iTerm2, Warp, WezTerm, Kitty, Alacritty, Ghostty, Hyper | `terminal` | secrets-heavy terminal text; `document_type=terminal_buffer`, `surface=desktop`, `workflow=desktop_watch`, `review_profile=strict` |
| Slack, Discord, Microsoft Teams | `chat` | email/PII-heavy chat text; `document_type=chat_message`, `surface=other`, `workflow=collaboration_message`, `review_profile=strict` |
| VS Code, Cursor, VSCodium | `editor` | broad source/editor text; `document_type=source_buffer`, `surface=desktop`, `workflow=desktop_watch`, `review_profile=audit_grade` |
| Safari, Chrome, Edge, Firefox, Brave, Arc | `browser` | browser GenAI prompt text; `document_type=genai_prompt`, `surface=browser_genai`, `workflow=prompt_submit`, `review_profile=strict` |

Override or disable the selection explicitly:

```sh
uv run junas-watch --clipboard --once --foreground-profile terminal
uv run junas-watch --clipboard --once --foreground-profile off --review-profile strict
```

The local watcher does not inspect browser DOM. DOM-aware prompt handling remains owned
by the managed browser adapter.

Reference config sample: `docs/integrations/desktop-watcher.config.sample.toml`.
The current CLI is flag/env based and does not parse that file directly; use it as an
operator checklist when building shell wrappers, MDM profiles, or runbooks. The sample
keeps `clipboard = false` and requires explicit user opt-in through `--clipboard`.

## Folder Watch

- `--watch-folder` recursively scans supported text-like suffixes.
- Files larger than `--max-file-bytes` are skipped before content is read or sent
  to the backend. The JSON summary includes `status="skipped"`, byte counts, and
  a skipped-file reason, but not raw file content.
- The first scan reviews existing matching files, then later scans review changed files.
- `--poll-seconds` controls polling interval.
- `--once` performs one scan and exits.
- `--anonymize-output-dir` writes anonymized copies only when findings exist, output is explicitly configured, and the file was not skipped by the size cap.

## Clipboard Watch

- `--clipboard` reads macOS clipboard text through `pbpaste`.
- Empty or unchanged clipboard text is skipped.
- Clipboard review emits a JSON summary; it should not print raw clipboard content.
- `--copy-anonymized-clipboard` calls `/anonymize` only after findings exist and writes the anonymized text back with `pbcopy`.
- Use clipboard mode only for demos, offline local review, or power-user workflows where the user opted in.

AppleScript and Shortcuts wrappers live in [`macos-automation.md`](./macos-automation.md).

## Threat Model

- Clipboard sensitivity: `--clipboard` reads the whole current macOS clipboard through
  `pbpaste` when polling runs. Clipboard mode must stay off by default because the
  clipboard may contain passwords, tokens, personal messages, or copied customer data.
- Local token use: `--local-token`, `--local-token-file`, and
  `JUNAS_LOCAL_DAEMON_TOKEN` send `X-Junas-Local-Token` to the local daemon. Treat the
  token as same-user local secret material; do not paste it into shell history, shared
  logs, notifications, or bug reports.
- Notifications: `--notify` uses macOS `osascript` notifications only when findings are
  present. Notifications should contain counts and source labels only; they can still
  expose a path or the word `clipboard` to screenshots, screen sharing, or lock-screen
  previews.
- Watched-folder scope: `--watch-folder` scans recursively for supported suffixes. Use a
  dedicated drop directory, not a home directory, synced drive root, mail archive, or
  source tree with unrelated customer files.
- Accidental large-file scans: the current CLI has a default max-file-size cap.
  Oversized matching files fail closed as skipped JSON summaries before content
  is read or sent to the backend. Operators should still test with `--once`, keep
  watched folders small, and avoid broad recursive roots.

## Enforcement Boundary

The desktop watcher is not enterprise endpoint enforcement.

- It does not block paste, save, send, upload, browser submit, email send, or DMS check-in.
- It does not run as an EDR, DLP agent, kernel extension, browser policy, or MDM control.
- It cannot prove that every local file, clipboard value, or app workflow was reviewed.
- It should route enforced workflows to direct API, Outlook Smart Alerts, DMS hooks, or managed browser adapters.

## Threat Model

The desktop watcher is an experimental opt-in local fallback and should not be treated as enterprise endpoint enforcement.

### Clipboard sensitivity

- Clipboard monitoring is enabled only when the user explicitly starts the watcher with `--clipboard`.
- Clipboard contents should be treated as sensitive and should not be written to logs or exposed in error messages.
- Clipboard review is intended for local review workflows where the user has explicitly opted in.

### Local authentication

- When local daemon ACLs are enabled, use `--local-token`, `--local-token-file`, or `JUNAS_LOCAL_DAEMON_TOKEN`.
- Authentication failures must not expose clipboard or watched file contents.

### Notifications and review

- The watcher provides local review results only.
- It does not guarantee that notifications are acknowledged or acted upon.
- Users remain responsible for deciding whether reviewed content should be shared.

### Watched-folder scope

- Configure `--watch-folder` only for directories intended for review.
- Avoid monitoring unnecessarily broad locations to reduce accidental review of unrelated files.
- Use `--once` when a single review pass is sufficient.

### Large-file considerations

- The watcher is intended for supported text-like files.
- Restrict watched folders to the intended review scope to reduce accidental scans of large or unrelated files.
- Enterprise enforcement workflows should use supported integrations instead of relying on local folder monitoring.

## Auth And Output

- Use `--local-token`, `--local-token-file`, or `JUNAS_LOCAL_DAEMON_TOKEN` when local daemon ACLs are enabled.
- Output is a JSON summary with source, risk, finding count, document score, and optional anonymized path.
- Oversized files emit a JSON-safe skipped-file reason and byte counts without raw file content.
- Do not redirect watcher output to shared logs unless paths and counts are acceptable for that environment.
- Keep `--anonymize-output-dir` scoped to a user-approved directory.

Security model:

- Desktop watcher is an opt-in local fallback, not enterprise endpoint enforcement.
- Local daemon ACLs use `X-Junas-Local-Token` when enabled.
- Clipboard polling must remain explicit user opt-in.
- Output must stay under the configured output directory.
- Auth failures must not print sensitive clipboard or file content.
