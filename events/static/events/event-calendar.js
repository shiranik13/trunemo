const eventDateInput = document.querySelector("[data-event-calendar]");
if (eventDateInput && window.flatpickr) {
    const language = document.documentElement.lang.split("-")[0];
    flatpickr(eventDateInput, {
        locale: flatpickr.l10ns[language] || "default",
        dateFormat: eventDateInput.dataset.eventCalendar,
        allowInput: true,
        disableMobile: true,
    });
}
