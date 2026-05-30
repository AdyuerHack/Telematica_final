#!/bin/bash
# ================================================
# setup_aws.sh - Configuración automática AWS Academy
# Custom ASG - ST0263 Telemática
# ================================================

echo "================================================"
echo "  🚀 Setup Custom ASG - AWS Academy"
echo "================================================"

# ── 1. Verificar credenciales ────────────────────
echo ""
echo "📋 PASO 1: Verificando credenciales AWS..."
aws sts get-caller-identity > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Credenciales no configuradas."
    echo "👉 Ve a AWS Academy → AWS Details → AWS CLI"
    echo "   Pega las credenciales y vuelve a correr este script"
    exit 1
fi
echo "✅ Credenciales OK"

# ── 2. Instalar dependencias ─────────────────────
echo ""
echo "📋 PASO 2: Instalando dependencias Python..."
pip3 install grpcio grpcio-tools boto3 -q
echo "✅ Dependencias instaladas"

# ── 3. Pedir datos al usuario ────────────────────
echo ""
echo "📋 PASO 3: Configuración de AWS"
echo "   (Estos datos los encuentras en la consola EC2)"
echo ""

read -p "🔸 AMI ID (ami-xxx):              " AMI_ID
read -p "🔸 Subnet ID (subnet-xxx):        " SUBNET_ID
read -p "🔸 Security Group ID (sg-xxx):    " SG_ID
read -p "🔸 Región [us-east-1]:            " REGION
REGION=${REGION:-us-east-1}

# ── 4. Crear config.json ─────────────────────────
echo ""
echo "📋 PASO 4: Creando config.json..."

cat > ~/Telefinal/Telematica_final/server/config.json << EOF
{
    "ami_id":               "$AMI_ID",
    "instance_type":        "t2.micro",
    "key_name":             "vockey",
    "security_group_ids":   ["$SG_ID"],
    "subnet_id":            "$SUBNET_ID",
    "iam_instance_profile": "LabInstanceProfile",
    "region":               "$REGION",
    "min_instances":        2,
    "max_instances":        5,
    "scale_out_threshold":  75.0,
    "scale_in_threshold":   20.0,
    "cooldown_seconds":     60
}
EOF
echo "✅ config.json creado"

# ── 5. Verificar archivos necesarios ────────────
echo ""
echo "📋 PASO 5: Verificando archivos del proyecto..."
FILES=("server/main.py" "server/monitor_s.py" "server/controller_asg.py" "agent/monitor_c.py")
ALL_OK=true
for f in "${FILES[@]}"; do
    if [ -f ~/Telefinal/Telematica_final/$f ]; then
        echo "  ✅ $f"
    else
        echo "  ❌ $f NO ENCONTRADO"
        ALL_OK=false
    fi
done

if [ "$ALL_OK" = false ]; then
    echo "❌ Faltan archivos. Verifica el repositorio."
    exit 1
fi

# ── 6. Verificar llave SSH ───────────────────────
echo ""
echo "📋 PASO 6: Verificando llave SSH..."
if [ -f ~/.ssh/labsuser.pem ]; then
    chmod 400 ~/.ssh/labsuser.pem
    echo "✅ labsuser.pem encontrado"
else
    echo "⚠️  labsuser.pem no encontrado en ~/.ssh/"
    echo "   Descárgalo desde AWS Academy → AWS Details → Download PEM"
fi

# ── Resumen final ────────────────────────────────
echo ""
echo "================================================"
echo "  ✅ Setup completado!"
echo "================================================"
echo ""
echo "Para correr el sistema:"
echo "  cd ~/Telefinal/Telematica_final/server"
echo "  python3 main.py"
echo ""
echo "Para la demo de sustentación:"
echo "  scale_out_cpu = 10.0  (en controller_asg.py)"
echo "  scale_in_cpu  = 95.0"
echo "  cooldown_sec  = 15"
echo "================================================"
