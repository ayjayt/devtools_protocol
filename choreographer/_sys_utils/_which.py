import os
import platform
import shutil

from choreographer._cli_utils import get_chrome_download_path

from ._chrome_constants import chrome_names, typical_chrome_paths


def _is_exe(path):
    try:
        return os.access(path, os.X_OK)
    except:  # noqa: E722 bare except ok, weird errors, best effort.
        return False


def _which_from_windows_reg():
    try:
        import re
        import winreg

        command = winreg.QueryValueEx(
            winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT,
                "ChromeHTML\\shell\\open\\command",
                0,
                winreg.KEY_READ,
            ),
            "",
        )[0]
        exe = re.search('"(.*?)"', command).group(1)
    except BaseException:  # noqa: BLE001 don't care why, best effort search
        return None

    return exe


def browser_which(executable_names=chrome_names, *, skip_local=False):  # noqa: C901
    path = None

    if isinstance(executable_names, str):
        executable_name = [executable_names]

    local_chrome = get_chrome_download_path()
    if (
        local_chrome.exists()
        and not skip_local
        and local_chrome.name in executable_names
    ):
        return local_chrome

    if platform.system() == "Windows":
        os.environ["NoDefaultCurrentDirectoryInExePath"] = "0"  # noqa: SIM112 var name set by windows

    for exe in executable_name:
        if platform.system() == "Windows" and exe == "chrome":
            path = _which_from_windows_reg()
        if path and _is_exe(path):
            return path
        path = shutil.which(exe)
        if path and _is_exe(path):
            return path
    # which didn't work

    # hail mary
    if "chrome" in executable_names:
        for candidate in typical_chrome_paths:
            if _is_exe(candidate):
                return candidate
    return None


def get_browser_path(**kwargs):
    return os.environ.get("BROWSER_PATH", browser_which(**kwargs))
