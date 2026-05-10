# LearningSteps Lockdown - Security Hardening Project

## Overview
This project transforms an intentionally insecure Azure deployment into a hardened, production-ready architecture.

## Architecture

### Before (Insecure)
- VM with public IP directly exposed
- NSG allowing all traffic on ports 22, 80, 8000
- PostgreSQL with public IP and open firewall
- No authentication on API
- No encryption

### After (Hardened)
- VM with no public IP, access only via Azure Bastion
- Identity-based SSH via Microsoft Entra ID
- API protected by oauth2-proxy with JWT validation
- PostgreSQL isolated in private VNet with no public IP
- Nginx edge layer with TLS 1.2/1.3, HSTS, WAF, rate limiting

## Security Improvements by Day

### Day 2: Perimeter Security
- Removed public IP from VM (Azure Policy compliance)
- Enabled Managed Identity on VM
- Installed AADSSHLoginForLinux extension
- Granted RBAC role: Virtual Machine Administrator Login
- Deployed Azure Bastion with tunneling
- Restricted NSG port 22 to specific IP and Bastion subnet only

![Day 2 - Entra ID Login](docs/day2-entra-login.png)

### Day 3: API Security
- Created App Registration in Microsoft Entra ID
- Deployed oauth2-proxy as systemd sidecar on port 4180
- Configured OIDC with tenant v2.0 endpoint
- Removed port 8000 from NSG
- All API access requires valid Bearer Token (JWT)

![Day 3 - Token Tests](docs/day3-token-tests.png)

### Day 4: Data Isolation
- Deleted public PostgreSQL instance
- Created dedicated delegated subnet (snet-db 10.0.3.0/24)
- Created private DNS zone for PostgreSQL
- Redeployed PostgreSQL with VNet Integration (no public IP)
- Migrated all data via pg_dump/psql restore

![Day 4 - DB Success from VM](docs/day4-db-success.png)
![Day 4 - DB Failure from Outside](docs/day4-db-failure.png)

### Day 5: Edge Security
- Moved oauth2-proxy to localhost:4180
- Deployed Nginx as edge proxy on ports 80/443
- Generated self-signed TLS certificate (RSA 2048, TLS 1.2/1.3)
- HTTP to HTTPS redirect
- Security headers: HSTS, X-Content-Type-Options, X-Frame-Options
- Rate limiting: 10 req/s, burst 20, returns 429
- WAF rules blocking SQLi and XSS patterns
- Removed port 80 from NSG, only 443 allowed

![Day 5 - HTTPS and WAF](docs/day5-https-waf.png)
![Day 5 - Rate Limiting](docs/day5-rate-limit.png)

## Final Architecture
Internet -> NSG (443 only) -> Nginx (TLS + WAF + Rate Limit) -> oauth2-proxy (JWT) -> FastAPI -> PostgreSQL (private VNet)
Management: Azure Bastion -> VM (Entra ID login)

## Deployment
Clone the repo and run deploy.py to set up the base infrastructure, then apply security hardening manually as documented above.

## Files Modified
- vm.tf - Removed public IP from NIC
- outputs.tf - Updated to use private IP and az ssh command

## Bonus Security Features

### Resource Lock
- Applied CanNotDelete lock on VNet to prevent accidental deletion
- Tested: deletion attempt returns ScopeLocked error

### Activity Logs
- Azure Monitor Activity Logs track all NSG modifications
- Audit trail shows caller, operation, and timestamp

### Fail2Ban
- Monitors Nginx access logs for repeated 403 errors
- Bans IPs after 10 failures within 60 seconds for 1 hour

### WAF Implementation Note
ModSecurity OWASP CRS was not available as a precompiled package for Nginx 1.18 on Ubuntu 22.04. A custom WAF was implemented using Nginx map directives to block SQLi and XSS patterns, returning 403 Forbidden for malicious requests.
