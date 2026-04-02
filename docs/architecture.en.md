# Peneo Architecture Overview

This document gives a high-level view of the current implementation structure of `Peneo`.
It describes the actual responsibilities and data flow that exist in the codebase as of `2026-03-26`, not the full MVP vision.

## 1. Principles

The current implementation is built around these responsibilities:

- `UI`: Textual rendering and event entry points
- `input dispatcher`: normalizes key input into reducer-facing `Action` values
- `reducer`: updates `AppState` as a pure function and returns required side effects as `Effect`
- `selectors`: builds render-only models from `AppState`
- `services`: use-case boundaries that execute effects outside the reducer
- `adapters`: implementations for external dependencies such as the OS, filesystem, and clipboard

The design keeps branching logic out of widgets and centralizes state transitions under `state/`.

## 2. Overall Structure

```mermaid
flowchart LR
    subgraph UI["UI (`src/peneo/app.py`, `src/peneo/ui`)"]
        App["PeneoApp"]
        Widgets["CurrentPathBar / MainPane / SidePane / CommandPalette / ConflictDialog / AttributeDialog / HelpBar / StatusBar"]
    end

    subgraph State["State (`src/peneo/state`)"]
        Input["input.py\nkey input dispatcher"]
        Actions["actions.py\nAction definitions"]
        Reducer["reducer.py\nreduce_app_state"]
        Effects["effects.py\nEffect definitions"]
        Selectors["selectors.py\nselect_shell_data"]
        Models["models.py\nAppState / PaneState / UiMode"]
        Palette["command_palette.py\npalette candidate builder"]
    end

    subgraph Services["Services (`src/peneo/services`)"]
        Snapshot["browser_snapshot.py"]
        Clipboard["clipboard_operations.py"]
        Mutations["file_mutations.py"]
        Launch["external_launcher.py"]
    end

    subgraph Adapters["Adapters (`src/peneo/adapters`)"]
        FS["filesystem.py"]
        FileOps["file_operations.py"]
        External["external_launcher.py"]
    end

    subgraph Display["Display models (`src/peneo/models`)"]
        Shell["shell_data.py\nThreePaneShellData"]
        Domain["file_operations.py / external_launch.py"]
    end

    App --> Input
    Input --> Actions
    App --> Reducer
    Reducer --> Models
    Reducer --> Effects
    App --> Selectors
    Selectors --> Models
    Selectors --> Palette
    Selectors --> Shell
    App --> Widgets
    Effects --> Services
    Snapshot --> FS
    Clipboard --> FileOps
    Mutations --> FileOps
    Launch --> External
    Services --> Domain
```

## 3. Flow From Key Input To Rendering

The core flow is: input -> Action -> state update -> effect execution -> selector -> rerender.

```mermaid
sequenceDiagram
    participant User as User
    participant App as PeneoApp
    participant Input as dispatch_key_input
    participant Reducer as reduce_app_state
    participant Worker as Textual worker
    participant Service as services
    participant Selector as select_shell_data
    participant UI as Widgets

    User->>App: Key input
    App->>Input: AppState, key, character
    Input-->>App: Sequence of Actions
    loop Each Action
        App->>Reducer: AppState, Action
        Reducer-->>App: ReduceResult(state, effects)
    end
    opt Effects exist
        App->>Worker: Run effect asynchronously
        Worker->>Service: snapshot / paste / mutation / launch
        Service-->>App: success / failure action
        App->>Reducer: success / failure action
    end
    App->>Selector: Latest AppState
    Selector-->>App: ThreePaneShellData
    App->>UI: Rerender path / panes / dialogs / help / status
```

## 4. Responsibilities Of Major Modules

### `src/peneo/app.py`

- `PeneoApp` assembles the whole application
- Sends Textual `Key` events into the central dispatcher
- Bridges reducer effects to workers and services
- Updates UI widgets using selector output

### `src/peneo/state/input.py`

- Normalizes key input into `Action` values by mode
- The main currently supported modes are `BROWSING`, `FILTER`, `RENAME`, `CREATE`, `PALETTE`, `CONFIRM`, and `BUSY`
- Absorbs context-dependent keys such as `Esc`

