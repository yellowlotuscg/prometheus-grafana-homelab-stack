# Homelab alert runbook

These procedures apply only to this portfolio lab. Confirm the affected instance and time range before acting. Prometheus Alerts and Targets pages are at localhost:9090; Grafana is at localhost:3000. Do not generate memory pressure or fill a real disk merely to demonstrate an alert.

## InstanceDown

Meaning: a configured scrape endpoint has returned `up == 0` for one minute. Confirm the instance/job labels at `/alerts`, examine `/targets` for the scrape error, and run `docker compose ps -a` and `docker compose logs node-exporter` (or the named affected service). For the deliberate demo, restore with `docker compose start node-exporter`; otherwise fix the observed process, DNS, port or configuration problem, then confirm `up == 1` and the alert resolves. This does not detect a fully stopped Prometheus without a separate external monitor.

## HighCPU

Meaning: average non-idle CPU exceeds 85% for five minutes, using a five-minute rate of `node_cpu_seconds_total`. Confirm the CPU panel and evaluate `100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{job="node-exporter",mode="idle"}[5m])))` in Prometheus; inspect `docker stats` and host process activity, using Linux VM context on Docker Desktop. Stop only an identified disposable lab workload or reduce its concurrency; investigate I/O wait as well as compute because this query includes both, then wait for the rolling rate and hold period to clear. Do not kill unrelated processes.

## HighMemory

Meaning: memory usage calculated from MemAvailable exceeds 90% for five minutes. Confirm the memory panel and `node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes`, then inspect `docker stats` and Linux `free -h` on the monitored host for pressure or a growing workload. Reduce the identified lab workload, investigate memory growth, or intentionally adjust the VM's memory allocation after considering the physical host's capacity. Do not mistake filesystem cache alone for exhausted memory; MemAvailable accounts for reclaimable memory. Confirm available memory recovers and the alert clears.

## DiskFilling

Meaning: a writable, non-pseudo filesystem has less than 15% available space for ten minutes. Confirm the instance, device and mountpoint labels, the Grafana filesystem panel, and `df -h` on the monitored Linux host; use `docker system df` to inspect Docker consumption without deleting anything. Identify growth and apply retention or remove only explicitly approved disposable lab data; do not blindly prune volumes or logs. Expand storage if appropriate and verify free space stays above the threshold. The alert is threshold-based, not a prediction, and Docker Desktop readings refer to its VM filesystems.

## NodeExporterScrapeMissing

Meaning: Prometheus has no `up{job="node-exporter"}` series for two minutes, usually because the scrape job or targets vanished. Confirm `absent(up{job="node-exporter"})` returns 1, inspect `/targets` and the active configuration at `/status`, and compare it with `prometheus/prometheus.yml`. Restore the expected job name and `node-exporter:9100` target, validate configuration, then run `docker compose restart prometheus` and verify the series returns. This is intentionally different from a failed scrape, which retains `up=0` and triggers InstanceDown. This missing-series rule checks the entire job, not individual targets in a larger multi-host inventory.
