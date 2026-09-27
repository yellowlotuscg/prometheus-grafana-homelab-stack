"""Static homelab validation, not a substitute for promtool or live checks."""
import argparse
import json
from pathlib import Path
import re
import urllib.request

import yaml

ROOT = Path(__file__).resolve().parents[1]
METRICS = {
    "node_cpu_seconds_total", "node_memory_MemAvailable_bytes",
    "node_memory_MemTotal_bytes", "node_filesystem_avail_bytes",
    "node_filesystem_size_bytes", "node_network_receive_bytes_total",
    "node_network_transmit_bytes_total",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-upstream", action="store_true")
    args = parser.parse_args()
    configs = {}
    for path in ROOT.rglob("*.yml"):
        if ".venv" in path.parts:
            continue
        configs[str(path.relative_to(ROOT))] = yaml.safe_load(path.read_text())
    config = configs["prometheus/prometheus.yml"]
    assert {job["job_name"] for job in config["scrape_configs"]} == {"prometheus", "node-exporter"}
    assert config["rule_files"] == ["/etc/prometheus/alerts.yml"]
    rules = [rule for group in configs["prometheus/alerts.yml"]["groups"] for rule in group["rules"]]
    assert len(rules) >= 5
    assert len({rule["alert"] for rule in rules}) == len(rules)
    runbook = (ROOT / "runbook.md").read_text()
    for rule in rules:
        assert re.fullmatch(r"[a-zA-Z_:][a-zA-Z0-9_:]*", rule["alert"])
        assert isinstance(rule["expr"], str) and rule["expr"].strip()
        assert re.fullmatch(r"[1-9][0-9]*[smhd]", rule["for"])
        assert rule["labels"]["severity"] in {"warning", "critical"}
        assert all(rule["annotations"].get(key) for key in ("summary", "description", "runbook_url"))
        assert "## " + rule["alert"] in runbook
    dashboard = json.loads((ROOT / "grafana/provisioning/dashboards/host-overview.json").read_text())
    metrics = set()
    for panel in dashboard["panels"]:
        assert panel["datasource"]["uid"] == "prometheus"
        for target in panel["targets"]:
            metrics.update(re.findall(r"\bnode_[a-zA-Z0-9_]+", target["expr"]))
    assert metrics == METRICS, metrics
    datasource = configs["grafana/provisioning/datasources/prometheus.yml"]["datasources"][0]
    assert datasource["uid"] == "prometheus"
    assert datasource["url"] == "http://prometheus:9090"
    compose = configs["docker-compose.yml"]
    assert set(compose["services"]) == {"prometheus", "grafana", "node-exporter", "alertmanager"}
    for service in compose["services"].values():
        assert re.search(r":v?\d+\.\d+\.\d+$", service["image"])
        assert all(port.startswith("127.0.0.1:") for port in service.get("ports", []))
    for path in ROOT.rglob("*"):
        if path.is_file() and not any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            assert chr(0x2014) not in path.read_text(), path
    print(f"PASS: {len(configs)} YAML files, {len(rules)} alert schemas/runbook entries, {len(dashboard['panels'])} panels, {len(metrics)} metric names, pinned images, loopback bindings, no em dashes")
    if args.check_upstream:
        base = "https://raw.githubusercontent.com/prometheus/node_exporter/v1.9.1/collector/"

        def fetch(path):
            with urllib.request.urlopen(base + path, timeout=30) as response:
                return response.read().decode()

        text = fetch("fixtures/e2e-output.txt")
        exposed = set(re.findall(r"^# TYPE (\w+) ", text, re.MULTILINE))
        # Upstream's end-to-end fixture omits some host-dependent metrics.
        # Confirm those names from the pinned collector descriptors instead.
        filesystem = fetch("filesystem_common.go")
        assert 'const subsystem = "filesystem"' in filesystem
        exposed.update("node_filesystem_" + name for name in re.findall(
            r'BuildFQName\(namespace, subsystem, "(\w+)"\)', filesystem))
        memory = fetch("meminfo.go")
        assert 'memInfoSubsystem = "memory"' in memory
        assert 'BuildFQName(namespace, memInfoSubsystem, k)' in memory
        exposed.update("node_memory_" + name for name in re.findall(
            r'metrics\["(\w+)"\]', fetch("meminfo_linux.go")))
        assert metrics <= exposed, metrics - exposed
        assert "node_filesystem_readonly" in exposed
        print("PASS: all panel metric names and filesystem readonly metric verified against pinned upstream fixture/collector source: " + base)
    print("LIMIT: PromQL semantics and live operation require promtool and a running stack.")


if __name__ == "__main__":
    main()
