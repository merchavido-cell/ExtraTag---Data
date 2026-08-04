import sys
import io
import os
import builtins
import json
import uuid
from winpty import PtyProcess
import queue
import threading
import ctypes
from ctypes import wintypes
from packaging import version  # להשוואת גרסאות מדויקת
import time
import tempfile
import msvcrt
import pathlib
from datetime import datetime
import argparse
from dotenv import load_dotenv
import requests
import webview
import imaplib
import smtplib
import ssl
import winshell
from pathlib import Path
from win32com.client import Dispatch
import base64
import subprocess
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header, make_header
import asyncio
import email
import email.utils

# ---------------- TERMINAL & PRINT FIX ----------------

if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

def safe_print(*args, **kwargs):
    sep = kwargs.get('sep', ' ')
    end = kwargs.get('end', '\n')
    file = kwargs.get('file', sys.stdout)

    message = sep.join(str(arg) for arg in args) + end

    try:
        file.write(message)
    except UnicodeEncodeError:
        encoding = getattr(file, 'encoding', 'ascii') or 'ascii'
        clean_message = message.encode(encoding, errors='ignore').decode(encoding)
        file.write(clean_message)
    except Exception:
        pass

builtins.print = safe_print

# ---------------- PYTHON 3.14 FIX ----------------

if not hasattr(asyncio, "coroutine"):
    asyncio.coroutine = lambda f: f

# ---------------- GITHUB CONFIG & HELPERS ----------------

BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / "legendsecret093.env"
load_dotenv(dotenv_path=env_path)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
print(f"DEBUG: Loaded GITHUB_TOKEN = {GITHUB_TOKEN}")

GITHUB_RAW_URL = "https://raw.githubusercontent.com/merchavido-cell/ExtraTag---Data/main/global_history.json"
GITHUB_API_URL = "https://api.github.com/repos/merchavido-cell/ExtraTag---Data/contents/global_history.json"

GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "Python-App"
}

def safe_get(url, retries=5):
    for i in range(retries):
        try:
            return requests.get(url, timeout=10)
        except Exception as e:
            print(f"GET error, retry {i+1}/{retries}: {e}")
            time.sleep(1 + i)
    return None

def github_load_global_history():
    print("\n=== GITHUB → github_load_global_history() ===")
    info = requests.get(GITHUB_API_URL, headers=GITHUB_HEADERS)
    info.raise_for_status()
    sha = info.json()["sha"]

    resp = requests.get(GITHUB_RAW_URL)
    resp.raise_for_status()
    raw = resp.text.strip()

    if raw == "":
        data = {}
    elif raw == "[]":
        data = []
    else:
        try:
            data = json.loads(raw)
        except Exception as e:
            print("❌ Error loading JSON:", e)
            data = {}

    print("✔ Loaded JSON + SHA:", sha)
    return data, sha

def clean_data_for_github(data):
    """
    מנקה ומסיר את שדות המצב המקומיים (is_logged_in, is_selected)
    לפני העלאה ל-GitHub בלבד!
    """
    if isinstance(data, list):
        cleaned = []
        for item in data:
            if isinstance(item, dict):
                item_copy = item.copy()
                item_copy.pop("is_logged_in", None)
                item_copy.pop("is_selected", None)
                cleaned.append(item_copy)
            else:
                cleaned.append(item)
        return cleaned
    elif isinstance(data, dict):
        data_copy = data.copy()
        data_copy.pop("is_logged_in", None)
        data_copy.pop("is_selected", None)
        return data_copy
    return data

def github_save_global_history(data, sha):
    if sha is None:
        print("❌ Cannot save: SHA is None")
        return

    # סינון הנתונים שלא יעלו ל-GitHub עם is_logged_in ו-is_selected
    data_to_upload = clean_data_for_github(data)

    encoded = base64.b64encode(json.dumps(data_to_upload, ensure_ascii=False, indent=4).encode()).decode()

    payload = {
        "message": "Update global_history.json",
        "content": encoded,
        "sha": sha
    }

    resp = requests.put(GITHUB_API_URL, json=payload, headers=GITHUB_HEADERS)

    if resp.status_code == 409:
        print("⚠ SHA mismatch → refreshing SHA")
        meta = requests.get(GITHUB_API_URL, headers=GITHUB_HEADERS)
        meta.raise_for_status()
        new_sha = meta.json().get("sha")

        payload["sha"] = new_sha
        resp = requests.put(GITHUB_API_URL, json=payload, headers=GITHUB_HEADERS)

    try:
        resp.raise_for_status()
    except Exception:
        print("❌ Save failed:", resp.text)
        raise

    print("✔ Saved successfully to GitHub (Filtered local flags)")

def sync_local_history_from_global(local_path):
    if not os.path.exists(local_path):
        return

    try:
        global_profiles, _ = github_load_global_history()

        with open(local_path, "r", encoding="utf-8") as f:
            local_profiles = json.load(f)

        if not isinstance(global_profiles, list) or not isinstance(local_profiles, list):
            return

        global_map = {
            str(profile.get("id")): profile
            for profile in global_profiles
            if profile.get("id") is not None
        }

        updated = False

        for i, local_profile in enumerate(local_profiles):
            profile_id = str(local_profile.get("id")) if local_profile.get("id") is not None else None

            if profile_id and profile_id in global_map:
                # שמירה על הסטטוסים המקומיים הקיימים ב-local_history
                saved_logged_in = local_profile.get("is_logged_in")
                saved_selected = local_profile.get("is_selected")

                local_profiles[i].update(global_map[profile_id])

                if saved_logged_in is not None:
                    local_profiles[i]["is_logged_in"] = saved_logged_in
                if saved_selected is not None:
                    local_profiles[i]["is_selected"] = saved_selected

                updated = True

        if updated:
            with open(local_path, "w", encoding="utf-8") as f:
                json.dump(local_profiles, f, ensure_ascii=False, indent=4)
            print("✔ local_history synced successfully!")

    except Exception as e:
        print(f"sync_local_history_from_global error: {e}")

