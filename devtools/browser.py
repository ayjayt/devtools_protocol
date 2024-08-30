from .pipe import Pipe
from .protocol import Protocol
from .pipe import PipeClosedError
from threading import Thread
import platform
import os
import sys
import subprocess
import tempfile
import warnings
import json

from .system import which_browser

default_path = which_browser()


class Browser:
    def __init__(self, path=default_path, headless=True, debug=False, debug_browser=None):
        if path is None:
            raise ValueError("You must specify a path")

        self.pipe = Pipe(debug=debug)

        if platform.system() != "Windows":
            self.temp_dir = tempfile.TemporaryDirectory()
        else:
            self.temp_dir = tempfile.TemporaryDirectory(
                delete=False, ignore_cleanup_errors=True
            )

        if not debug_browser:  # false o None
            stderr = subprocess.DEVNULL
        elif debug_browser is True:
            stderr = None
        else:
            stderr = debug

        new_env = os.environ.copy()
        new_env["CHROMIUM_PATH"] = str(path)
        new_env["USER_DATA_DIR"] = str(self.temp_dir.name)
        if headless:
            new_env["HEADLESS"] = "--headless" # unset if false

        win_only = {}
        if platform.system() == "Windows":
            win_only = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}

        proc = subprocess.Popen(
            [
                sys.executable,
                os.path.join(
                    os.path.dirname(os.path.realpath(__file__)), "chrome_wrapper.py"
                ),
            ],
            close_fds=True,
            stdin=self.pipe.read_to_chromium,
            stdout=self.pipe.write_from_chromium,
            stderr=stderr,
            env=new_env,
            **win_only,
        )
        self.subprocess = proc
        self.protocol = Protocol(self.pipe)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close_browser()

    def create_tab_1(self, url="chrome://new-tab-page/"):
        self.protocol.create_tab_1(url)

    def create_tab_2(self, tab_obj, data):
        self.protocol.create_tab_2(self, tab_obj, data)

    def list_tabs(self):
        self.protocol.list_tabs()

    def close_tab(self, tab):
        self.protocol.close_tab(tab)

    def close_browser(self):
        if platform.system() == "Windows":
            # maybe we don't need chrome_wrapper for windows because of how handles are needed
            # if we're not chaining process, this might not be necessary
            # otherwise, win behaves strangely in the face of signals, so call a command to kill the process instead
            # NB: chrome accepts being killed like this because it knows windows is a nightmare
            subprocess.call(
                ["taskkill", "/F", "/T", "/PID", str(self.subprocess.pid)]
            )  # this output should be handled better by where there is debug
            self.subprocess.wait(2)
        self.subprocess.terminate()
        self.subprocess.wait(2)
        self.subprocess.kill()
        try:
            self.temp_dir.cleanup()
        except Exception as e: # TODO- handle specific errors
            print(str(e))

        # windows doesn't like python's default cleanup
        if platform.system() == "Windows":
            import stat
            import shutil
            def remove_readonly(func, path, excinfo):
                os.chmod(path, stat.S_IWUSR)
                func(path)

            try:
                shutil.rmtree(self.temp_dir.name, onexc=remove_readonly)
                del self.temp_dir
            except PermissionError:
                warnings.warn(
                        "The temporary directory could not be deleted, but execution will continue."
                        )
            except Exception:
                warnings.warn(
                        "The temporary directory could not be deleted, but execution will continue."
                        )

    def send_command(self, command, params=None, session_id=""):
        return self.protocol.send_command(self, command, params, session_id)

    def run_output_thread(self, debug=False):
        print("Start run_output_thread() to improve debugging".center(6, "-"))

        def run_print(debug):
            while True:
                try:
                    json_list = self.pipe.read_jsons(debug=debug)
                    if json_list:
                        for json_ in json_list:
                            print(json.dumps(json_, indent=4))
                except PipeClosedError:
                    print("Pipe closed".center(10, "-"))
                    break

        thread_print = Thread(target=run_print, args=(debug,))
        thread_print.start()
