#!/usr/bin/env bash
# Provision WSL Ubuntu with the recon toolchain for JARVIS/Ultron HackingTool fleet.
set -u
export DEBIAN_FRONTEND=noninteractive
export PATH="$PATH:/usr/local/go/bin:/root/go/bin"

echo "=== apt tool presence ==="
for t in nmap ffuf gobuster wafw00f whatweb dnsrecon go git curl jq; do
  printf '%-10s ' "$t"; command -v "$t" || echo MISSING
done

echo
echo "=== installing ProjectDiscovery Go tools (subfinder httpx nuclei katana dnsx) ==="
export GOBIN=/usr/local/bin
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest 2>&1 | tail -1
go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest           2>&1 | tail -1
go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest      2>&1 | tail -1
go install -v github.com/projectdiscovery/katana/cmd/katana@latest         2>&1 | tail -1
go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest             2>&1 | tail -1

echo
echo "=== final toolchain ==="
for t in nmap ffuf gobuster wafw00f whatweb dnsrecon subfinder httpx nuclei katana dnsx; do
  printf '%-10s ' "$t"; command -v "$t" || echo MISSING
done
