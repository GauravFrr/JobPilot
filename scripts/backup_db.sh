#!/bin/bash
set -e

# Define directories relative to script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${SCRIPT_DIR}/../storage_state/backups"

mkdir -p "${BACKUP_DIR}"

TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.sql.gz"

echo "Starting database backup..."

# Run pg_dump within the postgres container and compress it
# Use -T to disable pseudo-TTY allocation for script execution
docker compose exec -T postgres pg_dump -U postgres -d jobpilot | gzip > "${BACKUP_FILE}"

echo "Database backup saved to: ${BACKUP_FILE}"

# Keep only the last 7 backups, delete older ones
echo "Cleaning up backups older than 7 days..."
find "${BACKUP_DIR}" -name "backup_*.sql.gz" -type f -mtime +7 -delete

echo "Backup rotation complete."
