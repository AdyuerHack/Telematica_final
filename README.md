# Custom ASG - ST0263 Telemática 🚀

Sistema de Auto Escalamiento personalizado sobre instancias EC2 de AWS,
reemplazando el servicio nativo de AWS Auto Scaling.

## Integrantes
- Adyuer Ojeda Badel
- Julian Peña Ochoa
- Carlos Arturo Diaz Hernandez

---

## Arquitectura
WSL / Servidor Central
├── MonitorS      → polling cada 5s a los agentes (gRPC)
└── ControllerASG → evalúa métricas cada 10s
├── Scale-Out → CPU > umbral → run_instances()
└── Scale-In  → CPU < umbral → terminate_instances()
EC2 Agentes (creadas dinámicamente)
└── MonitorC → servidor gRPC :50051
├── Ping/Pong  → heartbeat de vivacidad
└── GetMetrics → CPU simulada (onda senoidal)

## Tecnologías
- Python 3 + Threading + Locks
- gRPC + Protocol Buffers
- boto3 (AWS SDK)
- AWS EC2 + AMI personalizada
- systemd (autostart del agente)

---

## Requisitos previos

- WSL Ubuntu o Linux
- Python 3.8+
- AWS Academy account
- Git

---

## Instalación

### 1. Clonar el repositorio
```bash
git clone https://github.com/AdyuerHack/Telematica_final.git
cd Telematica_final
```

### 2. Configurar credenciales AWS Academy
AWS Academy → Start Lab → esperar verde ✅
→ AWS Details → AWS CLI → copiar y pegar en terminal
```bash
aws configure set aws_access_key_id     "ASIA..."
aws configure set aws_secret_access_key "xxx..."
aws configure set aws_session_token     "FwoG..."
aws configure set region                "us-east-1"

# Verificar
aws sts get-caller-identity
```

### 3. Descargar llave SSH
AWS Academy → AWS Details → Download PEM
```bash
mkdir -p ~/.ssh
cp /mnt/c/Users/TuUsuario/Downloads/labsuser.pem ~/.ssh/
chmod 400 ~/.ssh/labsuser.pem
```

---

## Configuración AWS (solo primera vez)

### Crear Security Groups en EC2 → Security Groups

**SG-1: custom-asg-controller**
| Tipo | Puerto | Origen |
|------|--------|--------|
| SSH  | 22     | My IP  |

**SG-2: custom-asg-agents**
| Tipo       | Puerto | Origen                |
|------------|--------|-----------------------|
| Custom TCP | 50051  | custom-asg-controller |
| SSH        | 22     | My IP                 |

### Crear instancia base y AMI

```bash
# 1. Lanzar instancia en consola AWS:
#    AMI: Amazon Linux 2023 | Tipo: t2.micro
#    Key pair: vockey | SG: custom-asg-agents

# 2. Conectarse por SSH
ssh -i ~/.ssh/labsuser.pem ec2-user@<IP_PUBLICA>

# 3. Instalar dependencias
sudo dnf install -y python3-pip
pip3 install grpcio grpcio-tools boto3

# 4. Subir archivos del agente (desde WSL local)
scp -i ~/.ssh/labsuser.pem \
    agent/monitor_c.py \
    agent/monitor_pb2.py \
    agent/monitor_pb2_grpc.py \
    ec2-user@<IP_PUBLICA>:~/

# 5. Crear servicio systemd (dentro de la instancia)
sudo nano /etc/systemd/system/grpc-agent.service
```

Contenido del servicio:
```ini
[Unit]
Description=gRPC Agent Monitor
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/ec2-user/monitor_c.py
WorkingDirectory=/home/ec2-user
Restart=always
RestartSec=5
User=ec2-user

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable grpc-agent
sudo systemctl start grpc-agent
sudo systemctl status grpc-agent
```
6. Crear AMI desde la consola AWS:
EC2 → Instances → Actions → Image and templates → Create image
Image name: custom-asg-ami-v2
Reboot instance: desmarcado
---

## Correr el setup automático

```bash
chmod +x setup_aws.sh
./setup_aws.sh
```

El script pedirá:
🔸 AMI ID      → el de custom-asg-ami-v2
🔸 Subnet ID   → de tu instancia base
🔸 SG ID       → de custom-asg-agents
🔸 Región      → us-east-1 (Enter)
---

## Ejecutar el sistema

```bash
cd server
python3 main.py
```

Output esperado:
🚀 Iniciando Servidor Central ASG
🚀 MonitorS iniciado
🚀 ControllerASG iniciado
✅ Sistema activo
📊 Evaluando políticas | Instancias vivas: 2 | CPU: 54%
✅ Sin acción de escalamiento necesaria
---

## Demo de Sustentación

### Umbrales para demo rápida
Edita `server/controller_asg.py`:
```python
"scale_out_cpu" : 10.0,   # Scale-Out agresivo
"scale_in_cpu"  : 90.0,   # Scale-In agresivo  
"cooldown_sec"  : 15,     # Cooldown corto
```

### Umbrales para producción
```python
"scale_out_cpu" : 70.0,   # Scale-Out normal
"scale_in_cpu"  : 30.0,   # Scale-In normal
"cooldown_sec"  : 60,     # Cooldown normal
```

### Guión de la demo (~6 minutos)
python3 main.py     → crea 2 instancias automáticamente
Esperar ~2 min      → Scale-Out 2→3→4→5 instancias
Observar Scale-In   → 5→4→3→2 instancias
Ctrl+C              → terminar sistema
EC2 → Terminate     → limpiar instancias

---

## Renovar credenciales AWS Academy
Las credenciales expiran cada ~4 horas:
AWS Academy → AWS Details → AWS CLI → copiar y pegar

---

## Estructura del proyecto
```
Telematica_final/
├── agent/
│   ├── monitor_c.py           # Agente gRPC (corre en EC2)
│   ├── monitor_pb2.py         # Generado del .proto
│   └── monitor_pb2_grpc.py    # Generado del .proto
├── generated/
│   ├── __init__.py
│   ├── monitor_pb2.py         # Generado del .proto
│   └── monitor_pb2_grpc.py    # Generado del .proto
├── proto/
│   └── monitor.proto          # Contrato gRPC
├── server/
│   ├── main.py                # Punto de entrada
│   ├── monitor_s.py           # Monitor de instancias
│   ├── controller_asg.py      # Controlador de escalamiento
│   ├── monitor_pb2.py
│   └── monitor_pb2_grpc.py
├── tests/                     # Pruebas locales
├── setup_aws.sh               # Script de configuración AWS
├── generate_proto.sh          # Script para compilar .proto
├── requirements.txt           # Dependencias Python
├── explicacion_proyecto.md    # Documentación adicional
├── .gitignore
└── README.md
```
---

## Notas importantes
> ⚠️ Las credenciales AWS Academy expiran cada ~4 horas
> ⚠️ Terminar instancias después de cada prueba para no agotar créditos
> ⚠️ La AMI se conserva entre sesiones — no la borres
> ⚠️ maxInstances=5 por limitación de AWS Academy