### `src/peneo/state/reducer.py`

- The single update point for `AppState`
- Manages screen transitions, cursor movement, selection, filter, sort, clipboard, rename/create/delete, palette execution, file search, config editor, split terminal, and dialog state
- Does not perform external I/O directly; instead returns effects for snapshot loads, child-pane loads, paste, rename/create/delete, external launch, file search, split-terminal lifecycle, and config save
- Matches async results by request id and discards stale snapshot results

### `src/peneo/state/selectors.py`

- Builds `ThreePaneShellData` from `AppState`
- Applies filter and sort only to the main pane, while parent and child panes stay fixed to name order plus directories-first
- Formats the display text for the help bar, status bar, input bar, command palette, conflict dialog, attribute dialog, config dialog, and split terminal
- Also assembles cut-item dimming and the summary line fields such as `item_count`, `selected_count`, and `sort_label`

### `src/peneo/state/command_palette.py`

- Builds command palette candidates and filters them by query
- The current palette includes `Find file`, `Grep`, `Show attributes`, `Rename`, `Extract archive`, `Copy path`, `Open in file manager`, `Open terminal here`, `Open/Close split terminal`, `Show/Hide hidden files`, `Edit config`, `Create file`, and `Create directory`
- `Show attributes` appears only for a single target and opens a read-only attribute dialog with `Name`, `Type`, `Path`, `Size`, `Modified`, `Hidden`, and `Permissions`
- `Extract archive` appears only for a single supported archive (`.zip` / `.tar` / `.tar.gz` / `.tar.bz2`) and reuses the pending input bar to edit the destination path
  - The input accepts both absolute and relative paths, and relative paths are resolved from the archive file's parent directory
  - The default value is the absolute path to a same-name directory next to the archive
  - The reducer performs a preflight scan for destination conflicts and uses the confirm dialog before continuing when conflicts are found
  - Extraction runs in `BUSY` mode and reports entry-count progress through the status bar
- `Find file` switches the palette into file-search mode and reuses the same UI to show recursive matches under the current directory
  - Plain input runs a case-insensitive partial basename match
  - `re:`-prefixed input is treated as a Python regex against basenames, and invalid regex patterns are surfaced inline in the palette
- `Grep` switches the palette into content-search mode and renders matches as `relative/path:line:content`
  - Plain input runs a case-insensitive fixed-string search
  - `re:`-prefixed input is treated as regex, and invalid patterns are surfaced inline in the palette
- The split-terminal and hidden-files entries change their labels to reflect the current state

### `src/peneo/services/`

- `browser_snapshot.py`: builds the three-pane snapshot from the real filesystem
- `clipboard_operations.py`: handles copy / cut / paste execution and conflict detection
- `config.py`: loads, validates, saves, and renders `config.toml`, including normalized startup editor settings such as `editor.command`
- `file_search.py`: handles recursive file search under the current directory, interpreting both plain input and `re:` regex input before filtering results according to hidden-file visibility
- `grep_search.py`: handles recursive content search through `rg`, treating plain input as fixed-string search and `re:` input as regex before applying hidden-file visibility rules
- `file_mutations.py`: handles rename / create / trash delete
- `archive_extract.py`: handles preflight archive scans, destination conflict detection, safe extraction with the standard-library `zipfile` / `tarfile` modules, and progress notifications
- `external_launcher.py`: handles default-app open, editor-in-current-terminal launch, terminal launch, and copying a path to the system clipboard, resolving editors in config -> `$EDITOR` -> built-in order
- `split_terminal.py`: starts PTY-backed embedded terminal sessions, forwards I/O, and reports exit events

### `src/peneo/adapters/`

- `filesystem.py`: enumerates directory entries and reads metadata
- `file_operations.py`: performs copy / move / rename / create / trash and related file operations
- `external_launcher.py`: hides OS-specific command differences and launches external processes

### `src/peneo/models/`

- `shell_data.py`: render-only models
- `external_launch.py` and `file_operations.py`: request / result models exchanged between services and the reducer
- `state/models.py`: state models managed by the reducer

## 5. Modes And Input Boundaries

