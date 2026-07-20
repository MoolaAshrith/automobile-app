# AutoForge — Complete Deployment Guide (AWS Free Tier)
## Automobile Manufacturing App | Docker + ECR + Terraform + GitHub Actions

---

## What You Are Building

A real-world DevOps project that showcases:
- A Flask web app (automobile manufacturing dashboard) running inside Docker containers
- MySQL database also running as a container (no RDS — free tier friendly)
- Docker images stored in Amazon ECR (private registry)
- AWS infrastructure created automatically by Terraform
- Fully automated CI/CD pipeline via GitHub Actions (6 jobs)

```
You push code to GitHub
       ↓
GitHub Actions runs automatically
       ↓
Job 1: Lint + test your Python code
Job 2: Build Docker image
Job 3: Push image to Amazon ECR
Job 4: Terraform creates EC2 on AWS
Job 5: You approve the deployment (manual gate)
Job 6: SSH into EC2, pull image, start containers
       ↓
App is live at http://YOUR_EC2_IP
```

---

## Free Tier Resources Used   -------

| AWS Resource     | Free Tier Limit          | What We Use      |
|------------------|--------------------------|------------------|
| EC2 t2.micro     | 750 hours/month          | 1 instance       |
| EBS gp2 storage  | 30 GB/month              | 20 GB            |
| ECR              | 500 MB/month free        | ~150 MB          |
| S3               | 5 GB storage             | <1 MB (tfstate)  |
| DynamoDB         | 25 GB + 25 WCU free      | <1 MB            |

**Estimated cost: $0/month if within first 12 months of AWS account.**
ECR has a small charge after 500MB — our 5-image policy keeps it under.

---

## Tools to Install on Your Windows Machine

Install these before starting. Open each link, download, and install.

### 1. Git
Download: https://git-scm.com/download/win
- During install: choose "Use Git from command line and also from 3rd-party software"
- Everything else: keep defaults

Verify in PowerShell:
```powershell
git --version
# Expected: git version 2.x.x
```

### 2. AWS CLI v2
Download: https://aws.amazon.com/cli/
- Download the `.msi` installer
- Run it, keep all defaults

Verify:
```powershell
aws --version
# Expected: aws-cli/2.x.x Python/3.x.x Windows/...
```

### 3. Terraform
Download: https://developer.hashicorp.com/terraform/install
- Select Windows AMD64
- Download the zip
- Extract `terraform.exe`
- Move it to `C:\terraform\`
- Add `C:\terraform` to your Windows PATH:
  - Search "Environment Variables" in Start
  - System Properties → Environment Variables
  - Under System Variables, find Path → Edit → New → type `C:\terraform`
  - Click OK on all dialogs

Verify (open a new PowerShell window):
```powershell
terraform --version
# Expected: Terraform v1.x.x
```

---

## PHASE 1 — AWS Account Setup
### (Do this once. Takes about 15 minutes.)

---

### Step 1.1 — Log into AWS Console

Go to: https://console.aws.amazon.com
Sign in with your root account email and password.

**Important:** In the top-right corner, make sure the region is set to:
`Asia Pacific (Mumbai) — ap-south-1`

Click the region dropdown and select Mumbai if it isn't already selected.

---

### Step 1.2 — Create an IAM User for GitHub Actions

**Why?** GitHub Actions needs AWS credentials to push Docker images to ECR, run
Terraform, and deploy to EC2. We create a dedicated IAM user for this — we never
use our root account credentials in pipelines.

1. In the AWS Console search bar, type **IAM** and click it
2. In the left sidebar, click **Users**
3. Click **Create user** (top right)
4. Username: `github-actions-user`
5. Click **Next**
6. Select **Attach policies directly**
7. In the search box, search and tick each of these 5 policies:
   - `AmazonEC2FullAccess`
   - `AmazonEC2ContainerRegistryFullAccess`
   - `AmazonS3FullAccess`
   - `AmazonDynamoDBFullAccess`
   - `IAMFullAccess`
8. Click **Next** → **Create user**
9. Click on the user you just created (`github-actions-user`)
10. Go to the **Security credentials** tab
11. Scroll down to **Access keys** → click **Create access key**
12. Use case: select **Command Line Interface (CLI)** → tick the confirmation checkbox
13. Click **Next** → **Create access key**
14. **CRITICAL: Copy both values now and save them in Notepad:**
    - Access key ID (looks like: `AKIAIOSFODNN7EXAMPLE`)
    - Secret access key (looks like: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`)
