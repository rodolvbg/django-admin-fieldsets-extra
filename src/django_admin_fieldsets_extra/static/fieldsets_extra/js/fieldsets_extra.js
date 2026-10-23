/*
 * django-admin-fieldsets-extra
 *
 * The "Save <fieldset>" buttons: post only that fieldset's fields and swap
 * in the re-rendered fieldset. The fieldsets that save themselves
 * (autosave): the same, as their fields change — a checkbox or a select at
 * once, a text when it's left or on Enter. Plain script, no dependencies;
 * uses django.jQuery (when present) only to re-run the admin's widget setup.
 */
(() => {
    const SKIP_TYPES = ["submit", "button", "reset", "image"];

    /** The admin form's values for the controls inside `container`. */
    function fieldsetFormData(container, form) {
        const data = new FormData();
        const csrf = form.querySelector("[name=csrfmiddlewaretoken]");
        if (csrf) {
            data.append(csrf.name, csrf.value);
        }
        for (const el of container.querySelectorAll(
            "input, select, textarea",
        )) {
            if (
                !el.name ||
                el.disabled ||
                el.form !== form ||
                SKIP_TYPES.includes(el.type)
            ) {
                continue;
            }
            if (
                (el.type === "checkbox" || el.type === "radio") &&
                !el.checked
            ) {
                continue;
            }
            if (el.type === "file") {
                for (const file of el.files) {
                    data.append(el.name, file);
                }
            } else if (el.tagName === "SELECT" && el.multiple) {
                for (const option of el.selectedOptions) {
                    data.append(el.name, option.value);
                }
            } else {
                data.append(el.name, el.value);
            }
        }
        return data;
    }

    /** Re-run the admin's widget setup on freshly inserted HTML. */
    function initWidgets(container) {
        const $ = window.django?.jQuery;
        if ($?.fn.djangoAdminSelect2) {
            $(container).find(".admin-autocomplete").djangoAdminSelect2();
        }
        if ($ && typeof window.DateTimeShortcuts !== "undefined") {
            $(".datetimeshortcuts").remove();
            window.DateTimeShortcuts.init();
        }
        if (typeof window.SelectFilter !== "undefined") {
            for (const el of container.querySelectorAll(
                ".selectfilter, .selectfilterstacked",
            )) {
                window.SelectFilter.init(
                    el.id,
                    el.dataset.fieldName,
                    el.classList.contains("selectfilterstacked"),
                );
            }
        }
        if ($) {
            $(container)
                .find(".related-widget-wrapper select")
                .trigger("change");
        }
        container.dispatchEvent(
            new CustomEvent("fieldsets-extra:saved", { bubbles: true }),
        );
    }

    function showFailure(container) {
        const status = container.querySelector(".fieldset-save-status");
        if (status) {
            status.className =
                "fieldset-save-status fieldset-save-status-failed";
            status.textContent = container.dataset.fieldsetSaveFailed ?? "";
        }
    }

    /** The fieldset `container` as the server answered it. */
    async function fetchFieldset(container, body) {
        const response = await fetch(container.dataset.fieldsetSaveUrl, {
            method: "POST",
            body,
            credentials: "same-origin",
            headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        // 409: someone else changed it; the answer is what's saved now.
        if (!response.ok && response.status !== 409) {
            throw new Error(`HTTP ${response.status}`);
        }
        const text = await response.text();
        const doc = new DOMParser().parseFromString(text, "text/html");
        const fresh = doc.getElementById(container.id);
        if (!fresh) {
            throw new Error("Fieldset not found in response");
        }
        return fresh;
    }

    /** Put the re-rendered fieldset in place of `container`, keeping it
     * open or closed, and the focus where it was. */
    function swap(container, fresh) {
        const node = document.importNode(fresh, true);
        const details = container.querySelector("details");
        const freshDetails = node.querySelector("details");
        if (details && freshDetails) {
            freshDetails.open = details.open;
        }
        const active = document.activeElement;
        const focused =
            active && container.contains(active) && active.name
                ? {
                      name: active.name,
                      start: active.selectionStart,
                      end: active.selectionEnd,
                  }
                : null;
        container.replaceWith(node);
        initWidgets(node);
        if (focused) {
            const again = [...node.querySelectorAll("[name]")].find(
                (el) => el.name === focused.name,
            );
            again?.focus();
            if (typeof focused.start === "number" && again?.setSelectionRange) {
                again.setSelectionRange(focused.start, focused.end);
            }
        }
        return node;
    }

    async function saveFieldset(container) {
        const form = container.closest("form");
        if (!form || container.classList.contains("fieldset-save-loading")) {
            return;
        }
        container.classList.add("fieldset-save-loading");
        try {
            const fresh = await fetchFieldset(
                container,
                fieldsetFormData(container, form),
            );
            swap(container, fresh);
        } catch {
            container.classList.remove("fieldset-save-loading");
            showFailure(container);
        }
    }

    // Autosave ---------------------------------------------------------------

    const SAVED_FOR = 2000;
    /** container id → { saved, busy, again, timer } */
    const autosaved = new Map();

    /** What a fieldset sends, without the token and the files (they're
     * sent, not compared). */
    function values(container, form) {
        return [...fieldsetFormData(container, form)].filter(
            ([name, value]) =>
                name !== "csrfmiddlewaretoken" && typeof value === "string",
        );
    }

    const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

    function track(container) {
        const form = container.closest("form");
        if (!form) return null;
        if (!autosaved.has(container.id)) {
            autosaved.set(container.id, {
                saved: values(container, form),
                busy: false,
                again: false,
                timer: null,
            });
        }
        return autosaved.get(container.id);
    }

    function status(container, state, text) {
        const node = container.querySelector(".fieldset-save-status");
        if (!node) return;
        node.className = `fieldset-save-status fieldset-save-status-${state}`;
        node.textContent = text;
    }

    async function autosave(container, force = false) {
        const form = container.closest("form");
        const entry = track(container);
        if (!entry) return;
        if (entry.busy) {
            entry.again = true;
            return;
        }
        const current = values(container, form);
        if (!force && same(current, entry.saved)) return;
        entry.busy = true;
        clearTimeout(entry.timer);
        status(container, "saving", container.dataset.fieldsetSaving ?? "");
        const body = fieldsetFormData(container, form);
        body.append("check", "1");
        for (const [name, value] of entry.saved) {
            body.append(`previous-${name}`, value);
        }
        let node = container;
        try {
            const fresh = await fetchFieldset(container, body);
            const answer = fresh.querySelector(".fieldset-save-status");
            const saved = answer?.classList.contains(
                "fieldset-save-status-saved",
            );
            if (
                saved &&
                (entry.again || container.contains(document.activeElement))
            ) {
                // Still being edited, or changed again meanwhile (its newer
                // values go next): only what it says.
                entry.saved = current;
                status(container, "saved", answer.textContent);
            } else {
                node = swap(container, fresh);
                // What's there now: saved, or the server's (a conflict).
                if (
                    saved ||
                    answer?.classList.contains("fieldset-save-status-conflict")
                ) {
                    entry.saved = values(node, form);
                }
            }
            if (saved) {
                entry.timer = setTimeout(() => {
                    const shown = document.getElementById(container.id);
                    if (shown) status(shown, "saved", "");
                }, SAVED_FOR);
            }
        } catch {
            showFailure(container);
        } finally {
            entry.busy = false;
        }
        if (entry.again) {
            entry.again = false;
            autosave(node.isConnected ? node : container);
        }
    }

    function autosaving(target) {
        const container = target.closest?.(".fieldset-autosave");
        return container && target.form === container.closest("form")
            ? container
            : null;
    }

    // What the fieldsets had before anything changed: when the page is
    // ready, and (for those that come later) when a field is entered.
    function trackAll() {
        for (const container of document.querySelectorAll(
            ".fieldset-autosave",
        )) {
            track(container);
        }
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", trackAll);
    } else {
        trackAll();
    }
    document.addEventListener("focusin", (event) => {
        const container = autosaving(event.target);
        if (container) track(container);
    });

    document.addEventListener("change", (event) => {
        const container = autosaving(event.target);
        if (container) autosave(container, event.target.type === "file");
    });

    // Enter saves a text that saves itself, instead of the whole form.
    document.addEventListener("keydown", (event) => {
        const container = autosaving(event.target);
        if (
            !container ||
            event.key !== "Enter" ||
            event.target.tagName !== "INPUT" ||
            SKIP_TYPES.includes(event.target.type)
        ) {
            return;
        }
        event.preventDefault();
        autosave(container);
    });

    document.addEventListener("click", (event) => {
        const button = event.target.closest("[data-fieldset-save]");
        const container = button?.closest(".fieldset-with-save");
        if (container) {
            event.preventDefault();
            saveFieldset(container);
        }
    });

    globalThis.DjangoAdminFieldsetsExtra = {
        autosave,
        fieldsetFormData,
        saveFieldset,
    };
})();
