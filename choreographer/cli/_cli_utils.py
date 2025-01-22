from __future__ import annotations

import argparse
import asyncio
import json
import platform
import shutil
import sys
import urllib.request
import warnings
import zipfile
from pathlib import Path

# SOON TODO this isn't the right download path, look at uv, use sysconfig
_default_download_path = Path(__file__).resolve().parent / "browser_exe"

_chrome_for_testing_url = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"

_platforms = ["linux64", "win32", "win64", "mac-x64", "mac-arm64"]

_arch_size_detected = "64" if sys.maxsize > 2**32 else "32"
_arch_detected = "arm" if platform.processor() == "arm" else "x"

if platform.system() == "Windows":
    _chrome_platform_detected = "win" + _arch_size_detected
elif platform.system() == "Linux":
    _chrome_platform_detected = "linux" + _arch_size_detected
elif platform.system() == "Darwin":
    _chrome_platform_detected = "mac-" + _arch_detected + _arch_size_detected

_default_exe_path = Path()
if platform.system().startswith("Linux"):
    _default_exe_path = (
        _default_download_path / f"chrome-{_chrome_platform_detected}" / "chrome"
    )
elif platform.system().startswith("Darwin"):
    _default_exe_path = (
        _default_download_path
        / f"chrome-{_chrome_platform_detected}"
        / "Google Chrome for Testing.app"
        / "Contents"
        / "MacOS"
        / "Google Chrome for Testing"
    )
elif platform.system().startswith("Win"):
    _default_exe_path = (
        _default_download_path / f"chrome-{_chrome_platform_detected}" / "chrome.exe"
    )


def get_chrome_download_path() -> Path:
    return _default_exe_path


# https://stackoverflow.com/questions/39296101/python-zipfile-removes-execute-permissions-from-binaries
class _ZipFilePermissions(zipfile.ZipFile):
    def _extract_member(self, member, targetpath, pwd):  # type: ignore [no-untyped-def]
        if not isinstance(member, zipfile.ZipInfo):
            member = self.getinfo(member)

        path = super()._extract_member(member, targetpath, pwd)  # type: ignore [misc]
        # High 16 bits are os specific (bottom is st_mode flag)
        attr = member.external_attr >> 16
        if attr != 0:
            Path(path).chmod(attr)
        return path


def get_chrome_sync(
    arch: str = _chrome_platform_detected,
    i: int = -1,
    path: str | Path = _default_download_path,
    *,
    verbose: bool = False,
) -> Path | str:
    """Download chrome synchronously: see `get_chrome()`."""
    if isinstance(path, str):
        path = Path(path)
    browser_list = json.loads(
        urllib.request.urlopen(  # noqa: S310 audit url for schemes
            _chrome_for_testing_url,
        ).read(),
    )
    version_obj = browser_list["versions"][i]
    if verbose:
        print(version_obj["version"])  # noqa: T201 allow print in cli
        print(version_obj["revision"])  # noqa: T201 allow print in cli
    chromium_sources = version_obj["downloads"]["chrome"]
    url = ""
    for src in chromium_sources:
        if src["platform"] == arch:
            url = src["url"]
            break
    if not path.exists():
        path.mkdir(parents=True)
    filename = path / "chrome.zip"
    with urllib.request.urlopen(url) as response, filename.open("wb") as out_file:  # noqa: S310 audit url
        shutil.copyfileobj(response, out_file)
    with _ZipFilePermissions(filename, "r") as zip_ref:
        zip_ref.extractall(path)

    if arch.startswith("linux"):
        exe_name = path / f"chrome-{arch}" / "chrome"
    elif arch.startswith("mac"):
        exe_name = (
            path
            / f"chrome-{arch}"
            / "Google Chrome for Testing.app"
            / "Contents"
            / "MacOS"
            / "Google Chrome for Testing"
        )
    elif arch.startswith("win"):
        exe_name = path / f"chrome-{arch}" / "chrome.exe"

    return exe_name


async def get_chrome(
    arch: str = _chrome_platform_detected,
    i: int = -1,
    path: str | Path = _default_download_path,
    *,
    verbose: bool = False,
) -> Path | str:
    """
    Download google chrome from google-chrome-for-testing server.

    Args:
        arch: the target platform/os, as understood by google's json directory.
        i: the chrome version: -1 being the latest version, 0 being the oldest
           still in the testing directory.
        path: where to download it too (the folder).
        verbose: print out version found

    """
    return await asyncio.to_thread(
        get_chrome_sync,
        arch=arch,
        i=i,
        path=path,
        verbose=verbose,
    )


def get_chrome_cli() -> None:
    if "ubuntu" in platform.version().lower():
        warnings.warn(  # noqa: B028
            "You are using `get_browser()` on Ubuntu."
            " Ubuntu is **very strict** about where binaries come from."
            " You have to disable the sandbox with use_sandbox=False"
            " when you initialize the browser OR you can install from Ubuntu's"
            " package manager.",
            UserWarning,
        )
    parser = argparse.ArgumentParser(description="tool to help debug problems")
    parser.add_argument("--i", "-i", type=int, dest="i")
    parser.add_argument("--arch", dest="arch")
    parser.add_argument("--path", dest="path")
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
    )
    parser.set_defaults(i=-1)
    parser.set_defaults(path=_default_download_path)
    parser.set_defaults(arch=_chrome_platform_detected)
    parser.set_defaults(verbose=False)
    parsed = parser.parse_args()
    i = parsed.i
    arch = parsed.arch
    path = Path(parsed.path)
    verbose = parsed.verbose
    if not arch or arch not in _platforms:
        raise RuntimeError(
            "You must specify a platform: "
            f"linux64, win32, win64, mac-x64, mac-arm64, not {platform}",
        )
    print(get_chrome_sync(arch=arch, i=i, path=path, verbose=verbose))  # noqa: T201 allow print in cli
