import { beforeAll, describe, expect, it } from "vitest";

let api;

beforeAll(async () => {
    await import(
        "../../src/django_admin_fieldsets_with_inlines/static/fieldsets_with_inlines/js/fieldsets_with_inlines.js"
    );
    api = globalThis.DjangoAdminFieldsetsWithInlines;
});

describe("fieldsetFormData", () => {
    it("collects only the fieldset's submittable fields", () => {
        document.body.innerHTML = `
            <form id="author_form">
              <input name="csrfmiddlewaretoken" value="tok">
              <input name="name" value="Outside">
              <div class="fieldset-with-save" id="fieldset-1-container">
                <fieldset>
                  <input name="email" value="a@example.com">
                  <input type="checkbox" name="active" checked>
                  <input type="checkbox" name="off">
                  <select name="tags" multiple>
                    <option value="1" selected></option><option value="2" selected></option>
                  </select>
                  <textarea name="bio">b</textarea>
                  <input name="disabled" value="x" disabled>
                  <input name="elsewhere" form="another-form" value="y">
                </fieldset>
                <button type="button" name="save" data-fieldset-save>Save</button>
              </div>
            </form>`;
        const data = api.fieldsetFormData(
            document.getElementById("fieldset-1-container"),
            document.getElementById("author_form"),
        );

        expect([...data.entries()]).toEqual([
            ["csrfmiddlewaretoken", "tok"],
            ["email", "a@example.com"],
            ["active", "on"],
            ["tags", "1"],
            ["tags", "2"],
            ["bio", "b"],
        ]);
    });
});
