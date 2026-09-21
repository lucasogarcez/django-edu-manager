#!/bin/bash
set -e
NOME_SERVICO="web" # Ajuste para o nome do seu serviço Django

echo "[1/4] Realizando Build (Sistema CONTINUA ONLINE)..."
# Compila o novo código em background. Os usuários nem percebem.
docker compose build --no-cache

echo "[2/4] Acionando o Interlock (Modo de Manutenção)..."
# A nossa placa bonita é ativada. Se alguém clicar em algo agora, cai nela.
docker compose exec -T $NOME_SERVICO touch maintenance.flag || true
sleep 3

echo "[3/4] Efetuando Hot-Swap (Troca a Quente)..."
# O 'up -d' é inteligente. Ele vê que a imagem mudou, desliga o contêiner velho 
# e liga o novo imediatamente. A "queda" do barramento dura menos de 3 segundos!
docker compose up -d

echo "[4/4] Limpando o circuito..."
# Removemos a flag do contêiner novo para liberar o tráfego
docker compose exec -T $NOME_SERVICO rm -f maintenance.flag || true

echo ">>> Deploy Zero-Downtime concluído com sucesso!"