import threading
import time
import tkinter as tk
from tkinter import font as tkfont
import webbrowser

import ctypes
from ctypes import wintypes

import requests
from bs4 import BeautifulSoup

from Utility import windowsAppBar

from Utility import statusSources

import GUI.uiConfig as ui


class TickerOverlay(tk.Tk):
    def __init__(self):
        super().__init__()

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=ui.BG)

        # Force the window to exist so we can get a real hwnd
        self.update_idletasks()
        hwnd = int(self.winfo_id())

        monitors = windowsAppBar.get_monitors()
        if not monitors:
            # fallback: primary screen
            sw = self.winfo_screenwidth()
            self.geometry(f"{sw}x{ui.BAR_HEIGHT}+0+0")
        else:
            idx = max(0, min(ui.MONITOR_INDEX, len(monitors) - 1))
            m = monitors[idx]

            if ui.RESERVE_SPACE_FOR_MAXIMIZE:
                # AppBar reserves space in the WORK area so maximized windows stay below it
                left, top, right, bottom = windowsAppBar.appbar_set_top(hwnd, m, ui.BAR_HEIGHT)
                width = right - left
                self.geometry(f"{width}x{ui.BAR_HEIGHT}+{left}+{top}")
            else:
                # Just snap to monitor top without reserving space
                width = m["right"] - m["left"]
                self.geometry(f"{width}x{ui.BAR_HEIGHT}+{m['left']}+{m['top']}")


        # Optional: keep from stealing focus on click (Windows may still focus it)
        # self.attributes("-disabled", True)  # not reliable across platforms

        self.canvas = tk.Canvas(self, height=ui.BAR_HEIGHT, bg=ui.BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.ticker_font = tkfont.Font(family="Segoe UI", size=14, weight="bold")
        self.ticker_font_u = tkfont.Font(family="Segoe UI", size=14, weight="bold", underline=True)

        self.status_var = tk.StringVar(value="Starting…")
        self.status = tk.Label(self, textvariable=self.status_var, anchor="w",
                               bg=ui.BG, fg="#aaaaaa", padx=12, font=("Segoe UI", 9))
        self.status.place(x=8, y=ui.BAR_HEIGHT-18)

        self.items = []  # list of dicts: {id, kind, url}
        self._lock = threading.Lock()
        self._pending_segments = None
        self._closing = False

        # Close controls
        self.bind("<Escape>", lambda e: self._close())
        self.bind("<Control-q>", lambda e: self._close())

        # Allow dragging the bar (optional quality-of-life)
        self._drag_start = None
        self.bind("<ButtonPress-1>", self._start_drag)
        self.bind("<B1-Motion>", self._do_drag)

        # Start
        self.after(100, self._refresh_in_background)
        self.after(ui.TICK_MS, self._animate)
        self.after(ui.REFRESH_EVERY_SECONDS * 1000, self._scheduled_refresh)

        # Re-assert topmost periodically (helps with some apps)
        self.after(2000, self._reassert_topmost)

    def _reassert_topmost(self):
        if self._closing:
            return
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass
        self.after(2000, self._reassert_topmost)

    def _close(self):
        self._closing = True
        try:
            if ui.RESERVE_SPACE_FOR_MAXIMIZE:
                windowsAppBar.appbar_remove(int(self.winfo_id()))
        except Exception:
            pass
        self.destroy()

    def _set_status(self, txt: str):
        self.after(0, lambda: self.status_var.set(txt))

    def _start_drag(self, event):
        # only drag if clicked in empty area (not on a link)
        self._drag_start = (event.x_root, event.y_root, self.winfo_x(), self.winfo_y())

    def _do_drag(self, event):
        if not self._drag_start:
            return
        x0, y0, wx, wy = self._drag_start
        dx = event.x_root - x0
        dy = event.y_root - y0
        self.geometry(f"+{wx + dx}+{wy + dy}")

    def _scheduled_refresh(self):
        if self._closing:
            return
        self._refresh_in_background()
        self.after(ui.REFRESH_EVERY_SECONDS * 1000, self._scheduled_refresh)

    def _refresh_in_background(self):
        def worker():
            start = time.time()
            try:
                segs = statusSources.build_segments()

                with self._lock:
                    self._pending_segments = segs

                elapsed = time.time() - start
                self._set_status(
                    f"Refreshed in {elapsed:.1f}s • Will apply on next loop • Next {ui.REFRESH_EVERY_SECONDS}s • Esc/Ctrl+Q to close"
                )

                # BOOTSTRAP: if nothing is on-screen yet, trigger an immediate apply
                # (must be done on Tk main thread)
                if not self.items:
                    self.after(0, self._apply_pending_now_if_empty)

            except Exception as e:
                self._set_status(f"Refresh failed: {e!r} (retrying)")

        self._set_status("Refreshing status…")
        threading.Thread(target=worker, daemon=True).start()



    def _clear_items(self):
        for item in self.items:
            self.canvas.delete(item["id"])
        self.items = []

    def _bind_click(self, item_id: int, url: str):
        def _open(_evt=None):
            try:
                webbrowser.open(url)
            except Exception:
                pass

        def _enter(_evt=None):
            # Canvas items may not support -cursor on some Tk builds,
            # so set cursor on the canvas widget instead.
            try:
                self.canvas.configure(cursor="hand2")
            except Exception:
                pass

        def _leave(_evt=None):
            try:
                self.canvas.configure(cursor="")
            except Exception:
                pass

        self.canvas.tag_bind(item_id, "<Button-1>", _open)
        self.canvas.tag_bind(item_id, "<Enter>", _enter)
        self.canvas.tag_bind(item_id, "<Leave>", _leave)


    def color_for_sev(sev: int) -> str:
        if sev == ui.SEV_OUTAGE:
            return ui.COLOR_OUTAGE
        if sev == ui.SEV_DEGRADED:
            return ui.COLOR_DEGRADED
        return ui.COLOR_OK

    def _layout_segments_off_right(self, segs):
        self._clear_items()

        w = max(self.canvas.winfo_width(), 1)
        x = w + 10
        y = (ui.BAR_HEIGHT // 2) - 6  # visually centered-ish

        for idx, seg in enumerate(segs):
            if idx > 0:
                sep_id = self.canvas.create_text(
                    x, y, text=ui.SEP, fill='white', font=self.ticker_font, anchor="w"
                )
                self.items.append({"id": sep_id, "kind": "sep", "url": None})
                x = self.canvas.bbox(sep_id)[2] + 2

            txt = seg["text"]
            sev = seg["sev"]
            url = seg["url"]
            clickable = seg["clickable"]

            fill = statusSources.color_for_sev(sev)
            font_used = self.ticker_font_u if clickable else self.ticker_font

            item_id = self.canvas.create_text(
                x, y, text=txt, fill=fill, font=font_used, anchor="w"
            )
            self.items.append({"id": item_id, "kind": "seg", "url": url})

            if clickable and url:
                self._bind_click(item_id, url)

            x = self.canvas.bbox(item_id)[2] + 2

    def _apply_pending_if_any(self):
        with self._lock:
            segs = self._pending_segments
            self._pending_segments = None

        if segs is not None:
            self._layout_segments_off_right(segs)

    def _apply_pending_now_if_empty(self):
        # Only used to draw the very first time so the bar isn't blank
        if self._closing or self.items:
            return

        with self._lock:
            segs = self._pending_segments
            self._pending_segments = None

        if segs is not None:
            self._layout_segments_off_right(segs)



    def _animate(self):
        if self._closing:
            return

        # If we have no items yet, try to apply pending (bootstrap safety)
        if not self.items:
            self._apply_pending_now_if_empty()
            self.after(ui.TICK_MS, self._animate)
            return

        # Move all items left smoothly
        for item in self.items:
            self.canvas.move(item["id"], -ui.SCROLL_PIXELS_PER_TICK, 0)

        # If everything has scrolled off the left, we are at the natural loop point.
        rightmost = max(
            (self.canvas.bbox(item["id"])[2] for item in self.items if self.canvas.bbox(item["id"])),
            default=0
        )

        if rightmost < 0:
            # At loop boundary: apply any pending refresh NOW (no mid-scroll jump)
            with self._lock:
                segs = self._pending_segments
                self._pending_segments = None

            if segs is not None:
                # Swap in refreshed content
                self._layout_segments_off_right(segs)
            else:
                # No pending update; loop the current content by rebuilding it
                current = []
                for item in self.items:
                    if item["kind"] != "seg":
                        continue
                    txt = self.canvas.itemcget(item["id"], "text")
                    fill = self.canvas.itemcget(item["id"], "fill")
                    url = item["url"]

                    # infer severity from fill color
                    sev = statusSources.SEV_OK
                    if fill.lower() == ui.COLOR_OUTAGE.lower():
                        sev = statusSources.SEV_OUTAGE
                    elif fill.lower() == ui.COLOR_DEGRADED.lower():
                        sev = statusSources.SEV_DEGRADED

                    current.append({
                        "text": txt,
                        "sev": sev,
                        "url": url,
                        "clickable": bool(url),
                    })

                self._layout_segments_off_right(current)

        self.after(ui.TICK_MS, self._animate)