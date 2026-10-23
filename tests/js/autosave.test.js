import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

let api;

beforeAll(async () => {
    await import(
        "../../src/django_admin_fieldsets_extra/static/fieldsets_extra/js/fieldsets_extra.js"
    );
    api = globalThis.DjangoAdminFieldsetsExtra;
});

let ids = 0;

/** A change form with a fieldset that saves itself; its id unique per
 * test (what the script remembers is by id). */
function page({ notes = "First", active = true } = {}) {
    ids += 1;
    const id = `fieldset-${ids}-container`;
    document.body.innerHTML = `
        <form id="author_form">
          <input name="csrfmiddlewaretoken" value="tok">
          <input name="name" value="Outside">
          ${container(id, { notes, active })}
        </form>`;
    return id;
}

function container(id, { notes, active, state = "", text = "" }) {
    return `<div class="fieldset-with-save fieldset-autosave" id="${id}"
                 data-fieldset-save-url="/save/" data-fieldset-autosave
                 data-fieldset-saving="Saving…"
                 data-fieldset-save-failed="Not saved.">
              <fieldset><details open><summary>Status</summary>
                <input type="checkbox" name="active"${active ? " checked" : ""}>
                <input name="notes" value="${notes}">
                <textarea name="bio"></textarea>
                <input type="file" name="photo">
              </details></fieldset>
              <div class="fieldset-save-bar">
                <span class="fieldset-save-status${state ? ` fieldset-save-status-${state}` : ""}">${text}</span>
              </div>
            </div>`;
}

function answer(
    id,
    values,
    { state = "saved", text = "Saved", status = 200 } = {},
) {
    return {
        ok: status < 400,
        status,
        text: async () => container(id, { ...values, state, text }),
    };
}

const el = (name) => document.querySelector(`[name="${name}"]`);
const statusOf = (id) =>
    document.getElementById(id).querySelector(".fieldset-save-status");
const flush = async () => {
    for (let i = 0; i < 5; i += 1) await new Promise((r) => setTimeout(r, 0));
};

function edit(name, value) {
    const input = el(name);
    input.dispatchEvent(new FocusEvent("focusin", { bubbles: true }));
    if (input.type === "checkbox") input.checked = value;
    else input.value = value;
    input.dispatchEvent(new Event("change", { bubbles: true }));
}

const sent = (fetch, call = 0) => [...fetch.mock.calls[call][1].body.entries()];

afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
});

