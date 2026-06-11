IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[data_library_runs]') AND type in (N'U'))
BEGIN
    CREATE TABLE data_library_runs (
        id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
        source VARCHAR(50) NOT NULL,
        run_date DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        status VARCHAR(20) NOT NULL,
        records_extracted INT DEFAULT 0,
        error_message NVARCHAR(MAX),
        created_at DATETIMEOFFSET DEFAULT SYSDATETIMEOFFSET()
    );
    CREATE INDEX idx_data_library_runs_source ON data_library_runs(source);
    CREATE INDEX idx_data_library_runs_date   ON data_library_runs(run_date DESC);
END
