from __future__ import annotations

import json
import time
from pathlib import Path

from cookiekit import load_browser_cookies, parse_browser_spec
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


OUTDIR = Path(__file__).resolve().parent


def export_mathacademy_cookies() -> list[dict[str, object]]:
    spec = parse_browser_spec("chrome/.mathacademy.com:Default")
    cookies = load_browser_cookies(spec)
    playwright_cookies: list[dict[str, object]] = []
    for cookie in cookies:
        domain = (cookie.domain or "").lstrip(".")
        if not domain.endswith("mathacademy.com"):
            continue
        payload: dict[str, object] = {
            "name": cookie.name,
            "value": cookie.value or "",
            "domain": cookie.domain,
            "path": cookie.path or "/",
            "secure": bool(cookie.secure),
            "httpOnly": bool(cookie._rest.get("HttpOnly")) if hasattr(cookie, "_rest") else False,
        }
        if cookie.expires is not None:
            payload["expires"] = float(cookie.expires)
        playwright_cookies.append(payload)
    return playwright_cookies


def option_payload(select) -> dict[str, object]:
    return select.evaluate(
        """select => ({
            selected: select.value || "",
            options: Array.from(select.options).map(option => ({
                value: option.value || "",
                label: (option.textContent || "").trim(),
                disabled: !!option.disabled,
                group: option.parentElement && option.parentElement.tagName === "OPTGROUP"
                    ? option.parentElement.label || ""
                    : "",
            })),
        })"""
    )


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    cookies = export_mathacademy_cookies()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 2200}, locale="en-US")
        context.add_cookies(cookies)
        page = context.new_page()
        page.set_default_timeout(45_000)

        console_events: list[dict[str, object]] = []
        request_failures: list[dict[str, object]] = []
        response_events: list[dict[str, object]] = []
        page.on("console", lambda msg: console_events.append({"type": msg.type, "text": msg.text}))
        page.on(
            "requestfailed",
            lambda req: request_failures.append(
                {"url": req.url, "method": req.method, "failure": req.failure}
            ),
        )
        page.on(
            "response",
            lambda resp: response_events.append({"url": resp.url, "status": resp.status}),
        )

        page.goto("https://mathacademy.com/settings/course", wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=5_000)
        except PlaywrightTimeoutError:
            pass

        page.locator("#configureCourseButton").first.click()

        active_root = None
        active_select = None
        active_payload = None
        deadline = time.time() + 30
        while time.time() < deadline:
            for root_selector in ("#configureCourseDialog", "#courseDialog"):
                root = page.locator(root_selector).first
                try:
                    if not root.is_visible():
                        continue
                except Exception:
                    continue
                for select_selector in ("#configureCourseDialog-courseSelect", "#courseDialog-courseSelect"):
                    select = root.locator(select_selector).first
                    try:
                        if not select.is_visible():
                            continue
                    except Exception:
                        continue
                    payload = option_payload(select)
                    selectable = [
                        option
                        for option in payload.get("options", [])
                        if isinstance(option, dict)
                        and str(option.get("value", "")).strip()
                        and str(option.get("label", "")).strip() != "-"
                        and not bool(option.get("disabled"))
                    ]
                    if selectable:
                        active_root = root
                        active_select = select
                        active_payload = payload
                        active_root_selector = root_selector
                        active_select_selector = select_selector
                        break
                if active_root is not None:
                    break
            if active_root is not None:
                break
            page.wait_for_timeout(200)

        if active_root is None or active_select is None or active_payload is None:
            raise SystemExit("No populated course dialog became available")

        save = None
        save_selector = None
        for selector in (
            "#configureCourseDialog-saveButton",
            "#configureCourseDialog-submitButton",
            "#courseDialog-saveButton",
            "#courseDialog-submitButton",
        ):
            locator = active_root.locator(selector).first
            try:
                if locator.is_visible():
                    save = locator
                    save_selector = selector
                    break
            except Exception:
                continue

        if save is None or save_selector is None:
            raise SystemExit("No visible save button was found")

        before = {
            "url": page.url,
            "root_selector": active_root_selector,
            "select_selector": active_select_selector,
            "save_selector": save_selector,
            "save_state": save.evaluate(
                """el => ({
                    text: (el.textContent || "").trim(),
                    disabledProp: !!el.disabled,
                    ariaDisabled: el.getAttribute("aria-disabled"),
                    className: el.className,
                })"""
            ),
            "cover_count": page.locator(".screenCover").count(),
            "selected_value": active_select.input_value(),
            "has_143": any(
                isinstance(option, dict) and str(option.get("value", "")).strip() == "143"
                for option in active_payload.get("options", [])
            ),
        }

        active_select.select_option(value="143")

        snapshots: list[dict[str, object]] = []
        for step in range(50):
            cover_info = page.locator(".screenCover").evaluate_all(
                """elements => elements.map((element, index) => {
                    const style = window.getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return {
                        index,
                        display: style.display,
                        visibility: style.visibility,
                        pointerEvents: style.pointerEvents,
                        width: rect.width,
                        height: rect.height,
                        className: element.className,
                    };
                })"""
            )
            save_state = save.evaluate(
                """el => ({
                    text: (el.textContent || "").trim(),
                    disabledProp: !!el.disabled,
                    ariaDisabled: el.getAttribute("aria-disabled"),
                    className: el.className,
                })"""
            )
            current_course_text = page.locator("#course").first.evaluate(
                'el => (el.textContent || "").trim()'
            )
            snapshots.append(
                {
                    "step": step,
                    "save": save_state,
                    "covers": cover_info,
                    "current_course": current_course_text,
                    "selected_value": active_select.input_value(),
                }
            )

            visible_cover = any(
                cover["display"] != "none"
                and cover["visibility"] != "hidden"
                and cover["pointerEvents"] != "none"
                and cover["width"] > 0
                and cover["height"] > 0
                for cover in cover_info
            )
            save_disabled = bool(save_state.get("disabledProp")) or save_state.get("ariaDisabled") == "true"
            save_disabled = save_disabled or "buttonDisabled" in str(save_state.get("className"))

            if not visible_cover and not save_disabled:
                break

            page.wait_for_timeout(500)

        output = {
            "before": before,
            "after_selected": snapshots[-1] if snapshots else None,
            "snapshots": snapshots,
            "console": console_events[-100:],
            "request_failures": request_failures[-100:],
            "responses": response_events[-200:],
        }
        (OUTDIR / "course_143_diagnostic.json").write_text(
            json.dumps(output, indent=2),
            encoding="utf-8",
        )
        page.screenshot(path=str(OUTDIR / "course_143_full.png"), full_page=True)
        active_root.screenshot(path=str(OUTDIR / "course_143_dialog.png"))

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