class TerminalManager:
    def __init__(self):
        self.pty = None
        self.window = None
        self.running = False
        self.lock = threading.Lock()

    def start(self, window, cwd):
        print(f"DEBUG: [TerminalManager] Starting PTY session in: '{cwd}'")
        self.window = window

        if self.pty and self.pty.isalive():
            print("DEBUG: [TerminalManager] PTY session already active.")
            return

        if not cwd or not os.path.exists(cwd):
            cwd = os.path.expanduser("~")

        try:
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"

            self.pty = PtyProcess.spawn(
                "cmd.exe",
                cwd=cwd,
                dimensions=(24, 80),
                env=env
            )
            self.running = True

            threading.Thread(
                target=self.reader_loop,
                daemon=True
            ).start()

            time.sleep(0.1)
            self.write("chcp 65001\r\n")

        except Exception as e:
            print(f"❌ DEBUG: [TerminalManager] Spawn error: {e}")

    def reader_loop(self):
        print("DEBUG: [TerminalManager] Reader loop thread started.")
        while self.running:
            if not self.pty:
                break

            try:
                if not self.pty.isalive():
                    print("DEBUG: [TerminalManager] PTY process ended.")
                    break

                data = self.pty.read(size=4096)

                if data and self.window:
                    safe = json.dumps(data)
                    js_code = f"""
                    if (typeof terminalWrite === 'function') {{
                        terminalWrite({safe});
                    }}
                    """
                    self.window.evaluate_js(js_code)

            except EOFError:
                break
            except Exception:
                time.sleep(0.01)

        print("DEBUG: [TerminalManager] Reader loop stopped.")

    def write(self, data):
        if self.pty and self.pty.isalive():
            try:
                if isinstance(data, bytes):
                    data = data.decode('utf-8', errors='ignore')
                self.pty.write(data)
            except Exception as e:
                print(f"❌ DEBUG: [TerminalManager] Write error: {e}")

    def resize(self, rows, cols):
        if self.pty and self.pty.isalive():
            try:
                self.pty.setwinsize(rows, cols)
            except Exception:
                pass

    def stop(self):
        self.running = False
        if self.pty:
            try:
                self.pty.close()
            except Exception:
                pass
            self.pty = None

terminal_session = TerminalManager()

