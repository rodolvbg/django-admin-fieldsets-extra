/*
 * django-admin-fieldsets-extra
 *
 * The "Save <fieldset>" buttons: post only that fieldset's fields and swap
 * in the re-rendered fieldset. Plain script, no dependencies; uses
 * django.jQuery (when present) only to re-run the admin's widget setup.
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

    async function saveFieldset(container) {
        const form = container.closest("form");
        if (!form || container.classList.contains("fieldset-save-loading")) {
            return;
        }
        container.classList.add("fieldset-save-loading");
        try {
            const response = await fetch(container.dataset.fieldsetSaveUrl, {
                method: "POST",
                body: fieldsetFormData(container, form),
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const text = await response.text();
            const doc = new DOMParser().parseFromString(text, "text/html");
            const fresh = doc.getElementById(container.id);
            if (!fresh) {
                throw new Error("Fieldset not found in response");
            }
            const node = document.importNode(fresh, true);
            // Keep a collapsible fieldset open or closed as it was.
            const details = container.querySelector("details");
            const freshDetails = node.querySelector("details");
            if (details && freshDetails) {
                freshDetails.open = details.open;
            }
            container.replaceWith(node);
            initWidgets(node);
        } catch {
            container.classList.remove("fieldset-save-loading");
            showFailure(container);
        }
    }

    document.addEventListener("click", (event) => {
        const button = event.target.closest("[data-fieldset-save]");
        const container = button?.closest(".fieldset-with-save");
        if (container) {
            event.preventDefault();
            saveFieldset(container);
        }
    });

    globalThis.DjangoAdminFieldsetsExtra = {
        fieldsetFormData,
        saveFieldset,
    };
})();
