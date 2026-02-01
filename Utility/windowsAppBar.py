import ctypes
from ctypes import wintypes
from Utility import statusSources

user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32

ABM_NEW = 0x00000000
ABM_REMOVE = 0x00000001
ABM_QUERYPOS = 0x00000002
ABM_SETPOS = 0x00000003

ABE_TOP = 1


class APPBARDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uCallbackMessage", wintypes.UINT),
        ("uEdge", wintypes.UINT),
        ("rc", wintypes.RECT),
        ("lParam", wintypes.LPARAM),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


MonitorEnumProc = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HMONITOR,
    wintypes.HDC,
    ctypes.POINTER(wintypes.RECT),
    wintypes.LPARAM,
)


def get_monitors():
    """
    Returns list of dicts:
      [{"left":..,"top":..,"right":..,"bottom":..,
        "work_left":..,"work_top":..,"work_right":..,"work_bottom":..}, ...]
    Ordered left-to-right, then top-to-bottom.
    """
    monitors = []

    def _callback(hMon, hdc, lprc, lparam):
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(hMon, ctypes.byref(mi))
        monitors.append({
            "left": mi.rcMonitor.left,
            "top": mi.rcMonitor.top,
            "right": mi.rcMonitor.right,
            "bottom": mi.rcMonitor.bottom,
            "work_left": mi.rcWork.left,
            "work_top": mi.rcWork.top,
            "work_right": mi.rcWork.right,
            "work_bottom": mi.rcWork.bottom,
        })
        return True

    user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(_callback), 0)
    monitors.sort(key=lambda m: (m["left"], m["top"]))
    return monitors


def appbar_set_top(hwnd: int, monitor_rect: dict, height: int):
    """
    Register + reserve space at top of the chosen monitor's WORK area.
    Makes maximized windows stop below it.
    Returns (left, top, right, bottom) for the reserved bar rectangle.
    """
    abd = APPBARDATA()
    abd.cbSize = ctypes.sizeof(APPBARDATA)
    abd.hWnd = wintypes.HWND(hwnd)
    abd.uCallbackMessage = 0

    shell32.SHAppBarMessage(ABM_NEW, ctypes.byref(abd))

    left = monitor_rect["work_left"]
    right = monitor_rect["work_right"]
    top = monitor_rect["work_top"]

    abd.uEdge = ABE_TOP
    abd.rc.left = left
    abd.rc.right = right
    abd.rc.top = top
    abd.rc.bottom = top + height

    shell32.SHAppBarMessage(ABM_QUERYPOS, ctypes.byref(abd))
    shell32.SHAppBarMessage(ABM_SETPOS, ctypes.byref(abd))

    return abd.rc.left, abd.rc.top, abd.rc.right, abd.rc.bottom


def appbar_remove(hwnd: int):
    abd = APPBARDATA()
    abd.cbSize = ctypes.sizeof(APPBARDATA)
    abd.hWnd = wintypes.HWND(hwnd)
    shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(abd))