15. Click **Done**

---

### Step 1.3 — Configure AWS CLI on Your Machine

**Why?** This lets you run AWS commands from PowerShell. It stores your credentials
locally so Terraform can also use them when you run it from your machine.

Open PowerShell and run:
```powershell
aws configure
```

Enter these when prompted (press Enter after each):
```
AWS Access Key ID [None]: PASTE_YOUR_ACCESS_KEY_ID
AWS Secret Access Key [None]: PASTE_YOUR_SECRET_ACCESS_KEY
Default region name [None]: ap-south-1
Default output format [None]: json
```

Verify it works:
```powershell
aws sts get-caller-identity
```

Expected output (your values will differ):
```json
{
    "UserId": "AIDAIOSFODNN7EXAMPLE",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/github-actions-user"
}
```

**Save your Account number (12 digits) — you will need it for GitHub secrets.**

---

### Step 1.4 — Create S3 Bucket for Terraform State

**Why?** Terraform needs to store a "state file" that tracks what resources it has
created. We store this in S3 so the GitHub Actions pipeline can also access it.
Without this, Terraform would not know that EC2 already exists on the next run.

Run in PowerShell:
```powershell
aws s3api create-bucket `
  --bucket automobile-tfstate-bucket `
  --region ap-south-1 `
  --create-bucket-configuration LocationConstraint=ap-south-1
```

Expected output:
```json
{
    "Location": "http://automobile-tfstate-bucket.s3.amazonaws.com/"
}
```

Enable versioning on the bucket (lets you recover old state files):
```powershell
aws s3api put-bucket-versioning `
  --bucket automobile-tfstate-bucket `
  --versioning-configuration Status=Enabled
```

No output = success.

---

### Step 1.5 — Create DynamoDB Table for State Locking

**Why?** When two pipeline runs happen at the same time, both might try to modify
the Terraform state file simultaneously and corrupt it. DynamoDB acts as a lock —
only one run can modify state at a time.

```powershell
aws dynamodb create-table `
  --table-name automobile-tfstate-lock `
  --attribute-definitions AttributeName=LockID,AttributeType=S `
  --key-schema AttributeName=LockID,KeyType=HASH `
  --billing-mode PAY_PER_REQUEST `
  --region ap-south-1
```

Expected output: a large JSON block with `"TableStatus": "CREATING"`. That is fine.

---

### Step 1.6 — Create EC2 Key Pair

**Why?** To SSH into your EC2 instance, you need a key pair. The key pair has two
parts: AWS keeps the public key, you keep the private key (.pem file). The GitHub
Actions pipeline uses this private key to SSH in and deploy.

```powershell
# Create the .ssh directory if it doesn't exist
New-Item -ItemType Directory -Force -Path "$HOME\.ssh"

# Create the key pair and save the private key
aws ec2 create-key-pair `
  --key-name automobile-app-key `
  --region ap-south-1 `
  --query "KeyMaterial" `
  --output text | Out-File -FilePath "$HOME\.ssh\automobile-app-key.pem" -Encoding ascii

# Fix file permissions so SSH accepts it
icacls "$HOME\.ssh\automobile-app-key.pem" /inheritance:r
icacls "$HOME\.ssh\automobile-app-key.pem" /grant:r "${env:USERNAME}:(R)"
```

Verify the file was created:
```powershell
Get-Content "$HOME\.ssh\automobile-app-key.pem"
```

You should see something like:
```
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Z3VS5JJcds3xHn/ygWep4PAtEsHAq...
-----END RSA PRIVATE KEY-----
```

**Copy the entire output including the BEGIN and END lines — you need this for
GitHub secrets in Phase 2.**

---

## PHASE 2 — GitHub Repository Setup
### (Takes about 10 minutes.)

---

### Step 2.1 — Create a GitHub Repository

1. Go to https://github.com and log in
2. Click the **+** icon (top right) → **New repository**
3. Fill in:
   - Repository name: `automobile-app`
   - Visibility: **Private**
   - Do NOT tick "Add a README file"
4. Click **Create repository**
5. Keep this page open — you will use the URL shown

---

### Step 2.2 — Extract and Push the Project Code

1. Download and extract `automobile-app.zip` to a folder on your machine
   (e.g. `C:\Projects\automobile-app`)

