# v0.2.0 — VPS Deployment Guide

Step-by-step plan to run the paper trading loop on a cloud VPS for the 4-week gate.

---

## Prerequisites (before you start)

- [ ] Alpaca paper API keys (from alpaca.markets)
- [ ] GitHub repo access (clone URL)
- [ ] Credit card for VPS provider (~$5–10/month)
- [ ] SSH client (built into Windows 10/11, Mac, Linux)

---

## Phase 1 — Provision the VPS

**This guide uses DigitalOcean as the primary example.** Steps are equivalent for Linode, Hetzner, or Vultr.

### 1.1 Choose a provider

| Provider | Plan | Price | Region |
|----------|------|-------|--------|
| **DigitalOcean** | Basic Droplet, 1 GB RAM | $6/mo | New York (NYC1) |
| Linode | Nanode 1 GB | $5/mo | Newark (US East) |
| Hetzner | CX11 | ~€4/mo | Falkenstein or Ashburn |
| Vultr | Cloud Compute 1 GB | $6/mo | New York |

**Recommendation:** Pick a US East region for lowest latency to Alpaca.

### 1.2 Create the instance (DigitalOcean)

**DigitalOcean — Create Droplet:**

1. Sign up at digitalocean.com
2. Create → Droplets
3. **Image:** Ubuntu 22.04 LTS
4. **Plan:** Basic, $6/mo (1 GB RAM, 1 vCPU, 25 GB SSD)
5. **Datacenter:** New York 1
6. **Authentication:** SSH key (recommended) or password
7. **Hostname:** `trade-swarm-paper` (optional)
8. Create Droplet

### 1.3 Note your IP and SSH in

After creation, you'll get an IP address (e.g. `164.92.xxx.xxx`).

```bash
ssh root@YOUR_VPS_IP
```

If using a password, enter it when prompted. If using an SSH key, it should connect automatically.

---

## Phase 2 — Initial server setup

### 2.1 Update the system

```bash
apt update && apt upgrade -y
```

### 2.2 Create a non-root user (optional but recommended)

```bash
adduser trader
usermod -aG sudo trader
usermod -aG docker trader   # add after Docker is installed
su - trader
```

From here on, use `trader` or `root` — adjust paths accordingly. This guide uses `root` for simplicity.

### 2.3 Set timezone (optional)

```bash
timedatectl set-timezone UTC
# or: timedatectl set-timezone America/New_York
```

---

## Phase 3 — Install dependencies

### 3.1 Install Docker

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker
```

Verify:

```bash
docker --version
```

### 3.2 Install Python 3.10+

```bash
apt install -y python3 python3-pip python3-venv git
python3 --version   # should be 3.10 or higher
```

If Ubuntu 22.04 has Python 3.10, you're good. For 3.11+ on older Ubuntu:

```bash
apt install -y software-properties-common
add-apt-repository ppa:deadsnakes/ppa
apt update
apt install -y python3.11 python3.11-venv python3.11-dev
```

### 3.3 Install tmux (for persistent sessions)

```bash
apt install -y tmux
```

---

## Phase 4 — Deploy the application

### 4.1 Clone the repository

```bash
cd /root   # or /home/trader
git clone https://github.com/bigmikecreates/trade-swarm.git
cd trade-swarm
```

**If the repo is private:** you'll need to authenticate. Options:

- **HTTPS + token:** `git clone https://YOUR_GITHUB_TOKEN@github.com/bigmikecreates/trade-swarm.git`
- **SSH:** Add your SSH key to the server and use `git clone git@github.com:bigmikecreates/trade-swarm.git`

### 4.2 Checkout the v0.2.0 branch

```bash
git checkout release/v0.2.0
```

### 4.3 Create and configure .env

```bash
cp .env.example .env
nano .env
```

Fill in:

```
ALPACA_API_KEY=your_actual_paper_key
ALPACA_SECRET_KEY=your_actual_paper_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets
REDIS_URL=redis://localhost:6379
```

Save and exit (Ctrl+O, Enter, Ctrl+X in nano).

### 4.4 Create virtual environment and install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Verify:

```bash
trade-swarm-paper --help
# or just run it briefly to see the startup message
```

---

## Phase 5 — Start Redis and the trading loop

### 5.1 Start Redis via Docker Compose

```bash
cd /root/trade-swarm   # ensure you're in the project root
docker compose up -d
docker compose ps      # should show redis running
```

### 5.2 Run the trading loop in tmux

**Why tmux:** The loop runs in the foreground. If you disconnect from SSH, the process would die. Tmux keeps it running.

```bash
tmux new -s trading
```

