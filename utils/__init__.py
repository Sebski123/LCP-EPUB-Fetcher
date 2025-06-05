import win32con
import win32gui
import win32process


def hide_visible_window_by_pid(hwnd: int, pid: int):
    """Callback function for EnumWindows to find the Thorium Reader window by process ID.
    If the window is visible, it hides it.

    Args:
        hwnd: _handle to the window
        pid: Process ID of the Thorium Reader process
    """
    if win32gui.IsWindowVisible(hwnd):
        _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
        if found_pid == pid:
            # Hide the window
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
