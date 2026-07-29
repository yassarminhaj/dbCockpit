# Database Maintenance Console - dbCockpit

Local desktop utility for running database and upload-file maintenance scripts safely.

This is intentionally separate from the Defect Tracker web app. It can still run when the web app is down, and it can later manage other projects by adding profiles.

## Start

From this folder:

```powershell
python app.py
```

No extra Python package is required. The UI uses standard Tkinter.

## Build Standalone EXE

Install/build with:

```powershell
.\build_exe.ps1 -InstallPyInstaller
```

After PyInstaller is installed once, rebuild with:

```powershell
.\build_exe.ps1
```

Output:

```text
dist/dbCockpit.exe
```

The build also copies editable runtime files beside the exe:

```text
dist/config/profiles.json
dist/logs/
dist/templates/
```

The exe still expects PostgreSQL client tools and the target project maintenance scripts to exist on the machine. It does not bundle PostgreSQL itself.

## Profile Model

Profiles are stored in:

```text
config/profiles.json
```

The repository keeps a sanitized example at:

```text
config/profiles.example.json
```

Runtime `profiles.json` is local-machine configuration and is intentionally not committed.

Each profile points to a project that owns its own maintenance scripts.

Example:

```json
{
  "name": "Defect Tracker Local",
  "database_type": "postgres",
  "project_root": "C:/path/to/your/project",
  "env_file": ".env",
  "maintenance_folder": "database/maintenance",
  "upload_folder": "uploads",
  "pg_bin": "C:/Program Files/PostgreSQL/18/bin"
}
```

The UI can add, edit, and delete profiles.

## Provisioning Another Project

For a new project, create or edit a profile, then click:

```text
Provision Scripts
```

This copies reusable PostgreSQL maintenance scripts into:

```text
<project_root>/database/maintenance
```

It also creates:

```text
<project_root>/database/backups/database
<project_root>/database/backups/files
```

The console does not invent project schema or seed data. The target project should provide:

- `database/schema.sql` for Reset Database
- `database/seed.sql` for Load Test Data
- `database/smoke_tests.sql` for Run Smoke Tests
- `database/maintenance/clean_data.sql` only if it needs custom clean-data behavior

If these files are missing, the related action is disabled after Connect.

## Connect Check

The Connect button validates:

- project root exists
- `.env` exists
- maintenance folder exists
- required scripts exist
- optional project SQL files and action availability
- upload folder exists or can be created
- `psql`, `pg_dump`, and `pg_restore` are available
- database can be reached with `select current_database();`

Maintenance actions stay disabled until Connect succeeds.

## Actions

Primary actions:

- Backup All
- Restore All
- Clean Data
- Reset Database
- Load Test Data
- Run Smoke Tests

Helpers:

- Open Backup Folder
- Open Project Folder
- Open Log Folder

## Safety

- Restore, clean, and reset require confirmation.
- Restore All uses a backup stamp so DB and uploaded files come from the same backup set.
- Reset Database drops and recreates empty tables. It does not load seed data.
- Load Test Data runs the seed script only when app tables are empty.
- Output is shown in the UI and written under `logs/`.

## Reuse For Another Project

Add another profile that points to a different project root and maintenance folder.

Then use Provision Scripts to copy reusable maintenance scripts into that project.

The console orchestrates scripts. It does not duplicate project-specific database logic.
