#!/bin/bash

# Smart Aid & Budget - Deployment Script
# Usage: ./scripts/deploy.sh [environment]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default environment
ENVIRONMENT=${1:-"development"}

echo -e "${BLUE}🚀 Smart Aid & Budget Deployment${NC}"
echo -e "${BLUE}===============================${NC}"
echo -e "Environment: ${YELLOW}$ENVIRONMENT${NC}"
echo ""

# Load environment-specific configuration
if [ "$ENVIRONMENT" = "production" ]; then
    echo -e "${GREEN}⚡ Production deployment selected${NC}"
    DOCKERFILE="Dockerfile.prod"
    COMPOSE_FILE="docker-compose.prod.yml"
    BUILD_ARGS="--no-cache"
else
    echo -e "${YELLOW}🔧 Development deployment selected${NC}"
    DOCKERFILE="Dockerfile"
    COMPOSE_FILE="docker-compose.yml"
    BUILD_ARGS=""
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

# Check if required files exist
if [ ! -f "$DOCKERFILE" ]; then
    echo -e "${RED}❌ Dockerfile not found: $DOCKERFILE${NC}"
    exit 1
fi

if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${YELLOW}⚠️  Docker Compose file not found: $COMPOSE_FILE. Using default.${NC}"
    COMPOSE_FILE="docker-compose.yml"
fi

# Step 1: Build Docker image
echo -e "\n${BLUE}📦 Step 1: Building Docker image...${NC}"
docker build $BUILD_ARGS -t smart-aid-backend:$ENVIRONMENT -f $DOCKERFILE .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Docker image built successfully${NC}"
else
    echo -e "${RED}❌ Docker build failed${NC}"
    exit 1
fi

# Step 2: Run database migrations
echo -e "\n${BLUE}🗄️  Step 2: Running database migrations...${NC}"
if [ "$ENVIRONMENT" = "production" ]; then
    echo -e "${YELLOW}⚠️  Skipping migrations in production (should be handled separately)${NC}"
else
    docker-compose -f $COMPOSE_FILE run --rm backend alembic upgrade head
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Database migrations completed${NC}"
    else
        echo -e "${RED}❌ Database migrations failed${NC}"
        exit 1
    fi
fi

# Step 3: Start services
echo -e "\n${BLUE}⚡ Step 3: Starting services...${NC}"
docker-compose -f $COMPOSE_FILE up -d

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Services started successfully${NC}"
else
    echo -e "${RED}❌ Failed to start services${NC}"
    exit 1
fi

# Step 4: Wait for services to be ready
echo -e "\n${BLUE}⏳ Step 4: Waiting for services to be ready...${NC}"
sleep 10

# Step 5: Check service health
echo -e "\n${BLUE}🏥 Step 5: Checking service health...${NC}"
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend API is healthy${NC}"
else
    echo -e "${RED}❌ Backend API health check failed${NC}"
    exit 1
fi

if curl -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API v1 endpoint is healthy${NC}"
else
    echo -e "${RED}❌ API v1 health check failed${NC}"
    exit 1
fi

# Step 6: Seed data (development only)
if [ "$ENVIRONMENT" = "development" ]; then
    echo -e "\n${BLUE}🌱 Step 6: Seeding development data...${NC}"
    docker-compose -f $COMPOSE_FILE exec backend python scripts/seed_data.py
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Development data seeded${NC}"
    else
        echo -e "${YELLOW}⚠️  Development data seeding failed or skipped${NC}"
    fi
fi

# Deployment summary
echo -e "\n${GREEN}🎉 Deployment completed successfully!${NC}"
echo -e "${BLUE}=================================${NC}"
echo -e "API URL: ${YELLOW}http://localhost:8000${NC}"
echo -e "API Documentation: ${YELLOW}http://localhost:8000/docs${NC}"
echo -e "Health Check: ${YELLOW}http://localhost:8000/health${NC}"
echo -e "Internal Health: ${YELLOW}http://localhost:8000/internal/health${NC}"
echo ""
echo -e "${BLUE}📋 Available endpoints:${NC}"
echo -e "  Auth: ${YELLOW}http://localhost:8000/api/v1/auth${NC}"
echo -e "  Students: ${YELLOW}http://localhost:8000/api/v1/students${NC}"
echo -e "  Expenses: ${YELLOW}http://localhost:8000/api/v1/expenses${NC}"
echo -e "  Budgets: ${YELLOW}http://localhost:8000/api/v1/budgets${NC}"
echo -e "  Scholarships: ${YELLOW}http://localhost:8000/api/v1/scholarships${NC}"
echo -e "  Notifications: ${YELLOW}http://localhost:8000/api/v1/notifications${NC}"
echo -e "  Payments: ${YELLOW}http://localhost:8000/api/v1/payments${NC}"
echo ""
echo -e "${BLUE}🐳 Docker commands:${NC}"
echo -e "  View logs: ${YELLOW}docker-compose -f $COMPOSE_FILE logs -f${NC}"
echo -e "  Stop services: ${YELLOW}docker-compose -f $COMPOSE_FILE down${NC}"
echo -e "  Restart backend: ${YELLOW}docker-compose -f $COMPOSE_FILE restart backend${NC}"
echo -e "  Access shell: ${YELLOW}docker-compose -f $COMPOSE_FILE exec backend bash${NC}"
echo ""
echo -e "${GREEN}🚀 Your Smart Aid & Budget backend is now running!${NC}"