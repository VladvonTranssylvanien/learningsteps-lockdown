# LearningSteps — Base Deployment

A one-command Azure deployment of the [LearningSteps](https://github.com/CyberstepsDE/learningsteps) API and a PostgreSQL database.

> **This deployment is intentionally minimal and unsecured.** The VM is publicly reachable, the database accepts connections from any IP, credentials are stored in plaintext, and there is no traffic inspection or monitoring. It is a starting point — not a production setup.

## What Gets Deployed

- **Ubuntu VM** (Standard_D2s_v3) running the FastAPI application on port 8000
- **Azure PostgreSQL Flexible Server** (B1ms) as the database
- A virtual network with one subnet and a basic network security group

## Prerequisites

Install the following before running the script:

| Tool | Install |
|---|---|
| Python 3.8+ | [python.org](https://www.python.org/downloads/) — on Windows use `python`, on macOS/Linux use `python3` |
| Terraform ≥ 1.5 | [developer.hashicorp.com/terraform/install](https://developer.hashicorp.com/terraform/install) |
| Azure CLI | [learn.microsoft.com/en-us/cli/azure/install-azure-cli](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) |
| Azure subscription | Your account needs **Contributor** or **Owner** role on the subscription |

## Deploy

```bash
python3 deploy.py
```

On Windows:
```
python deploy.py
```

The script will:
1. Log you in to Azure if needed (opens a browser)
2. Generate an SSH key pair in the project folder
3. Ask for a resource prefix and Azure region (press Enter for defaults)
4. Ask for a PostgreSQL admin password
5. Run `terraform apply` — takes about 7–8 minutes
6. Run a smoke test against the deployed API

To skip the interactive prompts:
```bash
python3 deploy.py --password YourPassword1 --prefix myenv --location westeurope
```

Once deployed, the script prints the API URL and SSH command.

## Stopping and Starting

When not in use, deallocate the VM to avoid compute charges:
```bash
az vm deallocate --resource-group rg-<prefix> --name vm-<prefix>
```

Start it again:
```bash
az vm start --resource-group rg-<prefix> --name vm-<prefix>
```

Stop the database:
```bash
az postgres flexible-server stop --resource-group rg-<prefix> --name psql-<prefix>-<suffix>
```

Start it again:
```bash
az postgres flexible-server start --resource-group rg-<prefix> --name psql-<prefix>-<suffix>
```

> Note: Azure automatically restarts a stopped PostgreSQL Flexible Server after 7 days.

To destroy everything permanently:
```bash
terraform destroy
```

## SSH Access

The SSH key is generated in the project folder during deployment:

```bash
ssh azureuser@<vm-ip> -i .learningsteps_key
```

