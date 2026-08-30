from pathlib import Path
from datetime import datetime
import json
import sys

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError
)


# ============================================================
# CONFIGURATION
# ============================================================

CDP_URL = "http://127.0.0.1:9222"

EXPECTED_HOST = "zeusx.com"

OUTPUT_DIR = (
    Path(__file__).resolve().parent
    / "logs"
    / "dom"
)


# ============================================================
# OUTPUT
# ============================================================

def create_output_dir():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


def save_text(filename, content):
    path = OUTPUT_DIR / filename

    path.write_text(
        content,
        encoding="utf-8"
    )

    print(f"[SAVED] {path}")


def save_json(filename, data):
    path = OUTPUT_DIR / filename

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(f"[SAVED] {path}")


# ============================================================
# INTERACTIVE ELEMENT INSPECTION
# ============================================================

def get_interactive_elements(page):

    script = """
    () => {

        const selectors = [
            'input',
            'textarea',
            'select',
            'button',
            '[role="button"]',
            '[role="combobox"]',
            '[role="listbox"]',
            '[role="option"]',
            '[role="checkbox"]',
            '[role="radio"]',
            '[contenteditable="true"]',
            '[tabindex]'
        ];

        const elements = document.querySelectorAll(
            selectors.join(',')
        );

        return Array.from(elements).map(
            (el, index) => {

                const rect =
                    el.getBoundingClientRect();

                const style =
                    window.getComputedStyle(el);

                return {

                    index: index,

                    tag: el.tagName,

                    type:
                        el.getAttribute('type'),

                    role:
                        el.getAttribute('role'),

                    id:
                        el.id || null,

                    name:
                        el.getAttribute('name'),

                    class:
                        typeof el.className === 'string'
                            ? el.className
                            : null,

                    placeholder:
                        el.getAttribute('placeholder'),

                    ariaLabel:
                        el.getAttribute('aria-label'),

                    ariaLabelledby:
                        el.getAttribute(
                            'aria-labelledby'
                        ),

                    title:
                        el.getAttribute('title'),

                    autocomplete:
                        el.getAttribute(
                            'autocomplete'
                        ),

                    value:
                        'value' in el
                            ? el.value
                            : null,

                    text:
                        (
                            el.innerText ||
                            el.textContent ||
                            ''
                        ).trim(),

                    checked:
                        'checked' in el
                            ? el.checked
                            : null,

                    selected:
                        'selected' in el
                            ? el.selected
                            : null,

                    disabled:
                        'disabled' in el
                            ? el.disabled
                            : false,

                    readonly:
                        'readOnly' in el
                            ? el.readOnly
                            : false,

                    visible:
                        (
                            rect.width > 0 &&
                            rect.height > 0 &&
                            style.visibility !== 'hidden' &&
                            style.display !== 'none'
                        ),

                    rect: {
                        x: rect.x,
                        y: rect.y,
                        width: rect.width,
                        height: rect.height
                    }
                };
            }
        );
    }
    """

    return page.evaluate(script)


# ============================================================
# FORM ELEMENT INSPECTION
# ============================================================

def get_forms(page):

    script = """
    () => {

        return Array.from(
            document.querySelectorAll('form')
        ).map((form, index) => {

            return {
                index: index,

                id:
                    form.id || null,

                name:
                    form.getAttribute('name'),

                action:
                    form.getAttribute('action'),

                method:
                    form.getAttribute('method'),

                ariaLabel:
                    form.getAttribute('aria-label'),

                text:
                    (
                        form.innerText ||
                        form.textContent ||
                        ''
                    ).trim()
            };
        });
    }
    """

    return page.evaluate(script)


# ============================================================
# BUTTON INSPECTION
# ============================================================

def get_buttons(page):

    script = """
    () => {

        return Array.from(
            document.querySelectorAll(
                'button, [role="button"]'
            )
        ).map((button, index) => {

            const rect =
                button.getBoundingClientRect();

            const style =
                window.getComputedStyle(button);

            return {

                index: index,

                tag:
                    button.tagName,

                type:
                    button.getAttribute('type'),

                role:
                    button.getAttribute('role'),

                id:
                    button.id || null,

                name:
                    button.getAttribute('name'),

                ariaLabel:
                    button.getAttribute(
                        'aria-label'
                    ),

                text:
                    (
                        button.innerText ||
                        button.textContent ||
                        ''
                    ).trim(),

                disabled:
                    button.disabled || false,

                visible:
                    (
                        rect.width > 0 &&
                        rect.height > 0 &&
                        style.visibility !== 'hidden' &&
                        style.display !== 'none'
                    )
            };
        });
    }
    """

    return page.evaluate(script)


