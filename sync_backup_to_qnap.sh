#!/usr/bin/env bash
# ==============================================================================
# Sincronizador de Respaldo de Cenaduría Viky hacia QNAP #2
# ==============================================================================
set -e

VPS_HOST="204.168.235.137"
QNAP1_HOST="192.168.100.10"
QNAP2_HOST="192.168.100.6"
QNAP_BACKUP_DIR="/share/CACHEDEV1_DATA/Public/respaldo_restaurante_viky"
DATE=$(date +"%Y%m%d_%H%M%S")

echo "=================================================="
echo "🛡️ Sincronizando respaldo Viky hacia QNAP #2..."
echo "=================================================="

# 1. Descargar base de datos actual del VPS
echo "📥 1/3 Descargando restaurant.db desde VPS ($VPS_HOST)..."
ssh root@$VPS_HOST "cat /root/classic_bot/data/restaurant.db" > /tmp/restaurant_live.db

# 2. Empaquetar código fuente limpio
echo "📦 2/3 Empaquetando código fuente actualizado..."
tar -C /Volumes/MiDisco1TB/Proyectos/28-whatsapp-restaurant \
    --exclude=".git" --exclude="node_modules" --exclude="venv" \
    --exclude="__pycache__" --exclude=".DS_Store" \
    -czf /tmp/respaldo_viky_completo.tar.gz \
    app static server.py requirements.txt README.md render.yaml Procfile

# 3. Enviar a QNAP #2 via QNAP #1
echo "🚀 3/3 Transfiriendo a QNAP #2 ($QNAP2_HOST)..."
sshpass -p "Amortiguad@r1" scp -o StrictHostKeyChecking=no /tmp/restaurant_live.db /tmp/respaldo_viky_completo.tar.gz admin@$QNAP1_HOST:/tmp/
sshpass -p "Amortiguad@r1" ssh -o StrictHostKeyChecking=no admin@$QNAP1_HOST "
  scp -o StrictHostKeyChecking=no /tmp/restaurant_live.db admin@$QNAP2_HOST:$QNAP_BACKUP_DIR/data/restaurant.db
  scp -o StrictHostKeyChecking=no /tmp/restaurant_live.db admin@$QNAP2_HOST:$QNAP_BACKUP_DIR/data/restaurant_$DATE.db
  scp -o StrictHostKeyChecking=no /tmp/respaldo_viky_completo.tar.gz admin@$QNAP2_HOST:$QNAP_BACKUP_DIR/respaldo_viky_completo.tar.gz
  rm -f /tmp/restaurant_live.db /tmp/respaldo_viky_completo.tar.gz
"

rm -f /tmp/restaurant_live.db /tmp/respaldo_viky_completo.tar.gz

echo "=================================================="
echo "✅ ¡Respaldo completado exitosamente en QNAP #2!"
echo "📍 Destino: $QNAP_BACKUP_DIR/"
echo "=================================================="
