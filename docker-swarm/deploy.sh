#!/bin/bash

# ==============================================
# DISCUSS HUB - DOCKER SWARM DEPLOY SCRIPT
# ==============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
STACK_NAME="discuss-hub"
COMPOSE_FILE="docker-compose.swarm.yml"
ENV_FILE=".env"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    log_info "Verificando requisitos..."

    # Check if running in swarm mode
    if ! docker info --format '{{.Swarm.LocalNodeState}}' | grep -q active; then
        log_error "Docker Swarm não está ativo!"
        log_info "Execute: docker swarm init"
        exit 1
    fi

    # Check if compose file exists
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log_error "Arquivo $COMPOSE_FILE não encontrado!"
        exit 1
    fi

    # Check if .env file exists
    if [[ ! -f "$ENV_FILE" ]]; then
        log_warning "Arquivo .env não encontrado. Copiando do .env.example..."
        if [[ -f ".env.example" ]]; then
            cp .env.example .env
            log_success "Arquivo .env criado. Por favor, revise as configurações."
        else
            log_error "Arquivo .env.example não encontrado!"
            exit 1
        fi
    fi

    log_success "Requisitos verificados!"
}

create_networks() {
    log_info "Criando networks..."

    # Create traefik network if it doesn't exist
    if ! docker network ls --format "{{.Name}}" | grep -q "^traefik$"; then
        docker network create --driver overlay --attachable traefik
        log_success "Network 'traefik' criada!"
    else
        log_info "Network 'traefik' já existe."
    fi
}

label_nodes() {
    log_info "Configurando labels dos nodes..."

    # Label current node for database (you can change this)
    NODE_ID=$(docker node ls --filter "role=manager" --format "{{.ID}}" | head -n1)
    docker node update --label-add db=true "$NODE_ID"

    log_success "Node labels configurados!"
}

deploy_stack() {
    log_info "Fazendo deploy da stack $STACK_NAME..."

    # Source environment file
    if [[ -f "$ENV_FILE" ]]; then
        set -a
        source "$ENV_FILE"
        set +a
    fi

    # Deploy the stack
    docker stack deploy -c "$COMPOSE_FILE" "$STACK_NAME"

    log_success "Stack $STACK_NAME deployed!"
}

check_stack_status() {
    log_info "Verificando status da stack..."

    echo ""
    echo "=== STACK STATUS ==="
    docker stack ls

    echo ""
    echo "=== SERVICES STATUS ==="
    docker stack services "$STACK_NAME"

    echo ""
    echo "=== SERVICES DETAILS ==="
    docker service ls --filter "label=com.docker.stack.namespace=$STACK_NAME"
}

show_urls() {
    # Source environment file to get DOMAIN
    if [[ -f "$ENV_FILE" ]]; then
        set -a
        source "$ENV_FILE"
        set +a
    fi

    DOMAIN=${DOMAIN:-localhost}

    echo ""
    echo "=== ACESSOS ==="
    echo -e "${GREEN}Odoo:${NC}           https://odoo.${DOMAIN}"
    echo -e "${GREEN}Evolution API:${NC}  https://evolution.${DOMAIN}"
    echo -e "${GREEN}Mailpit:${NC}       https://mailpit.${DOMAIN}"
    echo -e "${GREEN}Traefik:${NC}       https://traefik.${DOMAIN}"
    echo ""
    echo -e "${YELLOW}Aguarde alguns minutos para todos os serviços ficarem prontos...${NC}"
}

# Main execution
main() {
    log_info "=== DISCUSS HUB - DOCKER SWARM DEPLOY ==="

    check_requirements
    create_networks
    label_nodes
    deploy_stack

    echo ""
    log_success "Deploy concluído!"

    check_stack_status
    show_urls
}

# Handle command line arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "status")
        check_stack_status
        ;;
    "logs")
        SERVICE_NAME=${2:-}
        if [[ -n "$SERVICE_NAME" ]]; then
            docker service logs -f "${STACK_NAME}_${SERVICE_NAME}"
        else
            log_info "Serviços disponíveis:"
            docker stack services "$STACK_NAME" --format "table {{.Name}}\t{{.Replicas}}\t{{.Image}}"
            echo ""
            log_info "Use: $0 logs <service_name>"
            log_info "Exemplo: $0 logs odoo"
        fi
        ;;
    "scale")
        SERVICE_NAME=${2:-}
        REPLICAS=${3:-}
        if [[ -n "$SERVICE_NAME" ]] && [[ -n "$REPLICAS" ]]; then
            docker service scale "${STACK_NAME}_${SERVICE_NAME}=${REPLICAS}"
            log_success "Serviço ${SERVICE_NAME} escalado para ${REPLICAS} réplicas!"
        else
            log_error "Use: $0 scale <service_name> <replicas>"
            log_info "Exemplo: $0 scale odoo 3"
        fi
        ;;
    "remove")
        log_warning "Removendo stack $STACK_NAME..."
        docker stack rm "$STACK_NAME"
        log_success "Stack $STACK_NAME removida!"
        ;;
    "update")
        SERVICE_NAME=${2:-}
        if [[ -n "$SERVICE_NAME" ]]; then
            docker service update --force "${STACK_NAME}_${SERVICE_NAME}"
            log_success "Serviço ${SERVICE_NAME} atualizado!"
        else
            log_info "Atualizando todos os serviços..."
            docker stack deploy -c "$COMPOSE_FILE" "$STACK_NAME"
            log_success "Stack atualizada!"
        fi
        ;;
    "help"|*)
        echo "=== DISCUSS HUB - DOCKER SWARM MANAGER ==="
        echo ""
        echo "Uso: $0 [COMMAND] [OPTIONS]"
        echo ""
        echo "Comandos disponíveis:"
        echo "  deploy          Faz deploy da stack (padrão)"
        echo "  status          Mostra status da stack"
        echo "  logs [service]  Mostra logs do serviço"
        echo "  scale <service> <replicas>  Escala serviço"
        echo "  update [service]  Atualiza serviço ou stack"
        echo "  remove          Remove a stack"
        echo "  help            Mostra esta ajuda"
        echo ""
        echo "Exemplos:"
        echo "  $0                    # Deploy da stack"
        echo "  $0 status             # Ver status"
        echo "  $0 logs odoo          # Ver logs do Odoo"
        echo "  $0 scale odoo 3       # Escalar Odoo para 3 réplicas"
        echo "  $0 update odoo        # Atualizar serviço Odoo"
        echo "  $0 remove             # Remover tudo"
        ;;
esac
