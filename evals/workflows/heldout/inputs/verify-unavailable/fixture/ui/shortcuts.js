export function isTextField(target) {
  return Boolean(target) && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
}

export function handleKey(event, panel) {
  if (isTextField(event.target)) {
    return false;
  }
  if (event.shiftKey && event.key === "K") {
    const collapsed = panel.dataset.collapsed === "true";
    panel.dataset.collapsed = collapsed ? "false" : "true";
    return true;
  }
  return false;
}

export function installShortcuts(doc, panel) {
  doc.addEventListener("keydown", (event) => {
    if (handleKey(event, panel)) {
      event.preventDefault();
    }
  });
}
