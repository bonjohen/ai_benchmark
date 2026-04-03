  Phase 6: Deploy, Reset, Backfill
                                                                                                                                                                                                                                                                                   
  Pre-flight: Push & Upgrade (from C:\Projects\ai_benchmark)                                                                                                                                                                                                                       

  # 1. Push code
  git push origin feature/data-pipeline-only

  # 2. Deploy via installer
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/installer/Update-Instance.ps1 -Name ai-data-pipeline

  # 3. Verify new scripts landed
  ls C:\ai-data-pipeline\bin\weekly_report.bat
  ls C:\ai-data-pipeline\bin\report_range.ps1

  Database Reset (from C:\ai-data-pipeline)

  cd C:\ai-data-pipeline

  # 4. Safety export
  .\venv\Scripts\python.exe -m ai_benchmark export --format json --limit 99999 --output artifacts\pre_wipe_events.json

  # 5. Delete the database
  del data\ai_benchmark.db

  # 6. Recreate empty schema
  .\venv\Scripts\python.exe -m ai_benchmark init-db

  Backfill Collection (from C:\ai-data-pipeline)

  # 7. Backfill events — output captured to log file
  #    Feb 15–Mar 3 may be sparse (Google News 30-day limit)
  .\venv\Scripts\python.exe -m ai_benchmark collect --since 2026-02-15 > logs\backfill.log 2>&1

  # Monitor progress in a second terminal:
  Get-Content C:\ai-data-pipeline\logs\backfill.log -Wait

  Batch Reports (from C:\ai-data-pipeline)

  # 8. Stage 1 — extract daily JSON for every date (fast, ~5 seconds)
  .\venv\Scripts\python.exe -m ai_benchmark report-range --since 2026-02-15 --output-dir artifacts

  # 9. Stage 2 — Claude CLI summarization per date (slow, one call per day)
  #    Skips dates where daily_report_YYYYMMDD.md already exists
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File bin\report_range.ps1 -Since 2026-02-15

  Weekly Reports (from C:\ai-data-pipeline)

  # 10. Generate weekly reports — use the Sunday that ends each week
  bin\weekly_report.bat 2026-02-23
  bin\weekly_report.bat 2026-03-02
  bin\weekly_report.bat 2026-03-09
  bin\weekly_report.bat 2026-03-16
  bin\weekly_report.bat 2026-03-23
  bin\weekly_report.bat 2026-03-30

  ---
  Watch for:
  - Step 7 is the longest — wait for it to finish before step 8. Tail the log with Get-Content logs\backfill.log -Wait.
  - Step 9 makes one Claude CLI call per date (~47 calls) — retries once on failure then skips
  - Step 10 warns if daily reports are missing for a given week — expected for early weeks with sparse RSS data