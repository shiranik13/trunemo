const setup = document.querySelector("#group-setup");
const rows = setup.querySelector("[data-guest-rows]");
const template = setup.querySelector("[data-guest-template]");
const total = setup.elements["guests-TOTAL_FORMS"];
const add = setup.querySelector("[data-add-row]");
const next = setup.querySelector("[data-payment-next]");
const back = setup.querySelector("[data-payment-back]");
const save = setup.querySelector("[data-group-save]");
const saveWithoutPayments = setup.querySelector("[data-save-without-payments]");
const payerSelector = '[data-guest-details] input[type="checkbox"]';

function updatePaymentRows(row, payments = true) {
    const selected = payments && row.querySelector(payerSelector).checked;
    for (const field of row.querySelectorAll("[data-guest-payment] input, [data-guest-payment] select")) {
        field.disabled = !selected;
    }
    const extras = Array.from(row.querySelectorAll("[data-extra-payment]"));
    row.querySelector("[data-add-payment]").hidden = extras.every((extra) => !extra.hidden);
    for (const extra of extras) {
        for (const field of extra.querySelectorAll("input, select")) field.disabled = !selected || extra.hidden;
    }
}

for (const row of rows.children) updatePaymentRows(row);

rows.addEventListener("click", (event) => {
    const button = event.target.closest("[data-add-payment]");
    if (!button) return;
    const row = button.closest("[data-guest-row]");
    const extra = row.querySelector("[data-extra-payment][hidden]");
    if (!extra) return;
    extra.hidden = false;
    updatePaymentRows(row);
    extra.querySelector("input").focus();
});

function updateCoveredGuests() {
    const guestRows = Array.from(rows.children);
    const payers = guestRows.filter((row) => row.querySelector(payerSelector).checked);
    for (const row of guestRows) {
        const field = row.querySelector("[data-covered]");
        const options = field.querySelector("[data-covered-options]");
        const checked = new Set(Array.from(options.querySelectorAll(":checked"), (input) => input.value));
        field.hidden = payers.length < 2;
        options.replaceChildren();
        if (field.hidden) continue;
        guestRows.forEach((guest, index) => {
            const name = guest.querySelector('input[type="text"]').value.trim();
            if (!name) return;
            const input = document.createElement("input");
            input.type = "checkbox";
            input.name = field.dataset.fieldName;
            input.value = index;
            input.checked = checked.has(String(index));
            const label = document.createElement("label");
            label.append(input, " ", name);
            options.append(label);
        });
    }
}

function showStep(payments) {
    setup.querySelector("[data-group-details]").hidden = payments;
    setup.querySelector("[data-group-notes]").hidden = payments;
    setup.querySelector("[data-payment-heading]").hidden = !payments;
    for (const row of rows.children) {
        const selected = row.querySelector(payerSelector).checked;
        row.hidden = payments && !selected;
        row.querySelector("[data-guest-details]").hidden = payments;
        row.querySelector("[data-guest-payment]").hidden = !payments;
        row.querySelector("[data-payer-name]").textContent = row.querySelector('input[type="text"]').value;
        updatePaymentRows(row, payments);
    }
    add.hidden = payments || Number(total.value) >= 100;
    next.hidden = payments || !rows.querySelector(payerSelector + ":checked");
    back.hidden = !payments;
    save.hidden = !payments;
    saveWithoutPayments.hidden = payments;
    save.disabled = !payments;
    saveWithoutPayments.disabled = payments;
}

if (setup.hasAttribute("data-submitted")) {
    for (const row of rows.children) {
        row.querySelector("[data-guest-payment]").hidden = !row.querySelector(payerSelector).checked;
    }
} else {
    showStep(false);
}
rows.addEventListener("change", (event) => {
    if (event.target.matches(payerSelector)) showStep(false);
});

add.hidden = Number(total.value) >= 100;
add.addEventListener("click", () => {
    const index = Number(total.value);
    if (index >= 100) return;
    rows.insertAdjacentHTML("beforeend", template.innerHTML.replaceAll("__prefix__", index));
    total.value = index + 1;
    updatePaymentRows(rows.lastElementChild);
    showStep(false);
    rows.lastElementChild.querySelector('input[type="text"]').focus();
});

next.addEventListener("click", () => {
    for (const field of setup.querySelectorAll("[data-group-details] input, [data-guest-details] input")) {
        if (!field.reportValidity()) return;
    }
    for (const row of rows.children) {
        const name = row.querySelector('input[type="text"]');
        if (row.querySelector(payerSelector).checked && !name.value.trim()) {
            name.required = true;
            name.reportValidity();
            name.required = false;
            return;
        }
    }
    updateCoveredGuests();
    showStep(true);
    rows.querySelector("[data-guest-row]:not([hidden]) input[type='number']").focus();
});
back.addEventListener("click", () => showStep(false));
