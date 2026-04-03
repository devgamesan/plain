# Peneo - MVP Specification

## 1. Overview

This application is a simple file manager that runs in the terminal.
Existing full-featured TUI file managers such as yazi can have a high learning cost, so this project emphasizes:

- Low learning cost
- An interaction model closer to GUI file explorers
- A deliberately limited feature set
- A UI that minimizes hesitation

---

## 2. Scope (MVP Scope)

### 2.1 Included Features

- Browse files and directories
- Move between directories
- Multi-selection
- Copy / cut / paste
- Rename
- Delete to trash
- Create files and directories
- Filter by file name
- Switch sorting
- Copy paths
- Open files with an external app
- Launch a terminal in the current directory

### 2.2 Excluded Features

- File content preview
- File editing
- Git integration
- Archive handling
- Tabs
- Mouse interaction
- Shell command execution
- Advanced keybinding customization
- Features dedicated to network files

---

## 3. Screen Specification

### 3.1 Layout

```text
+----------------+----------------------+----------------+
| Parent Dir     | Current Dir          | Child Dir      |
+----------------+----------------------+----------------+
|                                                        |
| Status Bar                                             |
+--------------------------------------------------------+
```

---

### 3.2 Role Of Each Pane

#### Left Pane (Parent)

- Shows the contents of the parent directory

#### Center Pane (Main)

- Shows the contents of the current directory
- Main operation target

#### Right Pane (Child)

- Shows the contents of the focused item if it is a directory
- Stays empty when the focused item is a file

---

### 3.3 Displayed Fields

#### Center Pane

- Kind (file / directory)
- File name
- Size
- Modified time

#### Left And Right Panes

- File names only for a lighter display

---

### 3.4 Main Pane Summary / Status Bar

Displayed values:

- Number of items
- Number of selected items
- Current sort mode

Example:

`120 items | 3 selected | sort: modified desc`

The bottom status bar is used for notifications such as warning / error / info.

---

## 4. Interaction Specification

### 4.1 Navigation

| Input | Behavior |
|------|------|
| ↑ ↓ | Move the cursor |
| ← | Move to the parent directory |
| → | Enter a directory |
| Enter | Directory: move into it / File: open with the default app |
| e | Open a file in the editor inside the current terminal |
| Backspace | Move to the parent directory |

---

### 4.2 Selection

| Input | Behavior |
|------|------|
| Space | Toggle selection and move to the next row |
| Shift+↑ / Shift+↓ | Expand or shrink a contiguous range selection |
| Esc | Clear all selections |

#### Rules

- If one or more items are selected, operations target the selection
- Range selection covers the contiguous entries from the anchor to the current cursor
- Returning to plain ↑ / ↓ clears the active range selection
- If nothing is selected, operations target the focused item

---

### 4.3 File Operations

| Input | Behavior |
|------|------|
| Ctrl+C | Copy |
| Ctrl+X | Cut |
| Ctrl+V | Paste |
| : | Command palette |
| F2 | Rename |
| Delete | Move to trash |
| Command palette -> Create file | Create a file |
| Command palette -> Create directory | Create a directory |

---

### 4.4 Search (Filter)

| Input | Behavior |
|------|------|
| / | Start filter input |

#### Behavior

- Filter results update in real time while typing
- `Enter` confirms
- `Esc` clears the filter

---

### 4.5 Sort

The following sort modes can be switched:

- By name
- By modified time
- By size

Option:

- Directories-first on / off

---

### 4.6 Other Actions

| Input | Behavior |
|------|------|
| : | Open the command palette and run hidden-file visibility toggles |
| F5 | Reload |
| Ctrl+Shift+C | Copy path |
| Alt+Left | Back |
| Alt+Right | Forward |
| t | Launch a terminal in the current directory |

---

## 5. File Operation Rules

### 5.1 Copy / Move

- Can also run within the same directory
- Conflict behavior:
  - Overwrite
  - Skip
  - Rename
  - Selected from a dialog

---

### 5.2 Delete

- Default behavior is moving items to trash
- Failures are shown as error messages

---

### 5.3 Rename

- MVP supports a single file or directory target at a time
- Reflected immediately

---

## 6. External Integration

### 6.1 Open File

- Opens with the OS default application
- OS-specific commands:
  - Linux: `xdg-open`
  - macOS: `open`
  - Windows: `start`

---

### 6.2 Launch Terminal

- Launches a new terminal in the current directory
- Uses the appropriate command per OS

---

## 7. Performance Requirements

- Must remain operable with 1000 or more files
- Scrolling should support lazy loading
- The child pane should update only when needed

---

## 8. Error Handling

Targets:

- Insufficient permissions
- Missing files
- Copy failures
- Delete failures

Handling:

- Show them in the status bar or a popup
- The application should not exit

---

## 9. Technology Stack

### Language

- Python or TypeScript

### Recommendation

- Python + Textual

Reasons:

- Easy UI construction
- Async-friendly
- Cross-platform support

---

## 10. Future Extensions (Non-MVP)

- grep search
- Undo / Redo
- Preview support
- Tabs
- Keybinding customization
- Git integration

---

## 11. Design Guidelines

- Prioritize clarity of operation over adding more features
- Keep state transitions as small in number as possible
- Minimize modal UI
- The top priority is preventing user confusion

---

## 12. Implementation Direction (Summary)

### 12.1 Architectural Direction

- Separate UI from logic
- Manage state in a single structure
- Treat operations as Actions
- Centralize state updates in one place
- Separate file operations as side effects

Basic flow:

User input -> state update -> UI rerender -> side effect execution

---

### 12.2 UI Composition Direction

- Use Textual
- Base layout is three panes plus a status bar
- Keep the UI focused on presentation without embedding logic

---

### 12.3 State Management Direction

Manage everything under a single state object (`AppState`).

Main elements:

- Current path
- File list
- Cursor position
- Selection state
- Sort and filter conditions
- Clipboard state
- UI mode

---

### 12.4 UI Mode Handling

Switch input behavior between these modes:

- Normal browsing (`BROWSING`)
- Input modes (`FILTER` / `RENAME` / `CREATE`)
- Confirmation dialog (`CONFIRM`)
- Busy state (`BUSY`)

---

### 12.5 Side-Effect Policy

Keep the following separate from pure state updates:

- File operations
- Directory loading
- External app launch
- Terminal launch

Results are fed back into state afterward.

---

### 12.6 Async Processing

Run the following asynchronously:

- Directory loading
- File operations

Goal:

- Prevent UI freezes

---

### 12.7 Data Handling

- Separate source data from display data
- Track selection by path

---

### 12.8 OS-Dependent Processing

Keep these behind dedicated processing layers:

- File operations
- Trash handling
- App launch
- Terminal launch

---

### 12.9 Implementation Priority

1. Build the screen
2. Show directories
3. Navigation and selection
4. File operations
5. Search
6. Sort

---

### 12.10 Principles

- Centralized state
- Display-only UI
- Separated side effects
- Simplicity first

---
