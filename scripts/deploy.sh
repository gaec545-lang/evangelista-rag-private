#!/bin/bash
set -e

echo "=== Deploy Evangelista Intelligence Platform ==="
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VAULT_DIR="$(cd "$ROOT_DIR/../evangelista-vault" && pwd)"

# 1. Ingestar vault al Qdrant Cloud
echo ""
echo "1/4: Ingestando knowledge base en Qdrant Cloud..."
cd "$ROOT_DIR"
python -m cli.ingest --vault-path "$VAULT_DIR"
echo "Ingestión completada."

# 2. Deploy backend a Railway
echo ""
echo "2/4: Deploying backend a Railway..."
if command -v railway &>/dev/null; then
    railway up --detach
    echo "Backend deployed a Railway."
else
    echo "AVISO: Railway CLI no instalado. Instalar con: npm install -g @railway/cli"
    echo "Luego ejecutar: railway up --detach"
fi

# 3. Build + deploy frontend a Vercel
echo ""
echo "3/4: Deploying frontend a Vercel..."
cd "$ROOT_DIR/../evangelista-dashboard"
npm run build
if command -v vercel &>/dev/null; then
    vercel --prod
    echo "Frontend deployed a Vercel."
else
    echo "AVISO: Vercel CLI no instalado. Instalar con: npm install -g vercel"
    echo "Luego ejecutar: vercel --prod desde evangelista-dashboard/"
fi

# 4. Health check
echo ""
echo "4/4: Health check..."
if command -v railway &>/dev/null; then
    BACKEND_URL=$(railway variables get RAILWAY_PUBLIC_DOMAIN 2>/dev/null || echo "")
    if [ -n "$BACKEND_URL" ]; then
        curl -s "https://$BACKEND_URL/readiness" | python -m json.tool
    else
        echo "No se pudo obtener la URL de Railway. Verificar manualmente."
    fi
else
    echo "Verificar backend en Railway dashboard."
fi

echo ""
echo "=== Deploy completado ==="
echo "Backend: Railway dashboard"
echo "Frontend: Vercel dashboard"
echo "Qdrant: Qdrant Cloud dashboard"
