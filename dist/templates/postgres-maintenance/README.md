# Generic PostgreSQL Maintenance Scripts

These scripts are provisioned by dbCockpit.

Expected project files:

- `database/schema.sql` for Reset Database
- `database/seed.sql` for Load Test Data
- `database/smoke_tests.sql` for Smoke Tests
- `database/maintenance/clean_data.sql` only if the project wants custom clean-data behavior

Normal operations should be driven from dbCockpit.