You're now in a tmux session. Run:

```bash
cd /root/trade-swarm
source .venv/bin/activate
trade-swarm-paper
```

You should see:

```
Starting paper trading loop. Symbol: SPY | Equity: $100,000.00
```

**Detach from tmux (leave it running):** Press `Ctrl+B`, then `D`.

**Reattach later to view output:**

```bash
tmux attach -t trading
```

**Stop the loop:** Reattach, then press `Ctrl+C`.

---

## Phase 6 — Run as a systemd service (alternative)

For automatic restarts and no tmux needed:

### 6.1 Create the service file

```bash
nano /etc/systemd/system/trade-swarm-paper.service
```

Paste (adjust paths if you used `trader` user):

```ini
[Unit]
Description=Trade-Swarm Paper Trading Loop
After=network.target docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/trade-swarm
Environment="PATH=/root/trade-swarm/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/root/trade-swarm/.venv/bin/trade-swarm-paper
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 6.2 Enable and start

```bash
systemctl daemon-reload
systemctl enable trade-swarm-paper
systemctl start trade-swarm-paper
systemctl status trade-swarm-paper
```

### 6.3 View logs

```bash
journalctl -u trade-swarm-paper -f
```

### 6.4 Stop the service

```bash
systemctl stop trade-swarm-paper
```

---

## Phase 7 — Kill switch (remote)

To halt trading from your laptop:

### 7.1 SSH in and run the script

```bash
ssh root@YOUR_VPS_IP
cd /root/trade-swarm
source .venv/bin/activate
python scripts/activate_kill_switch.py
```

### 7.2 Or use Redis directly

```bash
ssh root@YOUR_VPS_IP
docker compose -f /root/trade-swarm/docker-compose.yml exec redis redis-cli SET kill_switch 1
```

### 7.3 Reset the kill switch

```bash
docker compose -f /root/trade-swarm/docker-compose.yml exec redis redis-cli DEL kill_switch
```

---

## Phase 8 — Monitoring

### 8.1 Check if the loop is running

**If using tmux:**

```bash
tmux ls
# Should show: trading: 1 windows (created ...)
```

**If using systemd:**

```bash
systemctl status trade-swarm-paper
```

### 8.2 View recent output

**Tmux:** `tmux attach -t trading` (then detach with Ctrl+B, D)

**Systemd:** `journalctl -u trade-swarm-paper -n 100`

### 8.3 Streamlit dashboard (optional)

To view the P&L dashboard from the VPS, you'd need to expose Streamlit. For simplicity, you can:

- **Option A:** Run Streamlit locally and point it at a shared DB (complex)
- **Option B:** Query the SQLite DB over SSH: `scp root@YOUR_VPS_IP:/root/trade-swarm/data/trades.db .` then open locally
- **Option C:** Use Alpaca's web dashboard for positions and P&L

---

## Phase 9 — Updating the code

If you push changes to the repo:

```bash
cd /root/trade-swarm
git pull origin release/v0.2.0
source .venv/bin/activate
pip install -e .

# Restart the loop
# Tmux: reattach, Ctrl+C, run trade-swarm-paper again
# Systemd: systemctl restart trade-swarm-paper
```

---

## Phase 10 — Shutdown and cleanup

When the 4-week gate is complete or you want to stop:

```bash
# Stop the loop (tmux or systemd)
# Stop Redis
cd /root/trade-swarm
docker compose down

# Optionally destroy the VPS from the provider's dashboard
```

---

## Checklist summary

| Step | Action |
|------|--------|
| 1 | Create VPS (Ubuntu 22.04, US region) |
| 2 | SSH in, `apt update && apt upgrade -y` |
| 3 | Install Docker, Python 3.10+, tmux |
| 4 | Clone repo, `git checkout release/v0.2.0` |
| 5 | Copy `.env.example` to `.env`, add Alpaca keys |
| 6 | `python3 -m venv .venv && source .venv/bin/activate && pip install -e .` |
| 7 | `docker compose up -d` |
| 8 | `tmux new -s trading` → `trade-swarm-paper` → Ctrl+B, D |
| 9 | Verify: `tmux attach -t trading` to see output |
| 10 | Check Alpaca paper account for activity during market hours |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: main` | `pip install -e .` again |
| `Redis unavailable` | `docker compose up -d` and check `docker compose ps` |
| `Market closed` for hours | Normal outside 9:30 AM–4 PM ET Mon–Fri |
| No trades after market open | EMA crossover is daily — signals are infrequent; wait for a crossover |
| SSH connection refused | Check firewall; ensure port 22 is open |
| Out of memory | Upgrade to 2 GB plan |