# ============================================================
# PAGE INFORMATION
# ============================================================

def get_page_information(page):

    return {
        "url": page.url,
        "title": page.title(),
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    create_output_dir()

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    print("=" * 70)
    print("ZEUSX DOM INSPECTOR - CDP")
    print("=" * 70)
    print()

    print(f"Connecting to: {CDP_URL}")
    print()

    with sync_playwright() as p:

        try:

            browser = p.chromium.connect_over_cdp(
                CDP_URL
            )

        except Exception as e:

            print()
            print("=" * 70)
            print("FAILED TO CONNECT TO CHROME")
            print("=" * 70)
            print()
            print(e)
            print()
            print(
                "Pastikan terlebih dahulu menjalankan:"
            )
            print()
            print("    python chrome_launcher.py")
            print()

            sys.exit(1)

        print(
            f"[SUCCESS] Connected to Chrome."
        )

        print(
            f"[INFO] Contexts: "
            f"{len(browser.contexts)}"
        )

        if not browser.contexts:

            print(
                "[ERROR] Tidak ada browser context."
            )

            browser.close()
            sys.exit(1)

        context = browser.contexts[0]

        print(
            f"[INFO] Pages: "
            f"{len(context.pages)}"
        )

        if not context.pages:

            print(
                "[ERROR] Tidak ada tab/page."
            )

            browser.close()
            sys.exit(1)

        # Pilih page yang ZeusX jika tersedia.
        page = None

        for candidate in context.pages:

            if EXPECTED_HOST in candidate.url:
                page = candidate
                break

        if page is None:
            page = context.pages[-1]

        print()
        print("=" * 70)
        print("CURRENT PAGE")
        print("=" * 70)
        print()
        print(f"URL   : {page.url}")
        print(f"TITLE : {page.title()}")
        print()

        if EXPECTED_HOST not in page.url:

            print(
                "[WARNING] Page saat ini bukan ZeusX."
            )

            print(
                "Silakan buka ZeusX Create Offer "
                "di Chrome terlebih dahulu."
            )

            input(
                "Setelah siap, tekan ENTER..."
            )

        # Tunggu rendering.
        try:
            page.wait_for_load_state(
                "domcontentloaded",
                timeout=10000
            )
        except PlaywrightTimeoutError:
            pass

        # Berikan waktu untuk SPA render.
        page.wait_for_timeout(2000)

        print()
        print("[1/5] Capturing page information...")

        page_info = get_page_information(page)

        save_json(
            f"page_{timestamp}.json",
            page_info
        )

        print()
        print("[2/5] Capturing complete HTML...")

        html = page.locator(
            "html"
        ).evaluate(
            "(element) => element.outerHTML"
        )

        save_text(
            f"dom_{timestamp}.html",
            html
        )

        print()
        print("[3/5] Capturing interactive elements...")

        interactive_elements = (
            get_interactive_elements(page)
        )

        save_json(
            f"interactive_elements_{timestamp}.json",
            interactive_elements
        )

        print(
            f"[INFO] "
            f"{len(interactive_elements)} "
            f"interactive elements found."
        )

        print()
        print("[4/5] Capturing forms and buttons...")

        forms = get_forms(page)

        buttons = get_buttons(page)

        save_json(
            f"forms_{timestamp}.json",
            forms
        )

        save_json(
            f"buttons_{timestamp}.json",
            buttons
        )

        print(
            f"[INFO] Forms found: {len(forms)}"
        )

        print(
            f"[INFO] Buttons found: {len(buttons)}"
        )

        print()
        print("[5/5] Capturing screenshot...")

        screenshot_path = (
            OUTPUT_DIR
            / f"page_{timestamp}.png"
        )

        page.screenshot(
            path=str(screenshot_path),
            full_page=True
        )

        print(
            f"[SAVED] {screenshot_path}"
        )

        print()
        print("=" * 70)
        print("INSPECTION COMPLETE")
        print("=" * 70)
        print()
        print(
            f"Output directory:\n"
            f"{OUTPUT_DIR}"
        )
        print()
        print("Files:")
        print(
            f"  dom_{timestamp}.html"
        )
        print(
            f"  interactive_elements_{timestamp}.json"
        )
        print(
            f"  forms_{timestamp}.json"
        )
        print(
            f"  buttons_{timestamp}.json"
        )
        print(
            f"  page_{timestamp}.json"
        )
        print(
            f"  page_{timestamp}.png"
        )
        print()

        print(
            "Chrome akan tetap terbuka."
        )

        input(
            "Tekan ENTER untuk disconnect inspector..."
        )

        # Hanya disconnect Playwright.
        # Tidak perlu menutup Chrome user.
        browser.close()


if __name__ == "__main__":
    main()