2. Open PowerShell and navigate to that folder:
```powershell
cd C:\Projects\automobile-app
```

3. Initialize git and push to GitHub:
```powershell
git init
git add .
git commit -m "Initial commit: AutoForge app with Docker, Terraform, CI/CD"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/automobile-app.git
git push -u origin main
```

When prompted, enter your GitHub username and password (or personal access token).

**Note:** Replace `YOUR_GITHUB_USERNAME` with your actual GitHub username.

---

### Step 2.3 — Add GitHub Actions Secrets

**Why?** The pipeline needs AWS credentials, SSH keys, and database passwords to
do its job. We never hardcode these in the code — instead GitHub stores them
securely and injects them into the pipeline at runtime.

Go to your GitHub repo → **Settings** tab → **Secrets and variables** (left sidebar)
→ **Actions** → click **New repository secret** for each one below:

---

**Secret 1:**
- Name: `AWS_ACCESS_KEY_ID`
- Value: Your access key ID from Step 1.2 (starts with AKIA...)

**Secret 2:**
- Name: `AWS_SECRET_ACCESS_KEY`
- Value: Your secret access key from Step 1.2

**Secret 3:**
- Name: `AWS_ACCOUNT_ID`
- Value: Your 12-digit AWS account number from Step 1.3
- Get it by running: `aws sts get-caller-identity --query Account --output text`

**Secret 4:**
- Name: `EC2_KEY_PAIR_NAME`
- Value: `automobile-app-key`

**Secret 5:**
- Name: `EC2_SSH_PRIVATE_KEY`
- Value: The full contents of your `.pem` file including the BEGIN and END lines
- Get it: `Get-Content "$HOME\.ssh\automobile-app-key.pem"`
- Copy everything and paste it as the secret value

**Secret 6:**
- Name: `SECRET_KEY`
- Value: Any random string, e.g. `AutoF0rge@SecretKey2024!`

**Secret 7:**
- Name: `DB_USER`
- Value: `automobile_user`

**Secret 8:**
- Name: `DB_PASSWORD`
- Value: `automobile_pass`

**Secret 9:**
- Name: `DB_NAME`
- Value: `automobile_db`

**Secret 10:**
- Name: `MYSQL_ROOT_PASSWORD`
- Value: `RootPass@2024`

After adding all 10, your Secrets page should show 10 secrets listed.

---

### Step 2.4 — Create the Production Environment (Approval Gate)

**Why?** Job 5 in the pipeline is a manual approval gate — it pauses and waits for
you to click Approve before deploying to production. This is a real-world DevOps
practice to prevent accidental deployments.

1. Go to repo → **Settings** → **Environments** (left sidebar)
2. Click **New environment**
3. Name: `production` (must be exactly this — matches the pipeline YAML)
4. Click **Configure environment**
5. Under **Deployment protection rules**, tick **Required reviewers**
6. In the search box, type your GitHub username and select yourself
7. Click **Save protection rules**

---

## PHASE 3 — Run Terraform From Your Machine
### (First time only. Takes about 5 minutes.)

**Why run Terraform manually first?** The pipeline also runs Terraform, but before
the pipeline can run, the ECR repository must exist (to push images to) and the
S3 backend must be accessible. Running it once manually creates everything cleanly.

---

### Step 3.1 — Open the Terraform folder

```powershell
cd C:\Projects\automobile-app\terraform
```

### Step 3.2 — Initialise Terraform

```powershell
terraform init
```

**What this does:** Downloads the AWS provider plugin, connects to your S3 backend,
and sets up the working directory.

Expected output (last few lines):
```
Initializing the backend...
Successfully configured the backend "s3"!

Terraform has been successfully initialized!
```

If you see an error about the S3 bucket not existing, re-run Step 1.4.

---

### Step 3.3 — Preview what Terraform will create

```powershell
terraform plan -var="key_pair_name=automobile-app-key"
```

**What this does:** Terraform compares what you have in code vs what exists in AWS,
and shows you exactly what it will create, change, or destroy. Nothing is created yet.

Look for this at the bottom:
```
Plan: 7 to add, 0 to change, 0 to destroy.
```

The 7 resources are:
- ECR repository (stores your Docker images)
- ECR lifecycle policy (auto-deletes old images)
- EC2 instance (your server — t2.micro, free tier)
- Security group (firewall rules — ports 22, 80, 5000)
- IAM role (lets EC2 pull images from ECR)
- IAM role policy (the actual ECR permissions)
- IAM instance profile (attaches the role to EC2)

