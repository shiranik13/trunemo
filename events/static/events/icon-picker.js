for (const picker of document.querySelectorAll("[data-icon-picker]")) {
    const options = Array.from(picker.querySelectorAll("[data-icon-option]"));
    const toggle = picker.querySelector("[data-icon-toggle]");
    const previewCount = 3;
    const suggestions = options.filter((option) => option.querySelector("input").value);
    for (let index = suggestions.length - 1; index > 0; index -= 1) {
        const other = Math.floor(Math.random() * (index + 1));
        [suggestions[index], suggestions[other]] = [suggestions[other], suggestions[index]];
    }

    function showOptions(expanded) {
        const selected = options.find((option) => option.querySelector("input").checked);
        const preview = [...new Set([options[0], selected, ...suggestions].filter(Boolean))].slice(0, previewCount);
        for (const option of options) option.hidden = !expanded && !preview.includes(option);
        toggle.setAttribute("aria-expanded", String(expanded));
        toggle.setAttribute("aria-label", expanded ? toggle.dataset.less : toggle.dataset.more);
    }

    if (options.length > previewCount) {
        toggle.hidden = false;
        showOptions(false);
        toggle.addEventListener("click", () => showOptions(toggle.getAttribute("aria-expanded") === "false"));
    }
}
