# NyayaGPT backend — deployment runbook

This is a one-time setup. After this, every merge to `main` auto-deploys via
`.github/workflows/ci-cd.yml`.

## 0. Prerequisites
- A server with SSH access (Oracle Cloud Ampere A1, or your existing EC2 box
  — the steps are the same either way).
- `nyayagpt.in` DNS already pointed at Vercel for the frontend (unchanged).
  This runbook only adds an `api.nyayagpt.in` record for the backend.

## 1. One-time server setup

SSH into the server, then:

```bash
sudo apt update && sudo apt install -y python3.11-venv nginx certbot python3-certbot-nginx

git clone https://github.com/naitik120gupta/nyayagpt.git
cd nyayagpt

python3.11 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# backend/.env — same values you used on EC2
cat > backend/.env <<'EOF'
GEMINI_API_KEY=your_key_here
EOF
```

The vector store (`backend/vector_store/chroma.sqlite3`) is already committed
to the repo, so there's nothing to build here — it comes with the clone.

## 2. systemd service

```bash
sudo cp deploy/nyayagpt-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nyayagpt-backend
sudo systemctl status nyayagpt-backend   # should show "active (running)"
```

## 3. Nginx + HTTPS

```bash
sudo cp deploy/nginx-nyayagpt.conf /etc/nginx/sites-available/nyayagpt
sudo ln -s /etc/nginx/sites-available/nyayagpt /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

sudo certbot --nginx -d api.nyayagpt.in
```

certbot auto-renews via a systemd timer it installs — no cron job needed.

## 4. DNS

At your domain registrar, add:

| Type | Host | Value            |
|------|------|-------------------|
| A    | api  | <server public IP> |

Propagation is usually under an hour. Confirm with:

```bash
curl -I https://api.nyayagpt.in/docs
```

## 5. Point the frontend at the new backend

In the Vercel project (or wherever the frontend reads its API base URL
from), set it to `https://api.nyayagpt.in` and redeploy. The frontend on
Vercel already auto-deploys on push — no workflow needed for that side.

## 6. GitHub secrets (for auto-deploy)

In the repo → Settings → Secrets and variables → Actions, add:

| Secret            | Value                                              |
|--------------------|----------------------------------------------------|
| `DEPLOY_HOST`      | server public IP                                   |
| `DEPLOY_USER`      | SSH user (e.g. `ubuntu`)                            |
| `DEPLOY_SSH_KEY`   | private key with access to that server (see below)  |
| `DEPLOY_PATH`      | `/home/ubuntu/nyayagpt`                             |

Generate a deploy-only key pair (don't reuse your personal SSH key):

```bash
ssh-keygen -t ed25519 -f nyayagpt_deploy_key -N ""
# copy nyayagpt_deploy_key.pub to the server's ~/.ssh/authorized_keys
# paste the CONTENTS of nyayagpt_deploy_key (the private half) into
# the DEPLOY_SSH_KEY secret
```

Also make sure the deploy user can restart the service without a password
prompt:

```bash
echo "ubuntu ALL=NOPASSWD: /bin/systemctl restart nyayagpt-backend" | sudo tee /etc/sudoers.d/nyayagpt-deploy
```

## After this is done

Every push to `main` that passes tests will:
1. `git reset --hard origin/main` on the server
2. reinstall requirements (fast — pip skips unchanged packages)
3. restart the systemd service
4. hit `/docs` to confirm it came back up

If a deploy ever breaks the live service, SSH in and check:
```bash
sudo systemctl status nyayagpt-backend
sudo journalctl -u nyayagpt-backend -n 100 --no-pager
```