---

### Step 3.4 — Apply (actually create the resources)

```powershell
terraform apply -var="key_pair_name=automobile-app-key"
```

Terraform will show the plan again and ask:
```
Do you want to perform these actions? Enter a value:
```

Type `yes` and press Enter.

Wait 2-3 minutes. When complete you will see:

```
Apply complete! Resources: 7 added, 0 changed, 0 destroyed.

Outputs:

app_url             = "http://13.233.xx.xx"
ec2_public_dns      = "ec2-13-233-xx-xx.ap-south-1.compute.amazonaws.com"
ec2_public_ip       = "13.233.xx.xx"
ecr_repository_name = "automobile-app"
ecr_repository_url  = "123456789012.dkr.ecr.ap-south-1.amazonaws.com/automobile-app"
```

**Save the `ec2_public_ip` value — this is your app URL.**

---

## PHASE 4 — Trigger the CI/CD Pipeline
### (Every deployment starts here.)

---

### Step 4.1 — Push to trigger the pipeline

Go back to your project root and make a small change to trigger the pipeline:

```powershell
cd C:\Projects\automobile-app

# Open run.py and add a comment, save it, then:
git add .
git commit -m "Trigger first deployment via CI/CD"
git push origin main
```

---

### Step 4.2 — Watch the pipeline run

1. Go to your GitHub repo in the browser
2. Click the **Actions** tab
3. You will see a workflow run called **Automobile App — CI/CD Pipeline**
4. Click it to open
5. You will see 6 jobs on the left side

Here is what each job does and how long it takes:

---

**Job 1 — Lint & test** (~2-3 minutes)

What happens:
- GitHub spins up a fresh Ubuntu machine
- Installs Python 3.11
- Starts a MySQL container as a service
- Installs all your Python packages from requirements.txt
- Runs `flake8` to check for code style errors
- Runs `python seed.py` to verify the DB connection works
- Runs pytest (skips gracefully if no tests folder)

What you should see: green tick ✓

---

**Job 2 — Docker build** (~3-4 minutes)

What happens:
- Uses Docker Buildx (advanced builder)
- Runs Stage 1 of your Dockerfile (installs gcc, compiles packages)
- Runs Stage 2 (copies only the venv into a clean slim image)
- Saves the built image as a `.tar` file (pipeline artifact)
- Caches Docker layers so next build is faster

What you should see: green tick ✓

---

**Job 3 — Push to ECR** (~1 minute)

What happens:
- Downloads the `.tar` image artifact from Job 2
- Logs into your ECR registry using AWS credentials
- Tags the image with two tags:
  - `:latest` (always points to newest build)
  - `:sha-abc1234` (specific to this git commit — for rollbacks)
- Pushes both tags to ECR

What you should see: green tick ✓

---

**Job 4 — Terraform apply** (~2 minutes)

What happens:
- Downloads Terraform
- Runs `terraform init` (connects to your S3 backend)
- Runs `terraform plan` (checks if infra needs changes)
- Runs `terraform apply` (updates infra if needed)
- Outputs the EC2 IP for Job 6 to use

Since you already ran Terraform manually in Phase 3, this will likely show:
`0 to add, 0 to change, 0 to destroy` — which is correct and fast.

What you should see: green tick ✓

---

**Job 5 — Manual approval** (PAUSED — waiting for you)

The pipeline stops here. You will see an orange hourglass icon.

GitHub will send you an email saying "Your review is requested."

To approve:
1. Click the email link OR go to Actions → click the running workflow
2. You will see a yellow banner: **"This workflow is waiting for your review"**
3. Click **Review deployments**
4. Tick the `production` checkbox
5. Click **Approve and deploy**

The pipeline continues immediately.

---

**Job 6 — Deploy to EC2** (~3-4 minutes)

What happens:
1. Saves your SSH private key to the runner's filesystem
2. Waits for EC2 SSH to be available (retries every 15 seconds, up to 20 times)
3. Copies `docker-compose.prod.yml` to `/opt/automobile-app/` on EC2
4. SSHs into EC2 and runs these commands:
   - Logs into ECR from EC2 using the instance IAM role (no credentials needed)
   - Writes the `.env` file with all your secrets
   - Runs `docker pull` to get the new image
   - Runs `docker compose down` then `docker compose up -d`
   - Waits 30 seconds for containers to start
