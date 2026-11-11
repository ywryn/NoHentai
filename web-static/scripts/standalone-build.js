// Mutable data is served by Python/SQLite. Never publish source snapshots,
// overrides or backups as a second source of truth in the web root.
import { rmSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
rmSync(fileURLToPath(new URL('../dist/data', import.meta.url)), { recursive: true, force: true })
