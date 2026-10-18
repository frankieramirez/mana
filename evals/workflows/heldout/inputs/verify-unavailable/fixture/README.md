# Filter panel shortcuts

`ui/panel.html` hosts the filter panel and `ui/shortcuts.js` wires its keyboard shortcuts.

`bash checks/interaction.sh` is the only check that exercises key handling. It drives the page in the `chromium-fixture` headless browser using the steps in `checks/shift-k.json`.
