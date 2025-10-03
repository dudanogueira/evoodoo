# ==============================================
# DISCUSS HUB - DOCKER SWARM DEPLOY SCRIPT (PowerShell)
# ==============================================

param(
    [Parameter(Position=0)]
    [ValidateSet("deploy", "status", "logs", "scale", "remove", "update", "help")]
    [string]$Command = "deploy",

    [Parameter(Position=1)]
    [string]$ServiceName = "",

    [Parameter(Position=2)]
    [int]$Replicas = 0
)

# Configuration
$STACK_NAME = "discuss-hub"
$COMPOSE_FILE = "docker-compose.swarm.yml"
$ENV_FILE = ".env"

# Functions
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Test-Requirements {
    Write-Info "Verificando requisitos..."

    # Check if Docker is running
    try {
        $null = docker info 2>$null
    } catch {
        Write-Error "Docker não está executando!"
        exit 1
    }

    # Check if running in swarm mode
    $swarmState = docker info --format '{{.Swarm.LocalNodeState}}' 2>$null
    if ($swarmState -ne "active") {
        Write-Error "Docker Swarm não está ativo!"
        Write-Info "Execute: docker swarm init"
        exit 1
    }

    # Check if compose file exists
    if (-not (Test-Path $COMPOSE_FILE)) {
        Write-Error "Arquivo $COMPOSE_FILE não encontrado!"
        exit 1
    }

    # Check if .env file exists
    if (-not (Test-Path $ENV_FILE)) {
        Write-Warning "Arquivo .env não encontrado. Copiando do .env.example..."
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
            Write-Success "Arquivo .env criado. Por favor, revise as configurações."
        } else {
            Write-Error "Arquivo .env.example não encontrado!"
            exit 1
        }
    }

    Write-Success "Requisitos verificados!"
}

function New-Networks {
    Write-Info "Criando networks..."

    # Check if traefik network exists
    $networks = docker network ls --format "{{.Name}}"
    if ($networks -notcontains "traefik") {
        docker network create --driver overlay --attachable traefik
        Write-Success "Network 'traefik' criada!"
    } else {
        Write-Info "Network 'traefik' já existe."
    }
}

function Set-NodeLabels {
    Write-Info "Configurando labels dos nodes..."

    # Label current node for database
    $nodeId = (docker node ls --filter "role=manager" --format "{{.ID}}" | Select-Object -First 1)
    docker node update --label-add db=true $nodeId

    Write-Success "Node labels configurados!"
}

function Deploy-Stack {
    Write-Info "Fazendo deploy da stack $STACK_NAME..."

    # Load environment variables
    if (Test-Path $ENV_FILE) {
        Get-Content $ENV_FILE | Where-Object { $_ -match '^\s*[^#].*=' } | ForEach-Object {
            $key, $value = $_ -split '=', 2
            [Environment]::SetEnvironmentVariable($key.Trim(), $value.Trim(), "Process")
        }
    }

    # Deploy the stack
    docker stack deploy -c $COMPOSE_FILE $STACK_NAME

    Write-Success "Stack $STACK_NAME deployed!"
}

function Show-StackStatus {
    Write-Info "Verificando status da stack..."

    Write-Host "`n=== STACK STATUS ===" -ForegroundColor Cyan
    docker stack ls

    Write-Host "`n=== SERVICES STATUS ===" -ForegroundColor Cyan
    docker stack services $STACK_NAME

    Write-Host "`n=== SERVICES DETAILS ===" -ForegroundColor Cyan
    docker service ls --filter "label=com.docker.stack.namespace=$STACK_NAME"
}