```mermaid
stateDiagram-v2
    [*] --> BROWSING
    BROWSING --> FILTER: /
    BROWSING --> RENAME: F2
    BROWSING --> PALETTE: :
    PALETTE --> CREATE: Enter on create command
    PALETTE --> CONFIG: Enter on Edit config
    PALETTE --> PALETTE: Enter on Find file / type file-search query
    PALETTE --> BROWSING: Enter on other command / Esc
    CONFIG --> BUSY: s save
    CONFIG --> BROWSING: Esc
    FILTER --> BROWSING: Enter / Down / Esc
    RENAME --> BUSY: Enter
    CREATE --> BUSY: Enter
    RENAME --> BROWSING: Esc
    CREATE --> BROWSING: Esc
    CONFIRM --> BROWSING: delete confirm/cancel
    CONFIRM --> BROWSING: paste conflict resolved/cancelled
    CONFIRM --> RENAME: rename conflict dismissed
    CONFIRM --> CREATE: create conflict dismissed
    BUSY --> BROWSING: effect completes

    BUSY --> BUSY: arbitrary keys are suppressed
```

Notes:

- `BROWSING`
  - Handles navigation, selection, starting filter input, paste, delete, rename, palette, and sort switching
  - If an active filter exists, `Esc` clears the filter before clearing the selection
- `FILTER`
  - Handles text input, `Backspace`, `Enter`, `Down`, and `Esc`
- `PALETTE`
  - Handles query updates, candidate cursor movement, command execution, and cancel
- `CONFIG`
  - Edits startup defaults in the config overlay, including terminal-editor presets, saves with `s`, and opens the raw `config.toml` in a terminal editor with `e`
- `RENAME` / `CREATE`
  - Edits names in the input bar and issues a mutation effect on `Enter`
- `CONFIRM`
  - Handles delete confirmation, paste conflicts, and duplicate-name warnings for rename/create
- `BUSY`
  - Wait state while loading snapshots or executing file mutations
- While the split terminal is visible
  - Terminal input takes precedence over browser shortcuts, and `Ctrl+T` closes the embedded terminal

## 6. What Works Today

- Launches the three-pane UI by loading the real filesystem from `CWD`
- Shows parent / current / child panes and supports cursor movement
- Moves into directories, back to parent, and reloads the current directory
- Supports filter input and continued list interaction after applying the filter
- Switches sort by name / modified time / size and toggles directories-first ordering
- Supports selection toggle, clear selection, copy / cut / paste
- Detects paste conflicts and resolves them with overwrite / skip / rename
- Renames a single target
- Creates files and directories
- Moves items to trash and shows a confirmation dialog for multi-target deletion
- Opens files with the OS default app
- Opens files in a terminal editor with `e`
- Provides recursive file search, attribute inspection, path copy, file-manager launch, terminal launch, and hidden-files toggle from the command palette
- Edits startup defaults in the config overlay and saves them back to `config.toml`
- Starts the embedded split terminal, forwards input to it, and reports when the session exits
- Keeps status bar / help bar / input bar / conflict dialog / attribute dialog / config dialog / split terminal synchronized with application state

## 7. Areas Still Unwired Or Unimplemented

- `HistoryState` exists in state, but back / forward is not wired into the UI yet
- File preview, in-app editing, Git integration, tabs, and keybinding customization are not implemented

Filesystem mutations treat the entry path selected in the UI as the trust boundary. When the selected item is a symlink, the final path component is not canonicalized, so delete / rename / move / copy / overwrite / trash operate on the symlink entry itself rather than silently following the target.

## 8. How To Extend It

When adding a new action, the intended insertion order is:

```mermaid
flowchart TD
    Key["New action"] --> Input["Add dispatch in input.py"]
    Input --> Action["Add Action in actions.py"]
    Action --> Reducer["Add state transition in reducer.py"]
    Reducer --> Effect["Add Effect if needed"]
    Effect --> Service["Add execution in services/"]
    Service --> Adapter["Delegate OS / FS differences to adapters"]
    Reducer --> Selector["Update selectors if rendering changes"]
    Selector --> UI["Keep UI display-only"]
```

Following this path keeps feature changes localized without pushing branching logic into widgets.