5. Runs a smoke test: hits `http://EC2_IP/auth/login` and checks for HTTP 200
6. Prints the deployment summary

What you should see: green tick ✓ and a summary like:
```
================================================
  Deployment successful!
  App URL : http://13.233.xx.xx
  Image   : 123456789012.dkr.ecr.ap-south-1.amazonaws.com/automobile-app:sha-abc1234
  Commit  : abc1234...
  Actor   : your-github-username
================================================
```

---

### Step 4.3 — Open the app in your browser

Go to: `http://YOUR_EC2_PUBLIC_IP`

You will see the AutoForge login page.

Login credentials:
- Username: `admin`
- Password: `Admin@123`

---

## PHASE 5 — Using the Application

### As admin you can:

**Dashboard** — see total vehicles, orders, pending orders, registered users

**Vehicles** → Add vehicle
- Make: Toyota, Model: Fortuner, Year: 2024
- Category: SUV, Price: 45000, Stock: 10
- Click Save vehicle

**Vehicles** → each row has Order, Edit, Delete buttons

**Orders** → see all orders placed, click Update to change status
(pending → confirmed → in_production → shipped → delivered)

### Create a test regular user:

1. Log out (top right)
2. Go to `http://YOUR_EC2_IP/auth/register`
3. Register with a new username and email
4. Log in as that user
5. Go to Vehicles → click Order on any vehicle
6. Enter quantity → Place order
7. Log back in as admin → Orders → you will see the order

---

## PHASE 6 — Every Future Deployment

For every code change after this:

```powershell
# Make your changes to any file
git add .
git commit -m "Describe what you changed"
git push origin main
```

Then:
1. Go to GitHub Actions — watch the pipeline
2. Approve at Job 5
3. App is updated in ~10 minutes

That is the full DevOps loop.

---

## Troubleshooting

### "Error: S3 bucket does not exist" during terraform init
Re-run Step 1.4. Make sure the bucket name in `terraform/providers.tf` matches
exactly: `automobile-tfstate-bucket`

### Job 1 fails — flake8 error
Look at the error message. It will say something like:
`app/routes/auth.py:34:121: E501 line too long (125 > 120 characters)`
Open that file, find line 34, shorten it. Push again.

### Job 3 fails — ECR push error
- Check `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` secrets are correct
- Check `AWS_ACCOUNT_ID` is your 12-digit account number (no spaces, no dashes)
- Make sure your IAM user has `AmazonEC2ContainerRegistryFullAccess`

### Job 4 fails — Terraform state error
Usually because the S3 bucket or DynamoDB table does not exist.
Re-run Steps 1.4 and 1.5 from your machine, then retry the pipeline.

### Job 6 fails — SSH Connection timeout
EC2 was just created and is still running `user_data.sh` (installing Docker).
This takes 3-5 minutes on first boot. The pipeline retries 20 times (5 minutes
total) — if it still fails, go to Actions, click Job 6, and click "Re-run job".

### App shows "502 Bad Gateway" or can't connect
SSH into EC2 to debug:
```powershell
ssh -i "$HOME\.ssh\automobile-app-key.pem" ubuntu@YOUR_EC2_IP
```

On EC2:
```bash
cd /opt/automobile-app
docker compose ps          # see if containers are running
docker compose logs automobile-app --tail=50   # Flask logs
docker compose logs automobile-db --tail=30    # MySQL logs
```

Common cause: MySQL takes ~30s to initialise on first start. If Flask started
before MySQL was ready, restart the app container:
```bash
docker compose restart automobile-app
```

### Out of memory — containers crashing
Check memory usage:
```bash
free -h
docker stats --no-stream
```

If MySQL is using too much:
```bash
docker compose down
docker compose up -d
```

The `--innodb-buffer-pool-size=128M` setting in docker-compose.prod.yml
limits MySQL to 128MB. The 1GB swap we added in user_data.sh handles spikes.

---

## Tearing Down (to avoid any charges)

When you want to stop the project and make sure nothing is running:

```powershell
cd C:\Projects\automobile-app\terraform
terraform destroy -var="key_pair_name=automobile-app-key"
```

Type `yes` when prompted.

This deletes: EC2, ECR, Security Group, IAM role, IAM policy, IAM instance profile.
It does NOT delete: S3 bucket, DynamoDB table (cost is negligible, keeps your state).

