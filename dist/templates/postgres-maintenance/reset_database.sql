-- Generic PostgreSQL project reset.
--
-- Drops all ordinary tables in the public schema.
-- Recreate structure by running the project's database/schema.sql after this.

BEGIN;

DO $$
DECLARE
    table_record record;
BEGIN
    FOR table_record IN
        SELECT schemaname, tablename
        FROM pg_tables
        WHERE schemaname = 'public'
    LOOP
        EXECUTE format(
            'DROP TABLE IF EXISTS %I.%I CASCADE',
            table_record.schemaname,
            table_record.tablename
        );
    END LOOP;
END $$;

COMMIT;