function Show-Urls {
    # Get domain from .env file
    $domain = "localhost"
    if (Test-Path $ENV_FILE) {
        $domainLine = Get-Content $ENV_FILE | Where-Object { $_ -match "^DOMAIN=" }
        if ($domainLine) {
            $domain = ($domainLine -split "=")[1].Trim()
        }
    }

    Write-Host "`n=== ACESSOS ===" -ForegroundColor Cyan
    Write-Host "Odoo:           " -NoNewline -ForegroundColor Green
    Write-Host "https://odoo.$domain"
    Write-Host "Evolution API:  " -NoNewline -ForegroundColor Green
    Write-Host "https://evolution.$domain"
    Write-Host "Mailpit:        " -NoNewline -ForegroundColor Green
    Write-Host "https://mailpit.$domain"
    Write-Host "Traefik:        " -NoNewline -ForegroundColor Green
    Write-Host "https://traefik.$domain"
    Write-Host "`nAguarde alguns minutos para todos os serviços ficarem prontos..." -ForegroundColor Yellow
}

function Invoke-Deploy {
    Write-Info "=== DISCUSS HUB - DOCKER SWARM DEPLOY ==="

    Test-Requirements
    New-Networks
    Set-NodeLabels
    Deploy-Stack

    Write-Host ""
    Write-Success "Deploy concluído!"

    Show-StackStatus
    Show-Urls
}

# Main execution based on command
switch ($Command) {
    "deploy" {
        Invoke-Deploy
    }
    "status" {
        Show-StackStatus
    }
    "logs" {
        if ($ServiceName) {
            docker service logs -f "$($STACK_NAME)_$ServiceName"
        } else {
            Write-Info "Serviços disponíveis:"
            docker stack services $STACK_NAME --format "table {{.Name}}`t{{.Replicas}}`t{{.Image}}"
            Write-Host ""
            Write-Info "Use: .\deploy.ps1 logs <service_name>"
            Write-Info "Exemplo: .\deploy.ps1 logs odoo"
        }
    }
    "scale" {
        if ($ServiceName -and $Replicas -gt 0) {
            docker service scale "$($STACK_NAME)_$ServiceName=$Replicas"
            Write-Success "Serviço $ServiceName escalado para $Replicas réplicas!"
        } else {
            Write-Error "Use: .\deploy.ps1 scale <service_name> <replicas>"
            Write-Info "Exemplo: .\deploy.ps1 scale odoo 3"
        }
    }
    "remove" {
        Write-Warning "Removendo stack $STACK_NAME..."
        docker stack rm $STACK_NAME
        Write-Success "Stack $STACK_NAME removida!"
    }
    "update" {
        if ($ServiceName) {
            docker service update --force "$($STACK_NAME)_$ServiceName"
            Write-Success "Serviço $ServiceName atualizado!"
        } else {
            Write-Info "Atualizando todos os serviços..."
            docker stack deploy -c $COMPOSE_FILE $STACK_NAME
            Write-Success "Stack atualizada!"
        }
    }
    "help" {
        Write-Host "=== DISCUSS HUB - DOCKER SWARM MANAGER ===" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Uso: .\deploy.ps1 [COMMAND] [OPTIONS]"
        Write-Host ""
        Write-Host "Comandos disponíveis:"
        Write-Host "  deploy          Faz deploy da stack (padrão)"
        Write-Host "  status          Mostra status da stack"
        Write-Host "  logs [service]  Mostra logs do serviço"
        Write-Host "  scale <service> <replicas>  Escala serviço"
        Write-Host "  update [service]  Atualiza serviço ou stack"
        Write-Host "  remove          Remove a stack"
        Write-Host "  help            Mostra esta ajuda"
        Write-Host ""
        Write-Host "Exemplos:"
        Write-Host "  .\deploy.ps1                    # Deploy da stack"
        Write-Host "  .\deploy.ps1 status             # Ver status"
        Write-Host "  .\deploy.ps1 logs odoo          # Ver logs do Odoo"
        Write-Host "  .\deploy.ps1 scale odoo 3       # Escalar Odoo para 3 réplicas"
        Write-Host "  .\deploy.ps1 update odoo        # Atualizar serviço Odoo"
        Write-Host "  .\deploy.ps1 remove             # Remover tudo"
    }
}
