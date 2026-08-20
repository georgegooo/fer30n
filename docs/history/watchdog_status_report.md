# Watchdog Status Report

- States implemented: **HEALTHY / DEGRADED / CRITICAL**
- Capabilities: **AUTO_RESTART, CONNECTION_RECOVERY, CRASH_RECOVERY, PROCESS_RESURRECTION, RAM_MONITORING, MEMORY_LEAK_DETECTION, LOOP_FREEZE_DETECTION, DEGRADATION_TRACKING**
- Monitor keys: **ai_memory_healthy, ai_memory_rows, cpu_ok, cpu_percent, database, db_latency_ms, disk_ok, feed_ok, historical_degradation, loop_frozen, loop_latency_sec, memory, mt5, process_alive, ram_ok, ram_percent, rss_growth_mb, rss_mb, telegram, telegram_latency_ms**

## Added coverage

- RAM monitoring
- Memory leak detection
- Loop freeze detection
- CPU spikes
- AI Memory health
- Database health + latency
- Telegram health + latency
- Historical degradation tracking