class Api:
    def __init__(self, base_directory):
        print("=== INIT START ===")
        self.base_dir = base_directory
        print("base_dir:", self.base_dir)

        internal_dir = os.path.join(self.base_dir, "_internal")
        if os.path.exists(internal_dir):
            self.html_base_dir = internal_dir
        else:
            self.html_base_dir = self.base_dir

        self.db_path = os.path.join(self.base_dir, "local_history.json")
        self.global_db_path = os.path.join(self.base_dir, "global_history.json")
        self.pty_process = None
        self.current_process = None
        self.proc = None
        self.output_queue = queue.Queue()
        self.github_raw_url = GITHUB_RAW_URL
        self.github_api_url = GITHUB_API_URL
        self.github_sha = None
        self.proc = None
        self.pty_proc = None
        self._sync_running = False
        self.mega_lock = threading.Lock()
        self.pty = None
        if not os.path.exists(self.db_path):
            self._save(self.db_path, [])

        if not os.path.exists(self.global_db_path):
            self._save(self.global_db_path, [])

        self.exe_path = self._get_exe_path()

        try:
            data, sha = github_load_global_history()
            self._save(self.global_db_path, data)
            self.github_sha = sha
        except Exception as e:
            print("❌ Error loading history from GitHub:", e)
            self.github_sha = None

    def handle_mobile_request(self, request_data):
        """
        פונקציית לכידה מרכזית המקבלת בקשות מה-Mobile Bridge ומריצה את פונקציית ה-Api הנדרשת
        """
        try:
            data = json.loads(request_data) if isinstance(request_data, str) else request_data
            func_name = data.get("func")
            args = data.get("args", [])
            req_id = data.get("reqId")

            func = getattr(self, func_name, None)
            if callable(func):
                result = func(*args)
                
                # המרה של תוצאה במידת הצורך להעברה נקייה בחזרה ל-JS
                if isinstance(result, (dict, list)):
                    res_payload = json.dumps(result, ensure_ascii=False)
                else:
                    res_payload = result

                js_callback = f"if(window['res_{req_id}']) window['res_{req_id}']({json.dumps(res_payload)});"
                
                window = self._get_window()
                if window:
                    window.evaluate_js(js_callback)
                return json.dumps({"success": True}, ensure_ascii=False)
            else:
                print(f"Mobile Bridge Error: Function {func_name} not found.")
                return json.dumps({"success": False, "error": f"Function {func_name} not found"}, ensure_ascii=False)
        except Exception as e:
            print(f"Mobile Bridge Execution Error: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    def get_local_history_json(self):
        try:
            data = self._load(self.db_path)
            return json.dumps(data, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error in get_local_history_json: {e}")
            return json.dumps([], ensure_ascii=False)

    def load_history(self):
        try:
            data = self._load(self.global_db_path)
            return data
        except Exception as e:
            print("❌ Error in load_history:", e)
            return []

    def _get_window(self):
        for _ in range(30):
            if webview.windows:
                return webview.windows[0]
            time.sleep(0.1)
        return None

    def _ensure_file(self, path):
        if not os.path.exists(path):
            self._save(path, [])

    def _load(self, path):
        try:
            if not os.path.exists(path):
                self._save(path, [])
                return []

            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()

            if not content:
                return []

            data = json.loads(content)
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"JSON load error: {path} -> {e}")
            return []

    def _save(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)

        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            os.replace(tmp, path)
        except Exception:
            try:
                os.remove(tmp)
            except Exception:
                pass
            raise

    def create_profile(self, profile_data):
        try:
            profile = self._parse_input(profile_data)

            if not profile:
                return {"success": False, "message": "Invalid profile data"}

            local_profiles = self._load(self.db_path)
            global_profiles = self._load(self.global_db_path)

            email = str(profile.get("email", "")).strip().lower()
            exmail = str(profile.get("exmail", "")).strip().lower()

            for p in global_profiles:
                if (
                    str(p.get("email", "")).strip().lower() == email or
                    (exmail and str(p.get("exmail", "")).strip().lower() == exmail)
                ):
                    return {"success": False, "message": "User already exists"}

            if not profile.get("id"):
                profile["id"] = str(uuid.uuid4())

            profile["is_logged_in"] = True
            profile["is_selected"] = True

            for p in local_profiles:
                p["is_logged_in"] = False
                p["is_selected"] = False

            for p in global_profiles:
                p["is_logged_in"] = False
                p["is_selected"] = False

            local_profiles.append(profile.copy())
            global_profiles.append(profile.copy())

            self._save(self.db_path, local_profiles)
            self._save(self.global_db_path, global_profiles)

            threading.Thread(target=lambda: github_save_global_history(
                self._load(self.global_db_path),
                self.github_sha
            ), daemon=True).start()

            return {"success": True, "profile": profile}

        except Exception as e:
            return {"success": False, "message": str(e)}

    def _get_exe_path(self):
        if getattr(sys, "frozen", False):
            return sys.executable
        return os.path.abspath(__file__)

    def _create_windows_shortcut(self, shortcut_path, target, arguments, icon_path=None, description=""):
        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(shortcut_path)
        shortcut.TargetPath = target
        shortcut.Arguments = arguments
        shortcut.WorkingDirectory = os.path.dirname(target)

        if icon_path and os.path.exists(icon_path):
            shortcut.IconLocation = icon_path

        shortcut.Description = description
        shortcut.save()

    def select_folder(self):
        try:
            result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
            if result and len(result) > 0:
                selected_path = result[0]
                folder_name = os.path.basename(selected_path)
                return json.dumps({
                    "success": True,
                    "folder_path": selected_path,
                    "folder_name": folder_name
                }, ensure_ascii=False)
            return json.dumps({"success": False, "error": "No folder selected"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    def create_file(self, file_name, content="", folder_path=None):
        try:
            if not folder_path:
                raise ValueError("לא נבחרה תיקיית עבודה.")
            if not os.path.exists(folder_path):
                raise ValueError(f"התיקייה '{folder_path}' אינה קיימת.")

            file_path = os.path.join(folder_path, file_name)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return json.dumps({"success": True, "path": file_path}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    def get_folder_contents(self, folder_path):
        try:
            if not folder_path or not os.path.exists(folder_path):
                return json.dumps({"success": False, "error": "Invalid folder path"}, ensure_ascii=False)

            items = []
            for entry in os.scandir(folder_path):
                if entry.name.startswith('.'):
                    continue
                items.append({
                    "name": entry.name,
                    "path": entry.path,
                    "is_dir": entry.is_dir()
                })

            items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            return json.dumps({"success": True, "items": items}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    def read_file(self, file_path):
        try:
            if not os.path.exists(file_path):
                return json.dumps({"success": False, "error": "File does not exist"}, ensure_ascii=False)

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            return json.dumps({"success": True, "content": content}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    def _enqueue_output(self, out):
        for line in iter(out.readline, ''):
            self.output_queue.put(line)
        out.close()

    def _read_available_stdout(self):
        if not self.proc or not self.proc.stdout:
            return ""
        try:
            handle = msvcrt.get_osfhandle(self.proc.stdout.fileno())
            avail = wintypes.DWORD()
            success = ctypes.windll.kernel32.PeekNamedPipe(
                handle, None, 0, None, ctypes.byref(avail), None
            )
            if success and avail.value > 0:
                raw_data = os.read(self.proc.stdout.fileno(), avail.value)
                return raw_data.decode('utf-8', errors='ignore')
        except Exception:
            pass
        return ""

    def start_terminal(self, folder_path=None):
        try:
            window = self._get_window()
            if not window:
                return json.dumps({"success": False, "error": "Window not ready"})
            terminal_session.start(window, folder_path)
            return json.dumps({"success": True})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def send_terminal_input(self, data):
        try:
            terminal_session.write(data)
            return json.dumps({"success": True})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def stop_terminal(self):
        terminal_session.stop()
        return True

    def resize_terminal(self, rows, cols):
        terminal_session.resize(rows, cols)
        return True
    
    def execute_terminal_command(self, command, terminal_type, folder_path):
        print("\n==================================================")
        print(f"DEBUG: [Api] 'execute_terminal_command' invoked!")
        print(f"DEBUG: [Api] Input Command: '{command}'")
        print(f"DEBUG: [Api] Terminal Type: '{terminal_type}'")
        print(f"DEBUG: [Api] Folder Path:   '{folder_path}'")
        print("==================================================")

        try:
            if not folder_path or not os.path.exists(folder_path):
                print(f"❌ DEBUG: [Api] Error: Folder path '{folder_path}' does not exist!")
                return json.dumps({"output": "Error: Path not found\n", "is_running": False}, ensure_ascii=False)

            if not terminal_session.pty or not terminal_session.pty.isalive():
                print("DEBUG: [Api] Terminal session is NOT alive. Calling self.start_terminal()...")
                start_res = self.start_terminal(folder_path)
                print(f"DEBUG: [Api] start_terminal result: {start_res}")
                
                print("DEBUG: [Api] Waiting 0.2s for PTY spawn initialization...")
                time.sleep(0.2)
                
                print("DEBUG: [Api] Reading initial terminal header output...")
                initial_output = terminal_session.write_and_read("", timeout=0.3)
                print(f"DEBUG: [Api] Initial Output captured ({len(initial_output)} chars)")
            else:
                print("DEBUG: [Api] Terminal session is ALREADY alive. Proceeding with command.")
                initial_output = ""

            print(f"DEBUG: [Api] Sending command '{command}' to write_and_read...")
            output = terminal_session.write_and_read(command, timeout=0.3)
            print(f"DEBUG: [Api] Command Output captured ({len(output)} chars)")

            full_output = initial_output + output
            is_alive = terminal_session.pty.isalive() if terminal_session.pty else False

            print(f"DEBUG: [Api] Total Output Length: {len(full_output)} | Is Alive: {is_alive}")
            print("==================================================\n")

            return json.dumps({
                "output": full_output,
                "is_running": is_alive
            }, ensure_ascii=False)

        except Exception as e:
            print(f"❌ DEBUG: [Api] Exception in execute_terminal_command: {e}")
            return json.dumps({"output": f"Terminal Error: {str(e)}\n", "is_running": False}, ensure_ascii=False)

    def create_app_shortcut(self, app_name, folder_name):
        try:
            target = self._get_exe_path()
            desktop = winshell.desktop()

            start_menu = os.path.join(
                os.environ["APPDATA"],
                "Microsoft", "Windows", "Start Menu", "Programs", "ExtraTag"
            )
            os.makedirs(start_menu, exist_ok=True)

            desktop_shortcut = os.path.join(desktop, f"{app_name}.lnk")
            start_shortcut = os.path.join(start_menu, f"{app_name}.lnk")

            icon_path = os.path.join(self.base_dir, folder_name, f"{app_name}.ico")
            if not os.path.exists(icon_path):
                icon_path = target

            arguments = f'--app "{folder_name}"'

            self._create_windows_shortcut(desktop_shortcut, target, arguments, icon_path, app_name)
            self._create_windows_shortcut(start_shortcut, target, arguments, icon_path, app_name)

            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def navigate_to(self, file, folder=None):
        window = self._get_window()
        if not window:
            return json.dumps({"success": False, "error": "window is None"}, ensure_ascii=False)

        def _do_navigate():
            try:
                if folder:
                    page_path = os.path.join(self.base_dir, folder, file)
                else:
                    page_path = os.path.join(self.base_dir, file)

                file_url = "file:///" + os.path.abspath(page_path).replace("\\", "/")
                window.load_url(file_url)
            except Exception as e:
                print("Navigation error:", e)

        threading.Thread(target=_do_navigate, daemon=True).start()
        return json.dumps({"success": True}, ensure_ascii=False)

    def go_back(self):
        window = self._get_window()
        if not window:
            return json.dumps({"success": False, "error": "window is None"}, ensure_ascii=False)

        try:
            window.evaluate_js("window.history.back();")
            return json.dumps({"success": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    def get_profiles_from_file(self):
        profiles = self._load(self.db_path)
        return json.dumps(profiles, ensure_ascii=False)

    def save_profile_to_file(self, profile_data):
        try:
            parsed_data = self._parse_input(profile_data)
            if not parsed_data:
                return False

            if isinstance(parsed_data, list):
                self._save(self.db_path, parsed_data)
                self._save(self.global_db_path, parsed_data)

                threading.Thread(
                    target=lambda: github_save_global_history(
                        parsed_data,
                        self.github_sha
                    ), 
                    daemon=True
                ).start()
                return True

            profile = parsed_data
            if not profile.get("id"):
                profile["id"] = str(uuid.uuid4())

            profile["is_logged_in"] = True
            profile["is_selected"] = True

            profiles = self._load(self.db_path)
            for p in profiles:
                p["is_logged_in"] = False
                p["is_selected"] = False

            found = False
            for i, p in enumerate(profiles):
                if p.get("id") == profile.get("id"):
                    profiles[i].update(profile)
                    found = True
                    break

            if not found:
                profiles.append(profile)

            self._save(self.db_path, profiles)

            global_profiles = self._load(self.global_db_path)
            for p in global_profiles:
                p["is_logged_in"] = False
                p["is_selected"] = False

            found = False
            for i, p in enumerate(global_profiles):
                if (
                    p.get("id") == profile.get("id")
                    or p.get("email", "").lower() == profile.get("email", "").lower()
                ):
                    global_profiles[i].update(profile)
                    found = True
                    break

            if not found:
                global_profiles.append(profile.copy())

            self._save(self.global_db_path, global_profiles)

            threading.Thread(
                target=lambda: github_save_global_history(
                    self._load(self.global_db_path),
                    self.github_sha
                ), 
                daemon=True
            ).start()

            return True

        except Exception as e:
            print("save_profile_to_file error:", e)
            return False

    def delete_profile_by_id(self, profile_id):
        try:
            profiles = self._load(self.db_path)
            updated_profiles = [
                p for p in profiles 
                if str(p.get("id")) != str(profile_id) 
                and p.get("exmail") != profile_id 
                and p.get("email") != profile_id
            ]

            if len(profiles) == len(updated_profiles):
                return False

            self._save(self.db_path, updated_profiles)

            global_profiles = self._load(self.global_db_path)
            updated_global = [
                p for p in global_profiles 
                if str(p.get("id")) != str(profile_id) 
                and p.get("exmail") != profile_id 
                and p.get("email") != profile_id
            ]
            self._save(self.global_db_path, updated_global)

            threading.Thread(
                target=lambda: github_save_global_history(
                    self._load(self.global_db_path),
                    self.github_sha
                ), 
                daemon=True
            ).start()

            return True

        except Exception as e:
            print("delete_profile_by_id error:", e)
            return False

    def _parse_input(self, data):
        if isinstance(data, str):
            try:
                return json.loads(data)
            except Exception:
                return {}
        if isinstance(data, dict):
            return data
        return {}

    def get_last_profile(self):
        profiles = self._load(self.db_path)
        return json.dumps({
            "success": True,
            "profile": profiles[-1] if profiles else {}
        }, ensure_ascii=False)

    def get_active_profile(self):
        try:
            profiles = self._load(self.db_path)
            active_profile = None

            for p in profiles:
                if p.get("is_selected") is True:
                    active_profile = p
                    break

            if not active_profile:
                return json.dumps({
                    "success": False,
                    "profile": None,
                    "message": "No active profile selected"
                }, ensure_ascii=False)

            result = {
                "success": True,
                "profile": {
                    "id": active_profile.get("id"),
                    "firstName": active_profile.get("firstName"),
                    "lastName": active_profile.get("lastName"),
                    "email": active_profile.get("email"),
                    "password": active_profile.get("password"),
                    "is_logged_in": active_profile.get("is_logged_in", False),
                    "is_selected": active_profile.get("is_selected", False),
                    "avatarColor": active_profile.get("avatarColor"),
                    "avatarShape": active_profile.get("avatarShape"),
                    "avatarTextColor": active_profile.get("avatarTextColor"),
                    "custom_username": active_profile.get("custom_username"),
                    "exmail": active_profile.get("exmail")
                }
            }
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "profile": None, "message": str(e)}, ensure_ascii=False)

    def create_exmail(self, profile_data):
        try:
            profile = self._parse_input(profile_data)
            if not profile or "id" not in profile:
                return json.dumps({"success": False, "message": "Invalid profile data"}, ensure_ascii=False)

            local_part = profile.get("custom_username")
            if not local_part:
                base_name = profile.get("firstName", "user").lower().strip().replace(" ", "")
                unique_id = profile.get("id")[-4:]
                local_part = f"{base_name}{unique_id}"
            
            generated_exmail = f"{local_part}@extra-tag.com"
            generated_expass = "P@ssword123!"

            MIGADU_USER = "merchavido@gmail.com" 
            MIGADU_TOKEN = "oYT2FXvovB8NCtkXvjbqX5QaUtqpbl0rQeKAJu-Lb4_2jBhm3Xp4msPc0mCQP0TDW7P80NPseMHa6x_9XbbaFg"
            url = f"https://api.migadu.com/v1/domains/extra-tag.com/mailboxes/"
            
            auth_string = f"{MIGADU_USER}:{MIGADU_TOKEN}"
            encoded_auth = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
            
            payload = {
                "local_part": local_part,
                "password": generated_expass,
                "name": f"User {local_part}", 
                "is_active": True
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Basic {encoded_auth}"
            }
            
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code in [201, 409, 400, 200]:
                print(f"✔ Migadu returned status {response.status_code}.")
            else:
                return json.dumps({"success": False, "message": f"Critical Migadu error: {response.status_code}"}, ensure_ascii=False)

            profiles = self._load(self.db_path)
            for i, p in enumerate(profiles):
                if p.get("id") == profile.get("id"):
                    profiles[i].update({
                        "exmail": generated_exmail,
                        "expass": generated_expass,
                        "custom_username": local_part,
                        "is_logged_in": True
                    })
                    profile = profiles[i]
                    break

            self._save(self.db_path, profiles)
            self.update_global_profile(profile)
            
            return json.dumps({
                "success": True,
                "email": generated_exmail,
                "password": generated_expass,
                "updated_profile": profile
            }, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)

    def login_by_email(self, email_input, password):
        res_json = self.login(email_input, password)
        return json.loads(res_json)

    def login(self, email_input, password):
        profiles = self._load(self.db_path)
        email_input = (email_input or "").lower().strip()

        target_index = None

        for i, p in enumerate(profiles):
            profile_email = p.get("email", "").lower().strip()
            profile_exmail = p.get("exmail", "").lower().strip()
            profile_password = p.get("password")

            if (profile_email == email_input or profile_exmail == email_input) and profile_password == password:
                target_index = i
                break

        if target_index is None:
            return json.dumps({"success": False, "message": "Wrong email or password"}, ensure_ascii=False)

        for p in profiles:
            p["is_logged_in"] = False

        profiles[target_index]["is_logged_in"] = True
        self._save(self.db_path, profiles)

        return json.dumps({"success": True, "profile": profiles[target_index]}, ensure_ascii=False)

    def logout(self, email=None):
        profiles = self._load(self.db_path)
        email_norm = email.lower().strip() if isinstance(email, str) else None

        for p in profiles:
            if email_norm is None or p.get("email", "").lower().strip() == email_norm:
                p["is_logged_in"] = False

        self._save(self.db_path, profiles)
        return True

    def logout_by_email(self, email):
        return self.logout(email)

    def get_global_history(self):
        try:
            history = self._load(self.global_db_path)
            return json.dumps(history, ensure_ascii=False)
        except Exception as e:
            return json.dumps([], ensure_ascii=False)

    def login_from_global_history(self, email_input, password):
        try:
            global_profiles = self._load(self.global_db_path)
            local_profiles = self._load(self.db_path)

            email_input = (email_input or "").strip().lower()
            password = (password or "").strip()

            target_index = None

            for i, profile in enumerate(global_profiles):
                email = str(profile.get("email", "")).strip().lower()
                exmail = str(profile.get("exmail", "")).strip().lower()
                profile_password = str(profile.get("password", ""))

                if (email == email_input or exmail == email_input) and profile_password == password:
                    target_index = i
                    break

            if target_index is None:
                return {"success": False, "message": "Wrong email or password"}

            for profile in global_profiles:
                profile["is_logged_in"] = False
                profile["is_selected"] = False

            global_profiles[target_index]["is_logged_in"] = True
            global_profiles[target_index]["is_selected"] = True

            active_profile = global_profiles[target_index]
            self._save(self.global_db_path, global_profiles)

            for p in local_profiles:
                p["is_selected"] = False

            exists_in_local = any(
                p.get("id") == active_profile.get("id")
                for p in local_profiles
            )

            if not exists_in_local:
                new_profile = active_profile.copy()
                local_profiles.append(new_profile)
                self._save(self.db_path, local_profiles)
            else:
                for p in local_profiles:
                    if p.get("id") == active_profile.get("id"):
                        p.update(active_profile)
                self._save(self.db_path, local_profiles)

            threading.Thread(target=lambda: github_save_global_history(
                self._load(self.global_db_path),
                self.github_sha
            ), daemon=True).start()

            return {"success": True, "profile": active_profile}

        except Exception as e:
            return {"success": False, "message": str(e)}

    def update_login_status(self, profile_id, status):
        profiles = self._load(self.db_path)
        for p in profiles:
            if p.get("id") == profile_id:
                p["is_logged_in"] = bool(status)
            elif bool(status):
                p["is_logged_in"] = False

        self._save(self.db_path, profiles)
        return json.dumps({"success": True}, ensure_ascii=False)

    def set_active_profile(self, profile_id):
        profiles = self._load(self.db_path)
        for p in profiles:
            p["is_selected"] = (p.get("id") == profile_id)

        self._save(self.db_path, profiles)
        return True

    def logout_from_profile(self):
        return self.logout()

    def upload_file_to_storage(self):
        import mimetypes
        try:
            if not webview.windows:
                return json.dumps({"success": False, "error": "No active window found"}, ensure_ascii=False)

            active_window = webview.windows[0]
            file_paths = active_window.create_file_dialog(webview.OPEN_DIALOG)

            if not file_paths:
                return json.dumps({"success": False, "message": "לא נבחר קובץ"}, ensure_ascii=False)

            source_path = file_paths[0]
            file_name = os.path.basename(source_path)
            file_size = os.path.getsize(source_path)

            MAX_SIZE_MB = 5
            max_size_bytes = MAX_SIZE_MB * 1024 * 1024

            if file_size > max_size_bytes:
                return json.dumps({
                    "success": False,
                    "error": "size_limit_exceeded",
                    "file_name": file_name,
                    "max_allowed_mb": MAX_SIZE_MB
                }, ensure_ascii=False)

            with open(source_path, "rb") as f:
                file_bytes = f.read()

            base64_encoded = base64.b64encode(file_bytes).decode("utf-8")
            mime_type, _ = mimetypes.guess_type(source_path)
            if not mime_type:
                mime_type = "application/octet-stream"

            base64_url = f"data:{mime_type};base64,{base64_encoded}"

            return json.dumps({
                "success": True,
                "file_name": file_name,
                "file_size": file_size,
                "file_data": base64_url
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    def smtp_send_generic(self, sender_email, password, smtp_server, smtp_port, receiver, subject, body):
        try:
            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = receiver
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            if smtp_port == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
                    server.login(sender_email, password)
                    server.sendmail(sender_email, receiver, msg.as_string())
            else:
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls()
                    server.login(sender_email, password)
                    server.sendmail(sender_email, receiver, msg.as_string())

            return json.dumps({"success": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)

    def get_exmail(self, email_address):
        try:
            profiles = self._load(self.db_path)
            profile = next((p for p in profiles if p.get("exmail") == email_address or p.get("email") == email_address), None)

            if not profile:
                return json.dumps({"success": False, "message": "Mailbox not found"}, ensure_ascii=False)

            password = profile.get("expass") if "extra-tag.com" in email_address else profile.get("password")

            imap = imaplib.IMAP4_SSL("imap.migadu.com", 993)
            imap.login(email_address, password)
            imap.select("INBOX")

            status, messages = imap.search(None, "ALL")
            if status != "OK":
                return json.dumps({"success": False, "message": "Failed to search inbox"}, ensure_ascii=False)

            mail_ids = messages[0].split()
            emails = []

            for mail_id in reversed(mail_ids[-50:]):
                status, msg_data = imap.fetch(mail_id, "(RFC822)")
                if status != "OK": continue

                msg = email.message_from_bytes(msg_data[0][1])
                subject = str(make_header(decode_header(msg.get("Subject", ""))))
                raw_sender = msg.get("From", "")
                _, sender_email = email.utils.parseaddr(raw_sender)
                sender = sender_email if sender_email else raw_sender

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                            break
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

                emails.append({
                    "from": sender,
                    "subject": subject,
                    "body": body[:500]
                })

            imap.close()
            imap.logout()

            return json.dumps({"success": True, "emails": emails}, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)

    def send_email(self, sender_email, receiver, subject, body):
        try:
            all_profiles = self._load(self.db_path)
            profile = next((p for p in all_profiles if p.get("is_logged_in")), None)

            if not profile and sender_email != "calc@extra-tag.com":
                return json.dumps({"success": False, "message": "No active profile"}, ensure_ascii=False)

        except Exception as e:
            if sender_email != "calc@extra-tag.com":
                return json.dumps({"success": False, "message": "Failed to load profile"}, ensure_ascii=False)

        smtp_server = "smtp.migadu.com"
        smtp_port = 587

        if sender_email == "calc@extra-tag.com":
            smtp_username = "calc@extra-tag.com"
            smtp_password = "P@ssword123!"
        else:
            smtp_username = profile.get("exmail") or profile.get("email")
            if "extra-tag.com" in (smtp_username or ""):
                smtp_password = profile.get("expass")
            else:
                smtp_password = profile.get("password")

        if not smtp_username or not smtp_password:
            return json.dumps({"success": False, "message": "Missing credentials in profile"}, ensure_ascii=False)

        try:
            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = receiver
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            context = ssl.create_default_context()

            with smtplib.SMTP(smtp_server, int(smtp_port), timeout=20) as server:
                server.set_debuglevel(1)
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)

            if profile:
                if "sent_emails" not in profile or not isinstance(profile["sent_emails"], list):
                    profile["sent_emails"] = []

                profile["sent_emails"].insert(0, {
                    "to": receiver,
                    "subject": subject,
                    "body": body,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                })

                if hasattr(self, '_save'):
                    self._save(self.db_path, all_profiles)

            return json.dumps({"success": True}, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)

    def get_sent_emails(self, email):
        try:
            all_profiles = self._load(self.db_path)
            profile = next((p for p in all_profiles if p.get("is_logged_in")), None)

            if not profile:
                return json.dumps({"success": False, "emails": []}, ensure_ascii=False)

            sent_list = profile.get("sent_emails", [])
            return json.dumps({"success": True, "emails": sent_list}, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"success": False, "error": str(e), "emails": []}, ensure_ascii=False)

    def fetch_emails(self, email_address, password, imap_server="imap.gmail.com", folder="INBOX", limit=10):
        try:
            mail = imaplib.IMAP4_SSL(imap_server)
            mail.login(email_address, password)
            mail.select(folder)

            status, messages = mail.search(None, "ALL")
            if status != "OK":
                return json.dumps({"success": False, "message": "Failed to fetch emails"}, ensure_ascii=False)

            email_ids = messages[0].split()
            email_ids = email_ids[-limit:]

            emails = []
            for eid in reversed(email_ids):
                status, msg_data = mail.fetch(eid, "(RFC822)")
                if status != "OK":
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = str(make_header(decode_header(msg.get("Subject", ""))))
                from_ = msg.get("From", "")
                date_ = msg.get("Date", "")

                emails.append({
                    "subject": subject,
                    "from": from_,
                    "date": date_
                })

            mail.logout()
            return json.dumps({"success": True, "emails": emails}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)

    def run_command(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return json.dumps({
                "success": True,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)

    def _decode_mime_header(self, value):
        if not value:
            return ""
        try:
            return str(make_header(decode_header(value)))
        except Exception:
            return value

    def save_global_history(self, profile_json):
        try:
            profile = self._parse_input(profile_json)
            if not profile:
                return json.dumps({"success": False, "message": "Invalid profile data"}, ensure_ascii=False)
            return self.update_global_profile(profile)
        except Exception as e:
            return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)

    def open_file_from_storage(self, file_name, base64_data_url):
        try:
            if "," in base64_data_url:
                header, base64_str = base64_data_url.split(",", 1)
            else:
                base64_str = base64_data_url

            file_bytes = base64.b64decode(base64_str)
            temp_dir = tempfile.gettempdir()
            target_path = os.path.join(temp_dir, file_name)

            with open(target_path, "wb") as f:
                f.write(file_bytes)

            os.startfile(target_path)
            return json.dumps({"success": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    def delete_file_from_storage(self, email, file_name):
        try:
            global_profiles = self._load(self.global_db_path)
            found = False

            for i, p in enumerate(global_profiles):
                if str(p.get("email", "")).lower().strip() == str(email).lower().strip():
                    files_list = p.get("files", [])
                    updated_files = [f for f in files_list if f.get("file_name") != file_name]
                    
                    if len(files_list) != len(updated_files):
                        global_profiles[i]["files"] = updated_files
                        found = True
                    break

            if found:
                self._save(self.global_db_path, global_profiles)
                threading.Thread(target=lambda: github_save_global_history(
                    self._load(self.global_db_path),
                    self.github_sha
                ), daemon=True).start()

                return json.dumps({"success": True}, ensure_ascii=False)
            else:
                return json.dumps({"success": False, "error": "User or File not found"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    def download_file_from_storage(self, file_name, base64_data_url):
        try:
            if "," in base64_data_url:
                header, base64_str = base64_data_url.split(",", 1)
            else:
                base64_str = base64_data_url

            file_bytes = base64.b64decode(base64_str)
            user_home = os.path.expanduser("~")
            downloads_dir = os.path.join(user_home, "Downloads")
            
            if not os.path.exists(downloads_dir):
                os.makedirs(downloads_dir)

            target_path = os.path.join(downloads_dir, file_name)

            with open(target_path, "wb") as f:
                f.write(file_bytes)

            os.system(f'explorer /select,"{target_path}"')
            return json.dumps({"success": True, "saved_path": target_path}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    def get_system_storage_info(self, active_profile):
        try:
            TOTAL_LIMIT_BYTES = 5 * 1024 * 1024

            used_bytes = 0
            user_files = active_profile.get("files", []) if active_profile else []

            for file_item in user_files:
                file_data = file_item.get("file_data", "")
                if file_data:
                    used_bytes += len(file_data.encode("utf-8"))

            used_mb = round(used_bytes / (1024 * 1024), 2)
            total_mb = 5.0
            free_mb = round(max(0, total_mb - used_mb), 2)

            used_percent = round((used_bytes / TOTAL_LIMIT_BYTES) * 100, 1)
            used_percent = min(100.0, used_percent)

            return json.dumps(
                {
                    "success": True,
                    "total_space": f"{total_mb:.1f} MB",
                    "used_space": f"{used_mb} MB",
                    "free_space": f"{free_mb} MB",
                    "used_percent": used_percent,
                },
                ensure_ascii=False,
            )

        except Exception as e:
            return json.dumps(
                {"success": False, "error": str(e)}, ensure_ascii=False
            )

    def update_global_profile(self, profile):
        try:
            global_profiles = self._load(self.global_db_path)
            prof_copy = profile.copy()

            for key in ["is_logged_in", "is_selected", "is_logged_in_email", "is_logged_in_Storage"]:
                prof_copy.pop(key, None)

            found = False
            local_id = str(prof_copy.get("id", ""))
            local_email = str(prof_copy.get("email", "")).lower().strip()

            for i, p in enumerate(global_profiles):
                p_id = str(p.get("id", ""))
                p_email = str(p.get("email", "")).lower().strip()

                if p_id == local_id or p_email == local_email:
                    current_files = global_profiles[i].get("files", [])
                    new_files = prof_copy.get("files", [])
                    
                    global_profiles[i].update(prof_copy)
                    
                    if new_files:
                        global_profiles[i]["files"] = new_files
                    else:
                        global_profiles[i]["files"] = current_files
                        
                    found = True
                    break

            if not found:
                global_profiles.append(prof_copy)

            self._save(self.global_db_path, global_profiles)

            threading.Thread(target=lambda: github_save_global_history(
                self._load(self.global_db_path),
                self.github_sha
            ), daemon=True).start()

            return json.dumps({"success": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

CURRENT_VERSION = "1.0.6"

SERVER_VERSION_URL = "https://raw.githubusercontent.com/merchavido-cell/ExtraTag---Data/main/version.json"


def auto_update_from_server():
    """בודק בשרת אם יש גרסה חדשה מ-CURRENT_VERSION, מוריד ומריץ את ה-Setup ברקע."""
    try:
        print(f"🔍 Checking for updates... Current version: {CURRENT_VERSION}")

        response = requests.get(SERVER_VERSION_URL, timeout=5)

        if response.status_code == 200:
            data = response.json()
            latest_version_str = data.get("version")

            download_url = data.get("download_url") or data.get("url")

            if not latest_version_str or not download_url:
                print(
                    "⚠️ Server JSON missing 'version' or 'download_url' keys."
                )
                return

            if version.parse(latest_version_str) > version.parse(
                CURRENT_VERSION
            ):
                print(
                    f"🚀 New update found! Server: {latest_version_str} > Local: {CURRENT_VERSION}"
                )

                temp_dir = os.environ.get("TEMP", "C:\\Windows\\Temp")
                temp_installer = os.path.join(
                    temp_dir, "ExtraTag_Setup_Update.exe"
                )

                print(f"📥 Downloading update from {download_url}...")
                with requests.get(download_url, stream=True, timeout=15) as r:
                    r.raise_for_status()
                    with open(temp_installer, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)

                print("✅ Download complete. Launching installer silently...")

                subprocess.Popen([
                    temp_installer,
                    "/VERYSILENT",
                    "/SUPPRESSMSGBOXES",
                    "/NORESTART",
                ])

                sys.exit(0)
            else:
                print("✨ You are running the latest version.")
    except Exception as e:
        print(f"DEBUG: Auto-update check skipped/failed: {e}")


def check_version_status(exe_dir):
    """בודק את מצב ההפעלה:

    - מחזיר ('first_run', None) בהפעלה ראשונה אי פעם.
    - מחזיר ('upgrade', previous_version) במידה וזו גרסה חדשה שעודכנה.
    - מחזיר ('normal', current_version) בהפעלה רגילה באותה גרסה.
    """
    flag_file = os.path.join(exe_dir, "version_status.flag")
    main_dir = os.path.dirname(exe_dir)

    if not os.path.exists(flag_file) and not os.path.exists(
        os.path.join(main_dir, "version_status.flag")
    ):
        try:
            with open(flag_file, "w", encoding="utf-8") as f:
                f.write(
                    f"VERSION={CURRENT_VERSION}\nFIRST_RUN={datetime.now()}\nUPDATED={datetime.now()}"
                )
            print(
                f"DEBUG: Created initial flag file with version {CURRENT_VERSION}"
            )
        except Exception as e:
            print(f"DEBUG: Failed to create flag file: {e}")

        return "first_run", None

    saved_version = None
    target_flag_path = (
        flag_file
        if os.path.exists(flag_file)
        else os.path.join(main_dir, "version_status.flag")
    )

    try:
        with open(target_flag_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VERSION="):
                    saved_version = line.strip().split("=")[1]
                    break
    except Exception as e:
        print(f"DEBUG: Failed to read flag file: {e}")

    if saved_version != CURRENT_VERSION:
        try:
            with open(target_flag_path, "w", encoding="utf-8") as f:
                f.write(
                    f"VERSION={CURRENT_VERSION}\nUPDATED={datetime.now()}"
                )
            print(
                f"DEBUG: Upgraded flag file from {saved_version} to {CURRENT_VERSION}"
            )
        except Exception as e:
            print(f"DEBUG: Failed to update flag file: {e}")

        return "upgrade", saved_version

    return "normal", CURRENT_VERSION


if __name__ == "__main__":
    # 0. בדיקת עדכון מהשרת
    auto_update_from_server()

    # 1. הגדרת נתיבים לפי הסביבה
    if getattr(sys, "frozen", False):
        base_directory = sys._MEIPASS
        exe_directory = os.path.dirname(sys.executable)
    else:
        base_directory = os.path.dirname(os.path.abspath(__file__))
        exe_directory = base_directory

    # 2. בדיקת גרסה
    status, prev_ver = check_version_status(exe_directory)
    if status == "first_run":
        print("🚀 First run detected!")
    elif status == "upgrade":
        print(f"🎉 Upgraded from {prev_ver} to {CURRENT_VERSION}")
    else:
        print(f"ℹ️ Running ExtraTag version {CURRENT_VERSION}")

    # 3. ארגומנטים
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=str, help="Target app folder name")
    args, unknown = parser.parse_known_args()

    # 4. אתחול API וסינכרון
    api = Api(base_directory)
    sync_local_history_from_global(api.db_path)

    # 5. הגדרת נתיב ה-HTML
    selected_folder = args.app if args.app else "Extratag - Apps"
    initial_path = os.path.join(base_directory, selected_folder, "index.html")
    file_url = "file:///" + os.path.abspath(initial_path).replace("\\", "/")

    # 6. בדיקת סביבה: האם מורץ במובייל (Kivy) או בדסקטופ (pywebview)
    if "ANDROID_ARGUMENT" in os.environ:
        # סביבת Android (Kivy WebView)
        try:
            from kivy.app import App  # type: ignore
            from kivy.uix.webview import WebView  # type: ignore
        except ImportError:
            sys.exit(1)

        class MobileApp(App):
            def build(self):
                # טעינת ה-HTML המקומי בתוך ה-APK
                return WebView(url=file_url)

        MobileApp().run()

    else:
        # סביבת Desktop (pywebview)
        window_title = f"ExtraTag - {selected_folder.replace('Extratag - ', '')}"
        window = webview.create_window(
            title=window_title,
            url=file_url,
            js_api=api,
            width=900,
            height=700,
        )

        def setup_mobile_bridge():
            js_bridge_code = """
            (function() {
                if (typeof window.pywebview === 'undefined') {
                    window.pywebview = {
                        api: new Proxy({}, {
                            get: function(target, propKey) {
                                return function(...args) {
                                    return new Promise((resolve, reject) => {
                                        const reqId = 'req_' + Math.random().toString(36).substr(2, 9);
                                        window['res_' + reqId] = function(response) {
                                            try {
                                                resolve(typeof response === 'string' ? JSON.parse(response) : response);
                                            } catch(e) {
                                                resolve(response);
                                            }
                                            delete window['res_' + reqId];
                                        };
                                        if (window.AndroidBridge && window.AndroidBridge.postMessage) {
                                            window.AndroidBridge.postMessage(JSON.stringify({ func: propKey, args: args, reqId: reqId }));
                                        } else if (window.pywebview_api && window.pywebview_api.handle_mobile_request) {
                                            window.pywebview_api.handle_mobile_request(JSON.stringify({ func: propKey, args: args, reqId: reqId }));
                                        }
                                    });
                                };
                            }
                        })
                    };
                }
            })();
            """
            try:
                window.evaluate_js(js_bridge_code)
            except Exception as e:
                print(f"DEBUG: Bridge injection skipped or error: {e}")

        webview.start(setup_mobile_bridge, debug=False)