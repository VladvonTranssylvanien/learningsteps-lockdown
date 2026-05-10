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
- Deployed Azure Bastion Standard with tunneling
- Restricted NSG port 22 to specific IP and Bastion subnet only

### Day 3: API Security
- Created App Registration in Microsoft Entra ID
- Deployed oauth2-proxy as systemd sidecar on port 80
- Configured OIDC with tenant v2.0 endpoint
- Removed port 8000 from NSG (FastAPI no longer directly accessible)
- All API access requires valid Bearer Token (JWT)

### Day 4: Data Isolation
- Deleted public PostgreSQL instance
- Created dedicated delegated subnet (snet-db 10.0.3.0/24)
- Created private DNS zone for PostgreSQL
- Redeployed PostgreSQL with VNet Integration (no public IP)
- Migrated all data via pg_dump/psql restore
- DB accessible only from within VNet

### Day 5: Edge Security
- Moved oauth2-proxy to localhost:4180
- Deployed Nginx as edge proxy on ports 80/443
- Generated self-signed TLS certificate (RSA 2048, TLS 1.2/1.3)
- HTTP to HTTPS redirect
- Security headers: HSTS, X-Content-Type-Options, X-Frame-Options
- Rate limiting: 10 req/s, burst 20, returns 429
- WAF rules blocking SQLi and XSS patterns
- Removed port 80 from NSG, only 443 allowed

## Final Architecture
Internet -> NSG (443 only) -> Nginx (TLS + WAF + Rate Limit) -> oauth2-proxy (JWT) -> FastAPI -> PostgreSQL (private VNet)
Management: Azure Bastion -> VM (Entra ID login)

## Deployment
Clone the repo and run deploy.py to set up the base infrastructure, then apply security hardening manually as documented above.

## Files Modified
- vm.tf - Removed public IP from NIC
- outputs.tf - Updated to use private IP and az ssh command
