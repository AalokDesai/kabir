# Phase 6 UI/UX Enhancements Walkthrough

## Already Implemented and Skipped

- Settings panel with local persistence through `engine/settings.json`.
- Notification Center with unread badge, manual alerts, backend-pushed alerts, and local browser storage.
- Backend health monitor with an offline/retry banner and reconnect refresh.
- Log viewer panel for recent `logs/kabir.log` entries.
- Light/dark theme support through the settings form.

## Added in This Pass

### Smart Command Suggestions

The chat input now shows command suggestions while typing. Suggestions are loaded from the existing backend skill registry through `get_skill_suggestions()` and merged with a fallback list of common commands.

How to use it:

1. Open the Chat panel.
2. Click the command input.
3. Start typing, for example `wea`, `send`, `open`, or `play`.
4. Click a suggestion to send it immediately.
5. Use `ArrowUp` and `ArrowDown` to move through suggestions.
6. Press `Tab` to fill the selected suggestion.
7. Press `Enter` on a selected suggestion to send it.
8. Press `Escape` to close suggestions.

Files changed:

- `www/index.html`: wrapped the chat input and added the suggestion dropdown container.
- `www/controller.js`: added suggestion loading, filtering, keyboard handling, click handling, and send integration.
- `www/style.css`: added dropdown styling, light-theme support, and responsive layout rules.

### Responsive Layout Polish

The UI now adapts better on narrower screens:

1. Below `1180px`, the right telemetry rail is hidden, wide panels collapse to one column, and command/history grids reduce their column count.
2. Below `780px`, the app stacks vertically, sidebar navigation becomes a compact grid, and form/search/notification grids collapse to one column.
3. Chat bubbles and suggestion dropdowns get safer widths and heights so they remain readable.

## Verification Checklist

1. Launch Kabir and authenticate into the main UI.
2. In Chat, focus the input and type `weather`.
3. Confirm suggestions appear above the input.
4. Press `ArrowDown`, then `Tab`; the selected suggestion should fill the input.
5. Press `Enter`; the command should send normally.
6. Switch to Settings, change theme to Light, save, and confirm the suggestion dropdown still has readable contrast.
7. Resize the window below tablet width and confirm panels do not overlap.
