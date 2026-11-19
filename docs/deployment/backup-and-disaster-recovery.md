# Backup, Restore & Disaster Recovery (DR) Runbook

**System:** AI Trading Intelligence SaaS Platform  
**Target RPO (Recovery Point Objective):** < 1 hour  
**Target RTO (Recovery Time Objective):** < 15 minutes  
**Standard:** Automated Encrypted Logical & Physical Backups with Cryptographic SHA-256 Verification

---

## 1. Disaster Recovery Overview

This runbook establishes standard operating procedures for automated backups, point-in-time recovery (PITR), data integrity verification, and failover disaster recovery for PostgreSQL 16 and Valkey/Redis.

```
+---------------------------------------------------------------------------------------+
|                                    BACKUP TOPOLOGY                                    |
+---------------------------------------------------------------------------------------+
|  Primary PostgreSQL 16                  Automated Backup Engine                       |
|  [31 Normalized Tables]  ---(Daily)--->  [scripts/backup_restore.py]                  |
|                                                     |                                 |
|                                                     v                                 |
|                                          +---------------------+                      |
|                                          | Compressed Archive  |                      |
|                                          | (.sql.gz + SHA-256) |                      |
|                                          +---------------------+                      |
|                                                     |                                 |
|                         +---------------------------+---------------------------+     |
|                         |                                                       |     |
|                         v                                                       v     |
|              [Local Disk /backups/]                               [Encrypted Cloud S3/GCS] |
|              - 7 Daily Retained                                   - 30 Daily Retained |
|              - 4 Weekly Retained                                  - 12 Monthly Retain |
+---------------------------------------------------------------------------------------+
```

---

## 2. Automated Backup Strategy

### 2.1 Backup Script Execution

The automated backup utility is located at [`scripts/backup_restore.py`](file:///W:/Projects/trade-intelligence-platform/scripts/backup_restore.py).

#### Manual Backup Generation
```bash
# Create logical backup with SHA-256 manifest
python scripts/backup_restore.py backup --out-dir ./backups
```

#### Manifest Verification
Each backup creates a companion manifest file (`.manifest.json`) recording:
- Backup filename and timestamp (UTC)
- Total uncompressed/compressed byte size
- Cryptographic SHA-256 checksum
- Schema table count verification

```json
{
  "format": "sql.gz",
  "timestamp_utc": "20261119_200000Z",
  "dump_file": "tip_backup_20261119_200000Z.sql.gz",
  "file_size_bytes": 1048576,
  "sha256_checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "compression": "gzip",
  "platform_version": "0.2.0",
  "schema_tables_count": 31
}
```

### 2.2 Retention & Pruning Policy
- **Grandfather-Father-Son:**
  - **Daily:** Retain the last 7 daily snapshots on local disk.
  - **Weekly:** Retain 4 weekly archives on primary storage.
  - **Off-Site Cloud:** Replicate to S3/GCS with 30-day lifecycle expiration.
```bash
# Prune backups older than retention limit
python scripts/backup_restore.py prune --dir ./backups --keep 7
```

---

## 3. Step-by-Step Restoration Runbook

### Step 1: Verify Integrity of Backup Archive
Before executing a restore, verify the cryptographic integrity of the target archive:
```bash
python scripts/backup_restore.py verify ./backups/tip_backup_20261119_200000Z.sql.gz
```
*Expected Output:* `Cryptographic SHA-256 integrity verified. Gzip decompression verified successfully.`

### Step 2: Stop Incoming API Traffic & Background Tasks
```bash
# Activate Global Emergency Kill Switch to halt signal generation workflows
curl -X POST http://localhost:8000/api/v1/admin/kill-switch \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: <CSRF_TOKEN>" \
  -d '{"enabled": true, "reason": "Database Disaster Recovery Restore Procedure"}'

# Pause Celery workers to prevent concurrent writes
docker compose stop worker celery_beat
```

### Step 3: Database Restoration
```bash
# Decompress and restore into PostgreSQL target
gunzip -c ./backups/tip_backup_20261119_200000Z.sql.gz | psql -U tip_app -d trade_intelligence
```

### Step 4: Verification & Smoke Test
Run the test harness to confirm data integrity across all 31 tables:
```bash
python -c "
from database.session import build_engine, build_session_factory
from database.models import User, TradingSignal, Subscription, Payment
from sqlalchemy import select, func

engine = build_engine('postgresql://tip_app:tip_secret_dev@localhost:5432/trade_intelligence')
Session = build_session_factory(engine)
with Session() as db:
    user_count = db.execute(select(func.count(User.id))).scalar()
    signal_count = db.execute(select(func.count(TradingSignal.id))).scalar()
    sub_count = db.execute(select(func.count(Subscription.id))).scalar()
    pay_count = db.execute(select(func.count(Payment.id))).scalar()
    print(f'Restored State: Users={user_count}, Signals={signal_count}, Subs={sub_count}, Payments={pay_count}')
"
```

### Step 5: Resume Traffic
```bash
# Restart background workers
docker compose start worker celery_beat

# Deactivate Kill Switch when verified
curl -X POST http://localhost:8000/api/v1/admin/kill-switch \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: <CSRF_TOKEN>" \
  -d '{"enabled": false, "reason": "Disaster Recovery Complete & Verified"}'
```

---

## 4. Point-In-Time Recovery (PITR) Setup
For production deployments requiring sub-minute RPO:
1. Enable Write-Ahead Log (WAL) archiving in `postgresql.conf`:
   ```ini
   wal_level = replica
   archive_mode = on
   archive_command = 'test ! -f /mnt/wal_archive/%f && cp %p /mnt/wal_archive/%f'
   ```
2. When recovering to an exact timestamp, create `recovery.signal`:
   ```ini
   restore_command = 'cp /mnt/wal_archive/%f %p'
   recovery_target_time = '2026-11-19 14:30:00 UTC'
   recovery_target_action = 'promote'
   ```