To also delete S3 and DynamoDB:
```powershell
aws s3 rb s3://automobile-tfstate-bucket --force
aws dynamodb delete-table --table-name automobile-tfstate-lock --region ap-south-1
```

---

## Project File Reference

```
automobile-app/
│
├── DEPLOYMENT_GUIDE.md          ← You are reading this
│
├── app/                         ← Flask application code
│   ├── __init__.py              ← App factory (creates Flask app, registers blueprints)
│   ├── models.py                ← Database tables: User, Vehicle, Order
│   ├── forms.py                 ← Form definitions: Login, Register, Vehicle, Order
│   └── routes/
│       ├── auth.py              ← /auth/login, /auth/logout, /auth/register
│       ├── dashboard.py         ← / (homepage with stats)
│       ├── vehicles.py          ← /vehicles/ (list, add, edit, delete)
│       └── orders.py            ← /orders/ (place, list, update status)
│
├── app/templates/               ← HTML pages (Jinja2)
│   ├── base.html                ← Master layout (navbar, flash messages)
│   ├── auth/login.html          ← Login page
│   ├── auth/register.html       ← Register page
│   ├── dashboard/index.html     ← Dashboard with stat cards
│   ├── vehicles/index.html      ← Vehicle list table
│   ├── vehicles/form.html       ← Add/edit vehicle form
│   ├── orders/index.html        ← Orders list table
│   ├── orders/place.html        ← Place order form
│   └── orders/update.html       ← Update order status form
│
├── app/static/css/style.css     ← Dark industrial theme CSS
│
├── config.py                    ← Flask config (reads from .env file)
├── run.py                       ← Entry point (gunicorn runs this)
├── seed.py                      ← Creates admin user + 5 sample vehicles on startup
├── requirements.txt             ← Python packages (Flask, SQLAlchemy, PyMySQL...)
│
├── Dockerfile                   ← Two-stage build:
│                                   Stage 1 (builder): installs gcc, compiles packages
│                                   Stage 2 (runtime): copies only venv, runs gunicorn
│
├── .dockerignore                ← Files excluded from Docker image (.git, venv, etc)
├── docker-compose.yml           ← Local development (not used in AWS deployment)
├── docker-compose.prod.yml      ← Production: Flask + MySQL + network + volumes
├── .env.example                 ← Template showing what .env should look like
├── .gitignore                   ← Files git should not track (.env, .terraform, etc)
│
└── terraform/
    ├── providers.tf             ← AWS provider config + S3 remote backend
    ├── variables.tf             ← t2.micro, ap-south-1, automobile-app-key
    ├── ecr.tf                   ← ECR private repo + lifecycle policy (keep 5 images)
    ├── security_group.tf        ← Firewall: allow ports 22, 80, 5000
    ├── iam.tf                   ← EC2 role that can pull from ECR (no credentials needed)
    ├── ec2.tf                   ← t2.micro instance, gp2 20GB, free tier
    ├── outputs.tf               ← Prints EC2 IP and ECR URL after apply
    └── user_data.sh             ← Runs on EC2 first boot:
                                    - Creates 1GB swap (critical for t2.micro)
                                    - Installs Docker + Docker Compose
                                    - Installs AWS CLI v2

└── .github/workflows/
    └── deploy.yml               ← 6-job CI/CD pipeline (the heart of this project)
```

---

## GitHub Secrets Quick Reference Card

| Secret Name          | Where to Get It                                              |
|----------------------|--------------------------------------------------------------|
| AWS_ACCESS_KEY_ID    | IAM → Users → github-actions-user → Security credentials    |
| AWS_SECRET_ACCESS_KEY| Same (save when created — shown only once)                  |
| AWS_ACCOUNT_ID       | `aws sts get-caller-identity --query Account --output text` |
| EC2_KEY_PAIR_NAME    | `automobile-app-key`                                        |
| EC2_SSH_PRIVATE_KEY  | `Get-Content "$HOME\.ssh\automobile-app-key.pem"`           |
| SECRET_KEY           | Any random string                                           |
| DB_USER              | `automobile_user`                                           |
| DB_PASSWORD          | `automobile_pass`                                           |
| DB_NAME              | `automobile_db`                                             |
| MYSQL_ROOT_PASSWORD  | `RootPass@2024`                                             |