describe("autosave", () => {
    it("saves the fieldset as a field changes, with what it was", async () => {
        const id = page();
        const fetch = vi.fn(async () =>
            answer(id, { notes: "Second", active: true }),
        );
        vi.stubGlobal("fetch", fetch);
        edit("notes", "Second");
        expect(statusOf(id).textContent).toBe("Saving…");
        expect(statusOf(id).className).toBe(
            "fieldset-save-status fieldset-save-status-saving",
        );
        await flush();
        expect(fetch.mock.calls[0][0]).toBe("/save/");
        expect(sent(fetch)).toEqual([
            ["csrfmiddlewaretoken", "tok"],
            ["active", "on"],
            ["notes", "Second"],
            ["bio", ""],
            ["check", "1"],
            ["previous-active", "on"],
            ["previous-notes", "First"],
            ["previous-bio", ""],
        ]);
        // Not being edited any more: re-rendered, saying so.
        expect(statusOf(id).textContent).toBe("Saved");
        expect(statusOf(id).classList).toContain("fieldset-save-status-saved");
    });

    it("keeps the fieldset being edited, and its focus", async () => {
        const id = page();
        vi.stubGlobal(
            "fetch",
            vi.fn(async () => answer(id, { notes: "Second", active: true })),
        );
        const notes = el("notes");
        notes.focus();
        edit("notes", "Second");
        await flush();
        expect(el("notes")).toBe(notes); // Not replaced.
        expect(document.activeElement).toBe(notes);
        expect(statusOf(id).textContent).toBe("Saved");
    });

    it("says it's saved for a moment", async () => {
        vi.useFakeTimers();
        const id = page();
        vi.stubGlobal(
            "fetch",
            vi.fn(async () => answer(id, { notes: "Second", active: true })),
        );
        edit("notes", "Second");
        await vi.advanceTimersByTimeAsync(0);
        expect(statusOf(id).textContent).toBe("Saved");
        await vi.advanceTimersByTimeAsync(2000);
        expect(statusOf(id).textContent).toBe("");
        // Gone meanwhile: nothing to clear.
        edit("notes", "Third");
        await vi.advanceTimersByTimeAsync(0);
        document.body.innerHTML = "";
        await vi.advanceTimersByTimeAsync(2000);
    });

    it("shows the errors, keeping what was written and the focus", async () => {
        const id = page();
        vi.stubGlobal(
            "fetch",
            vi.fn(async () =>
                answer(
                    id,
                    { notes: "Too long", active: true },
                    {
                        state: "invalid",
                        text: "Please correct the errors below.",
                    },
                ),
            ),
        );
        const notes = el("notes");
        notes.focus();
        notes.value = "Too long";
        notes.setSelectionRange(1, 3);
        notes.dispatchEvent(new Event("change", { bubbles: true }));
        await flush();
        expect(el("notes")).not.toBe(notes); // Re-rendered, with its errors.
        expect(document.activeElement).toBe(el("notes"));
        expect(el("notes").selectionStart).toBe(1);
        expect(statusOf(id).classList).toContain(
            "fieldset-save-status-invalid",
        );
    });

    it("shows what someone else saved meanwhile", async () => {
        const id = page();
        const fetch = vi.fn(async () =>
            answer(
                id,
                { notes: "Theirs", active: true },
                {
                    state: "conflict",
                    text: "Someone else changed it.",
                    status: 409,
                },
            ),
        );
        vi.stubGlobal("fetch", fetch);
        edit("notes", "Mine");
        await flush();
        expect(el("notes").value).toBe("Theirs");
        expect(statusOf(id).textContent).toBe("Someone else changed it.");
        // What's there now is what it starts from next.
        edit("notes", "Again");
        await flush();
        expect(sent(fetch, 1)).toContainEqual(["previous-notes", "Theirs"]);
    });

    it("says when it couldn't save", async () => {
        const id = page();
        vi.stubGlobal(
            "fetch",
            vi.fn(async () => ({ ok: false, status: 500 })),
        );
        edit("active", false);
        await flush();
        expect(statusOf(id).textContent).toBe("Not saved.");
        expect(statusOf(id).classList).toContain("fieldset-save-status-failed");
    });

    it("sends what changed meanwhile after the request under way", async () => {
        const id = page();
        let finish;
        const fetch = vi.fn(
            () =>
                new Promise((resolve) => {
                    finish = () =>
                        resolve(answer(id, { notes: "C", active: true }));
                }),
        );
        vi.stubGlobal("fetch", fetch);
        edit("notes", "A");
        edit("notes", "B");
        edit("notes", "C");
        expect(fetch).toHaveBeenCalledTimes(1);
        finish();
        await flush();
        expect(fetch).toHaveBeenCalledTimes(2);
        expect(sent(fetch, 1)).toContainEqual(["notes", "C"]);
        finish();
        await flush();
        // Nothing new since: nothing sent; a file always is.
        el("notes").dispatchEvent(new Event("change", { bubbles: true }));
        expect(fetch).toHaveBeenCalledTimes(2);
        el("photo").dispatchEvent(new Event("change", { bubbles: true }));
        expect(fetch).toHaveBeenCalledTimes(3);
    });

    it("saves a text on Enter, instead of the whole form", async () => {
        const id = page();
        const fetch = vi.fn(async () =>
            answer(id, { notes: "X", active: true }),
        );
        vi.stubGlobal("fetch", fetch);
        el("notes").dispatchEvent(new FocusEvent("focusin", { bubbles: true }));
        el("notes").value = "X";
        const enter = new KeyboardEvent("keydown", {
            key: "Enter",
            bubbles: true,
            cancelable: true,
        });
        el("notes").dispatchEvent(enter);
        expect(enter.defaultPrevented).toBe(true);
        await flush();
        expect(fetch).toHaveBeenCalledOnce();
        for (const [name, key] of [
            ["bio", "Enter"], // a new line
            ["notes", "a"],
            ["name", "Enter"], // not of a fieldset that saves itself
        ]) {
            const event = new KeyboardEvent("keydown", {
                key,
                bubbles: true,
                cancelable: true,
            });
            el(name).dispatchEvent(event);
            expect(event.defaultPrevented).toBe(false);
        }
        const checkbox = new KeyboardEvent("keydown", {
            key: "Enter",
            bubbles: true,
            cancelable: true,
        });
        el("active").dispatchEvent(checkbox);
        expect(checkbox.defaultPrevented).toBe(true);
    });

    it("leaves alone what isn't of its form", async () => {
        page();
        const fetch = vi.fn();
        vi.stubGlobal("fetch", fetch);
        const other = document.createElement("input");
        other.name = "elsewhere";
        other.setAttribute("form", "another");
        document.querySelector("fieldset").append(other);
        other.dispatchEvent(new Event("change", { bubbles: true }));
        document.dispatchEvent(new Event("change"));
        await api.autosave(document.createElement("div"));
        expect(fetch).not.toHaveBeenCalled();
    });
});
