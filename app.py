import json
import os
import queue
import subprocess
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk


APP_TITLE = "Database Maintenance Console"
if getattr(sys := __import__("sys"), "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
LOG_DIR = BASE_DIR / "logs"
PROFILES_PATH = CONFIG_DIR / "profiles.json"

REQUIRED_SCRIPTS = [
    "backup_all.ps1",
    "restore_all.ps1",
    "backup_database.ps1",
    "restore_database.ps1",
    "backup_files.ps1",
    "restore_files.ps1",
    "clean_files.ps1",
    "clean_data.sql",
    "reset_database.sql",
    "rebuild_schema.ps1",
    "load_test_data.ps1",
]


def ensure_runtime_folders():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def load_profiles():
    ensure_runtime_folders()
    if not PROFILES_PATH.exists():
        return {"profiles": []}
    try:
        return json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not parse {PROFILES_PATH}: {exc}") from exc


def save_profiles(data):
    ensure_runtime_folders()
    PROFILES_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_env_file(env_path):
    values = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_db_config(profile):
    project_root = Path(profile["project_root"])
    env_file = project_root / profile.get("env_file", ".env")
    env_values = read_env_file(env_file)

    config = {
        "host": "localhost",
        "port": env_values.get("POSTGRES_PORT", "5432"),
        "database": env_values.get("POSTGRES_DB", "defect_tracker"),
        "user": env_values.get("POSTGRES_USER", "postgres"),
        "password": env_values.get("POSTGRES_PASSWORD", ""),
    }

    database_url = env_values.get("DATABASE_URL")
    if database_url:
        config.update(parse_database_url(database_url, config))
    return config


def parse_database_url(database_url, fallback):
    # Avoid adding SQLAlchemy as a dependency. This parser handles the local
    # postgresql+psycopg2 URLs used by this project.
    from urllib.parse import urlparse, unquote

    normalized = database_url.replace("postgresql+psycopg2://", "postgresql://")
    parsed = urlparse(normalized)
    result = dict(fallback)
    if parsed.hostname:
        result["host"] = parsed.hostname
    if parsed.port:
        result["port"] = str(parsed.port)
    if parsed.path and parsed.path != "/":
        result["database"] = parsed.path.lstrip("/")
    if parsed.username:
        result["user"] = unquote(parsed.username)
    if parsed.password:
        result["password"] = unquote(parsed.password)
    return result


def resolve_profile_path(profile, key, default_value):
    project_root = Path(profile["project_root"])
    value = profile.get(key) or default_value
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def find_tool(tool_name, pg_bin=""):
    if pg_bin:
        candidate = Path(pg_bin) / f"{tool_name}.exe"
        if candidate.exists():
            return str(candidate)

    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    for entry in path_entries:
        candidate = Path(entry) / f"{tool_name}.exe"
        if candidate.exists():
            return str(candidate)

    for version in ["18", "17", "16", "15"]:
        candidate = Path(f"C:/Program Files/PostgreSQL/{version}/bin/{tool_name}.exe")
        if candidate.exists():
            return str(candidate)

    return None


class ProfileDialog(tk.Toplevel):
    def __init__(self, parent, title, profile=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result = None
        self.transient(parent)
        self.grab_set()

        profile = profile or {}
        self.vars = {
            "name": tk.StringVar(value=profile.get("name", "")),
            "database_type": tk.StringVar(value=profile.get("database_type", "postgres")),
            "project_root": tk.StringVar(value=profile.get("project_root", "")),
            "env_file": tk.StringVar(value=profile.get("env_file", ".env")),
            "maintenance_folder": tk.StringVar(value=profile.get("maintenance_folder", "database/maintenance")),
            "upload_folder": tk.StringVar(value=profile.get("upload_folder", "uploads")),
            "pg_bin": tk.StringVar(value=profile.get("pg_bin", "")),
        }

        body = ttk.Frame(self, padding=16)
        body.grid(row=0, column=0, sticky="nsew")

        rows = [
            ("Profile Name", "name", None),
            ("Database Type", "database_type", None),
            ("Project Root", "project_root", self.browse_project_root),
            ("Env File", "env_file", None),
            ("Maintenance Folder", "maintenance_folder", None),
            ("Upload Folder", "upload_folder", None),
            ("PostgreSQL Bin", "pg_bin", self.browse_pg_bin),
        ]

        for row_index, (label, key, browse_cmd) in enumerate(rows):
            ttk.Label(body, text=label).grid(row=row_index, column=0, sticky="w", pady=5)
            if key == "database_type":
                field = ttk.Combobox(body, textvariable=self.vars[key], values=["postgres"], state="readonly", width=52)
            else:
                field = ttk.Entry(body, textvariable=self.vars[key], width=55)
            field.grid(row=row_index, column=1, sticky="ew", padx=(10, 6), pady=5)
            if browse_cmd:
                ttk.Button(body, text="Browse", command=browse_cmd).grid(row=row_index, column=2, pady=5)

        actions = ttk.Frame(body)
        actions.grid(row=len(rows), column=0, columnspan=3, sticky="e", pady=(14, 0))
        ttk.Button(actions, text="Cancel", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(actions, text="Save", command=self.save).pack(side="right")

        self.bind("<Escape>", lambda _event: self.destroy())
        self.wait_window(self)

    def browse_project_root(self):
        selected = filedialog.askdirectory(title="Select project root")
        if selected:
            self.vars["project_root"].set(selected)

    def browse_pg_bin(self):
        selected = filedialog.askdirectory(title="Select PostgreSQL bin folder")
        if selected:
            self.vars["pg_bin"].set(selected)

    def save(self):
        profile = {key: var.get().strip() for key, var in self.vars.items()}
        if not profile["name"]:
            messagebox.showerror("Profile Required", "Profile name is required.")
            return
        if not profile["project_root"]:
            messagebox.showerror("Project Root Required", "Project root is required.")
            return
        self.result = profile
        self.destroy()


class MaintenanceConsole(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1120x740")
        self.minsize(980, 620)

        self.profiles_data = load_profiles()
        self.active_profile = None
        self.connected = False
        self.psql_path = None
        self.pg_dump_path = None
        self.pg_restore_path = None
        self.output_queue = queue.Queue()
        self.current_log_file = None

        self.profile_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Not connected")

        self.configure_style()
        self.build_ui()
        self.refresh_profiles()
        self.after(120, self.drain_output_queue)

    def configure_style(self):
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Status.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Danger.TButton", foreground="#8a1111")

    def build_ui(self):
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Database Maintenance Console", style="Header.TLabel").pack(side="left")
        ttk.Label(header, textvariable=self.status_var, style="Status.TLabel").pack(side="right")

        profile_panel = ttk.LabelFrame(root, text="Profile", padding=12)
        profile_panel.pack(fill="x", pady=(0, 12))

        ttk.Label(profile_panel, text="Active Profile").grid(row=0, column=0, sticky="w")
        self.profile_combo = ttk.Combobox(profile_panel, textvariable=self.profile_var, state="readonly", width=45)
        self.profile_combo.grid(row=0, column=1, sticky="ew", padx=8)
        self.profile_combo.bind("<<ComboboxSelected>>", lambda _event: self.on_profile_selected())

        ttk.Button(profile_panel, text="Add", command=self.add_profile).grid(row=0, column=2, padx=4)
        ttk.Button(profile_panel, text="Edit", command=self.edit_profile).grid(row=0, column=3, padx=4)
        ttk.Button(profile_panel, text="Delete", command=self.delete_profile).grid(row=0, column=4, padx=4)
        ttk.Button(profile_panel, text="Connect", command=self.connect_profile).grid(row=0, column=5, padx=(14, 0))

        profile_panel.columnconfigure(1, weight=1)

        details_panel = ttk.LabelFrame(root, text="Connection Details", padding=12)
        details_panel.pack(fill="x", pady=(0, 12))
        self.details_text = tk.Text(details_panel, height=5, wrap="word", state="disabled")
        self.details_text.pack(fill="x")

        actions_panel = ttk.LabelFrame(root, text="Maintenance Actions", padding=12)
        actions_panel.pack(fill="x", pady=(0, 12))

        self.action_buttons = []
        self.add_action_button(actions_panel, "Backup All", self.backup_all, 0, 0)
        self.add_action_button(actions_panel, "Restore All", self.restore_all, 0, 1)
        self.add_action_button(actions_panel, "Clean Data", self.clean_data, 0, 2)
        self.add_action_button(actions_panel, "Reset Database", self.reset_database, 0, 3)
        self.add_action_button(actions_panel, "Load Test Data", self.load_test_data, 0, 4)
        self.add_action_button(actions_panel, "Run Smoke Tests", self.run_smoke_tests, 1, 0)
        self.add_action_button(actions_panel, "Open Backup Folder", self.open_backup_folder, 1, 1)
        self.add_action_button(actions_panel, "Open Project Folder", self.open_project_folder, 1, 2)
        self.set_actions_enabled(False)

        log_panel = ttk.LabelFrame(root, text="Operation Log", padding=12)
        log_panel.pack(fill="both", expand=True)

        log_frame = ttk.Frame(log_panel)
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_frame, wrap="word", state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        log_actions = ttk.Frame(log_panel)
        log_actions.pack(fill="x", pady=(10, 0))
        ttk.Button(log_actions, text="Clear Log", command=self.clear_log).pack(side="left")
        ttk.Button(log_actions, text="Open Log Folder", command=lambda: self.open_path(LOG_DIR)).pack(side="left", padx=8)

    def add_action_button(self, parent, text, command, row, column):
        button = ttk.Button(parent, text=text, command=command)
        button.grid(row=row, column=column, padx=5, pady=5, sticky="ew")
        parent.columnconfigure(column, weight=1)
        self.action_buttons.append(button)

    def refresh_profiles(self):
        names = [profile["name"] for profile in self.profiles_data.get("profiles", [])]
        self.profile_combo["values"] = names
        if names and not self.profile_var.get():
            self.profile_var.set(names[0])
        self.on_profile_selected()

    def get_selected_profile(self):
        selected_name = self.profile_var.get()
        for profile in self.profiles_data.get("profiles", []):
            if profile.get("name") == selected_name:
                return profile
        return None

    def on_profile_selected(self):
        self.connected = False
        self.set_actions_enabled(False)
        self.status_var.set("Not connected")
        self.active_profile = self.get_selected_profile()
        self.render_profile_details()

    def render_profile_details(self):
        profile = self.active_profile
        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", "end")
        if not profile:
            self.details_text.insert("end", "No profile selected.")
        else:
            details = [
                f"Project Root: {profile.get('project_root', '')}",
                f"Environment File: {profile.get('env_file', '.env')}",
                f"Maintenance Folder: {profile.get('maintenance_folder', 'database/maintenance')}",
                f"Upload Folder: {profile.get('upload_folder', 'uploads')}",
                f"PostgreSQL Bin: {profile.get('pg_bin') or '(auto-detect)'}",
            ]
            self.details_text.insert("end", "\n".join(details))
        self.details_text.configure(state="disabled")

    def add_profile(self):
        dialog = ProfileDialog(self, "Add Profile")
        if dialog.result:
            self.profiles_data.setdefault("profiles", []).append(dialog.result)
            save_profiles(self.profiles_data)
            self.profile_var.set(dialog.result["name"])
            self.refresh_profiles()

    def edit_profile(self):
        profile = self.get_selected_profile()
        if not profile:
            messagebox.showinfo("No Profile", "Select a profile to edit.")
            return
        dialog = ProfileDialog(self, "Edit Profile", profile)
        if dialog.result:
            profiles = self.profiles_data.setdefault("profiles", [])
            for index, item in enumerate(profiles):
                if item.get("name") == profile.get("name"):
                    profiles[index] = dialog.result
                    break
            save_profiles(self.profiles_data)
            self.profile_var.set(dialog.result["name"])
            self.refresh_profiles()

    def delete_profile(self):
        profile = self.get_selected_profile()
        if not profile:
            return
        if not messagebox.askyesno("Delete Profile", f"Delete profile '{profile['name']}'?"):
            return
        self.profiles_data["profiles"] = [
            item for item in self.profiles_data.get("profiles", [])
            if item.get("name") != profile.get("name")
        ]
        save_profiles(self.profiles_data)
        self.profile_var.set("")
        self.refresh_profiles()

    def connect_profile(self):
        profile = self.get_selected_profile()
        if not profile:
            messagebox.showerror("No Profile", "Add or select a profile first.")
            return

        self.clear_log()
        self.log("Checking selected profile...")
        errors = []

        project_root = Path(profile.get("project_root", ""))
        if not project_root.exists():
            errors.append(f"Project root does not exist: {project_root}")

        env_file = project_root / profile.get("env_file", ".env")
        if not env_file.exists():
            errors.append(f".env file does not exist: {env_file}")

        maintenance_folder = resolve_profile_path(profile, "maintenance_folder", "database/maintenance")
        if not maintenance_folder.exists():
            errors.append(f"Maintenance folder does not exist: {maintenance_folder}")
        else:
            for script_name in REQUIRED_SCRIPTS:
                if not (maintenance_folder / script_name).exists():
                    errors.append(f"Required script missing: {script_name}")

        upload_folder = resolve_profile_path(profile, "upload_folder", "uploads")
        try:
            upload_folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            errors.append(f"Upload folder cannot be created/accessed: {upload_folder} ({exc})")

        pg_bin = profile.get("pg_bin", "")
        self.psql_path = find_tool("psql", pg_bin)
        self.pg_dump_path = find_tool("pg_dump", pg_bin)
        self.pg_restore_path = find_tool("pg_restore", pg_bin)
        if not self.psql_path:
            errors.append("Could not find psql.")
        if not self.pg_dump_path:
            errors.append("Could not find pg_dump.")
        if not self.pg_restore_path:
            errors.append("Could not find pg_restore.")

        if errors:
            for error in errors:
                self.log(f"FAILED: {error}")
            self.status_var.set("Connection failed")
            self.set_actions_enabled(False)
            return

        self.log(f"Project root found: {project_root}")
        self.log(f"Maintenance scripts found: {maintenance_folder}")
        self.log(f"Upload folder ready: {upload_folder}")
        self.log(f"psql: {self.psql_path}")
        self.log(f"pg_dump: {self.pg_dump_path}")
        self.log(f"pg_restore: {self.pg_restore_path}")

        config = get_db_config(profile)
        command = [
            self.psql_path,
            "--host", config["host"],
            "--port", config["port"],
            "--username", config["user"],
            "--dbname", config["database"],
            "--command", "select current_database();",
        ]
        env = os.environ.copy()
        if config.get("password"):
            env["PGPASSWORD"] = config["password"]

        self.log("Testing database connection...")
        result = subprocess.run(command, text=True, capture_output=True, env=env)
        if result.returncode != 0:
            self.log(result.stdout)
            self.log(result.stderr)
            self.status_var.set("Connection failed")
            self.set_actions_enabled(False)
            return

        self.log(result.stdout)
        self.log("Connected successfully.")
        self.connected = True
        self.status_var.set(f"Connected: {config['database']}")
        self.set_actions_enabled(True)

    def set_actions_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for button in self.action_buttons:
            button.configure(state=state)

    def run_script_async(self, label, command, cwd, env=None):
        self.start_log_file(label)
        self.set_actions_enabled(False)
        self.status_var.set(f"Running: {label}")
        self.log(f"Starting {label}")
        self.log(f"Command: {' '.join(str(part) for part in command)}")

        thread = threading.Thread(
            target=self.run_script_worker,
            args=(label, command, cwd, env or os.environ.copy()),
            daemon=True,
        )
        thread.start()

    def run_script_worker(self, label, command, cwd, env):
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            assert process.stdout is not None
            for line in process.stdout:
                self.output_queue.put(("log", line.rstrip()))
            exit_code = process.wait()
            self.output_queue.put(("done", label, exit_code))
        except Exception as exc:
            self.output_queue.put(("error", label, str(exc)))

    def drain_output_queue(self):
        try:
            while True:
                item = self.output_queue.get_nowait()
                if item[0] == "log":
                    self.log(item[1])
                elif item[0] == "done":
                    _kind, label, exit_code = item
                    if exit_code == 0:
                        self.log(f"{label} completed successfully.")
                        self.status_var.set("Connected")
                    else:
                        self.log(f"{label} failed with exit code {exit_code}.")
                        self.status_var.set("Action failed")
                    self.set_actions_enabled(self.connected)
                elif item[0] == "error":
                    _kind, label, error = item
                    self.log(f"{label} failed: {error}")
                    self.status_var.set("Action failed")
                    self.set_actions_enabled(self.connected)
        except queue.Empty:
            pass
        self.after(120, self.drain_output_queue)

    def powershell_command(self, script_name, extra_args=None):
        profile = self.get_selected_profile()
        assert profile is not None
        project_root = Path(profile["project_root"])
        maintenance_folder = resolve_profile_path(profile, "maintenance_folder", "database/maintenance")
        script_path = maintenance_folder / script_name
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
        ]
        if profile.get("pg_bin") and script_name in {
            "backup_all.ps1",
            "restore_all.ps1",
            "backup_database.ps1",
            "restore_database.ps1",
            "rebuild_schema.ps1",
            "load_test_data.ps1",
        }:
            command.extend(["-PgBin", profile["pg_bin"]])
        if extra_args:
            command.extend(extra_args)
        return command, str(project_root)

    def psql_file_command(self, sql_file):
        profile = self.get_selected_profile()
        assert profile is not None
        config = get_db_config(profile)
        project_root = Path(profile["project_root"])
        maintenance_folder = resolve_profile_path(profile, "maintenance_folder", "database/maintenance")
        file_path = maintenance_folder / sql_file
        env = os.environ.copy()
        if config.get("password"):
            env["PGPASSWORD"] = config["password"]
        command = [
            self.psql_path,
            "--host", config["host"],
            "--port", config["port"],
            "--username", config["user"],
            "--dbname", config["database"],
            "--file", str(file_path),
        ]
        return command, str(project_root), env

    def backup_all(self):
        command, cwd = self.powershell_command("backup_all.ps1")
        self.run_script_async("Backup All", command, cwd)

    def restore_all(self):
        stamp = simpledialog.askstring("Restore All", "Enter backup stamp, for example 20260522_183000:")
        if not stamp:
            return
        if not messagebox.askyesno("Confirm Restore", "Restore will replace database contents and upload files. Continue?"):
            return
        command, cwd = self.powershell_command("restore_all.ps1", ["-BackupStamp", stamp, "-Force"])
        self.run_script_async("Restore All", command, cwd)

    def clean_data(self):
        if not messagebox.askyesno("Confirm Clean Data", "Clean transactional defect data but keep setup/configuration?"):
            return
        command, cwd, env = self.psql_file_command("clean_data.sql")
        self.run_script_async("Clean Data", command, cwd, env)

    def reset_database(self):
        message = (
            "Reset Database drops and recreates clean empty app tables.\n\n"
            "No test data will be loaded.\n\n"
            "Continue?"
        )
        if not messagebox.askyesno("Confirm Reset Database", message):
            return
        command, cwd = self.powershell_command("rebuild_schema.ps1", ["-Force"])
        self.run_script_async("Reset Database", command, cwd)

    def load_test_data(self):
        message = (
            "Load Test Data will run seed.sql only if app tables are empty.\n\n"
            "If data already exists, the action will stop and ask you to reset first.\n\n"
            "Continue?"
        )
        if not messagebox.askyesno("Load Test Data", message):
            return
        command, cwd = self.powershell_command("load_test_data.ps1")
        self.run_script_async("Load Test Data", command, cwd)

    def run_smoke_tests(self):
        profile = self.get_selected_profile()
        assert profile is not None
        config = get_db_config(profile)
        project_root = Path(profile["project_root"])
        smoke_path = project_root / "database" / "smoke_tests.sql"
        if not smoke_path.exists():
            messagebox.showerror("Missing Smoke Tests", f"Could not find {smoke_path}")
            return
        env = os.environ.copy()
        if config.get("password"):
            env["PGPASSWORD"] = config["password"]
        command = [
            self.psql_path,
            "--host", config["host"],
            "--port", config["port"],
            "--username", config["user"],
            "--dbname", config["database"],
            "--file", str(smoke_path),
        ]
        self.run_script_async("Smoke Tests", command, str(project_root), env)

    def open_backup_folder(self):
        profile = self.get_selected_profile()
        if not profile:
            return
        project_root = Path(profile["project_root"])
        self.open_path(project_root / "database" / "backups")

    def open_project_folder(self):
        profile = self.get_selected_profile()
        if profile:
            self.open_path(Path(profile["project_root"]))

    def open_path(self, path):
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True) if path.suffix == "" else None
        os.startfile(path)

    def start_log_file(self, label):
        safe_label = "".join(ch if ch.isalnum() else "_" for ch in label.lower()).strip("_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_log_file = LOG_DIR / f"{timestamp}_{safe_label}.log"
        self.current_log_file.write_text(f"{label} started at {timestamp}\n", encoding="utf-8")

    def log(self, message):
        if message is None:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        if self.current_log_file:
            with self.current_log_file.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def clear_log(self):
        self.current_log_file = None
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")


def main():
    ensure_runtime_folders()
    app = MaintenanceConsole()
    app.mainloop()


if __name__ == "__main__":
    main()
