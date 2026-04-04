# Read Replicas — Deployment Guide

## Overview

ScientificState supports read replicas for horizontal scaling of query-heavy
workloads. This document covers the architecture, configuration, and
operational procedures for deploying read replicas.

## Architecture

```
                    +-----------------+
                    |  Primary (RW)   |
                    |  Supabase DB    |
                    +--------+--------+
                             |
              +--------------+--------------+
              |              |              |
     +--------v---+  +------v-----+  +-----v------+
     | Replica A   |  | Replica B  |  | Replica C  |
     | (read-only) |  | (read-only)|  | (read-only)|
     +-------------+  +------------+  +------------+
```

### Write Path
All writes go to the primary Supabase instance:
- SSV INSERT/UPDATE operations
- `audit_log` INSERT (immutable)
- `qpu_usage_log` INSERT (immutable)
- `qpu_price_snapshots` INSERT (immutable)
- Replication request lifecycle updates

### Read Path
Read replicas serve:
- SSV queries and search
- Replication verification reads
- Dashboard and analytics queries
- Federation discovery reads

## Configuration

### Supabase Read Replicas

Supabase Pro plan supports read replicas natively. Configure via the
Supabase dashboard or CLI:

```bash
# Enable read replicas (Supabase Pro required)
supabase db replicas create --region us-east-1
supabase db replicas create --region eu-west-1
```

### Daemon Configuration

The daemon connects to replicas via environment variables:

```env
# Primary (read-write)
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=<anon-key>

# Read replicas (optional)
SUPABASE_READ_REPLICA_URLS=https://<replica-1>.supabase.co,https://<replica-2>.supabase.co
```

### Connection Routing

The daemon routes connections based on query type:

| Operation | Target | Fallback |
|-----------|--------|----------|
| INSERT / UPDATE / DELETE | Primary | Error (no fallback) |
| SELECT (fresh data needed) | Primary | Replica with lag check |
| SELECT (analytics / search) | Replica | Primary |
| SELECT (replication verify) | Primary | Error (consistency required) |

## Replication Lag Monitoring

### Acceptable Lag Thresholds

| Workload | Max Acceptable Lag | Action on Breach |
|----------|--------------------|------------------|
| Analytics queries | 60 seconds | Log warning |
| SSV search | 10 seconds | Route to primary |
| Replication verification | 0 seconds | Always use primary |
| Federation discovery | 30 seconds | Log warning |

### Monitoring Queries

```sql
-- Check replication lag (PostgreSQL)
SELECT
    application_name,
    client_addr,
    sent_lsn,
    write_lsn,
    flush_lsn,
    replay_lsn,
    (sent_lsn - replay_lsn) AS replication_lag
FROM pg_stat_replication;
```

### Health Check Integration

The daemon `/health` endpoint includes replica status when replicas are
configured:

```json
{
    "status": "ok",
    "replicas": {
        "count": 2,
        "healthy": 2,
        "lag_seconds": {"replica-1": 0.5, "replica-2": 1.2}
    }
}
```

## Local Development (SQLite)

For local development, the daemon uses SQLite with WAL mode, which provides
a form of read concurrency:

```python
# WAL mode enables concurrent reads during writes
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
```

No replica configuration is needed for local development.

## Failover Procedures

### Replica Failure

1. Daemon detects replica health check failure
2. Affected replica removed from connection pool
3. Queries routed to remaining replicas or primary
4. Alert triggered via monitoring pipeline

### Primary Failure

1. Supabase handles automatic failover to standby
2. Daemon reconnects with exponential backoff
3. Read replicas continue serving read queries during failover
4. Write operations queue and retry after failover completes

## Capacity Planning

### Recommended Replica Count

| Institution Size | Users | Replicas | Regions |
|-----------------|-------|----------|---------|
| Small lab | < 10 | 0 | 1 |
| Department | 10-50 | 1 | 1 |
| University | 50-500 | 2 | 1-2 |
| Multi-institution | 500+ | 3+ | 2+ |

### Scaling Triggers

Add a replica when:
- Read query latency p95 exceeds 500ms
- Primary CPU utilization sustained above 70%
- Cross-region users experience latency above 200ms

---
*Part of ScientificState Phase 8 — Enterprise Scale + Compliance*
