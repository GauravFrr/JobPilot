import os
import sys
import subprocess
from datetime import datetime

def run_backup():
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backup_dir = os.path.abspath(os.path.join(script_dir, "..", "storage_state", "backups"))
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"backup_{timestamp}.sql")
    
    print("Starting database backup...")
    try:
        # Run docker compose exec to dump database
        cmd = ["docker", "compose", "exec", "-T", "postgres", "pg_dump", "-U", "postgres", "-d", "jobpilot"]
        with open(backup_file, "w", encoding="utf-8") as f:
            subprocess.run(cmd, stdout=f, check=True)
        print(f"Database backup saved to: {backup_file}")
        
        # Keep only last 7 backup files
        backups = sorted([
            os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
            if f.startswith("backup_") and f.endswith(".sql")
        ])
        if len(backups) > 7:
            for old_backup in backups[:-7]:
                try:
                    os.remove(old_backup)
                    print(f"Removed old backup: {old_backup}")
                except Exception as ex:
                    print(f"Failed to remove old backup {old_backup}: {str(ex)}")
        print("Backup rotation complete.")
    except Exception as e:
        print(f"Backup failed: {str(e)}")

if __name__ == "__main__":
    run_backup()
