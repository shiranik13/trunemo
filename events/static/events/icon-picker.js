for (const picker of document.querySelectorAll("[data-icon-picker]")) {
    const options = Array.from(picker.querySelectorAll("[data-icon-option]"));
    const toggle = picker.querySelector("[data-icon-toggle]");
    const suggestions = options.filter((option) => option.querySelector("input").value);
    let columnCount = 0;
    for (let index = suggestions.length - 1; index > 0; index -= 1) {
        const other = Math.floor(Math.random() * (index + 1));
        [suggestions[index], suggestions[other]] = [suggestions[other], suggestions[index]];
    }

    function showOptions(expanded) {
        const selected = suggestions.find((option) => option.querySelector("input").checked);
        const preview = [...new Set([selected, ...suggestions].filter(Boolean))].slice(0, columnCount);
        for (const option of suggestions) option.hidden = !expanded && !preview.includes(option);
        toggle.hidden = suggestions.length <= columnCount;
        toggle.setAttribute("aria-expanded", String(expanded));
        toggle.setAttribute("aria-label", expanded ? toggle.dataset.less : toggle.dataset.more);
    }

    function updateColumns() {
        const columns = getComputedStyle(picker).gridTemplateColumns.split(" ").length;
        if (columns === columnCount) return;
        columnCount = columns;
        showOptions(toggle.getAttribute("aria-expanded") === "true");
    }

    updateColumns();
    new ResizeObserver(updateColumns).observe(picker);
    toggle.addEventListener("click", () => showOptions(toggle.getAttribute("aria-expanded") === "false"));
}
