"""
controller_asg.py  ──  Controlador de Auto Scaling (ControllerASG)
Responsabilidades:
  • Leer el estado de instancias desde la memoria compartida del MonitorS
  • Evaluar las políticas de escalamiento cada N segundos
  • Crear nuevas instancias EC2 vía AWS SDK (boto3) cuando sea necesario
  • Terminar instancias EC2 vía AWS SDK cuando sea necesario
  • Respetar los límites minInstances=2 y maxInstances=5
"""

import boto3
import time
import logging
import threading
from typing import Optional
from monitor_s import MonitorS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ControllerASG] %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
#  Configuración del ASG (ajusta con tus valores de AWS Academy)
# ──────────────────────────────────────────────────────────────
ASG_CONFIG = {
    # ── Límites ─────────────────────────────────────────────────
    "min_instances"     : 2,
    "max_instances"     : 5,

    # ── Políticas de escalamiento ────────────────────────────────
    "scale_out_cpu"     : 70.0,   # Si CPU promedio > este valor → crear instancia
    "scale_in_cpu"      : 30.0,   # Si CPU promedio < este valor → terminar instancia
    "cooldown_sec"      : 60,     # Tiempo de espera entre acciones de escala

    # ── AWS (rellena con tus datos de AWS Academy) ───────────────
    "region"            : "us-east-1",
    "ami_id"            : "ami-XXXXXXXXXXXXXXXXX",   # ← Tu AMI personalizada
    "instance_type"     : "t2.micro",
    "key_name"          : "vockey",                  # ← Tu Key Pair de Academy
    "security_group_ids": ["sg-XXXXXXXXXXXXXXXXX"],  # ← Tu Security Group
    "subnet_id"         : "subnet-XXXXXXXXXXXXXXXXX",# ← Tu Subnet

    # ── Puerto donde escuchará el agente en cada nueva instancia ─
    "agent_port"        : 50051,
}

# Script que se ejecuta al arrancar cada instancia EC2 nueva
# (instala dependencias y arranca el agente MonitorC)
USER_DATA_SCRIPT = """#!/bin/bash
cd /home/ec2-user/agent
pip3 install grpcio grpcio-tools
python3 monitor_c.py --instance-id $(curl -s http://169.254.169.254/latest/meta-data/instance-id) --port 50051 &
"""


# ──────────────────────────────────────────────────────────────
#  Controlador ASG
# ──────────────────────────────────────────────────────────────
class ControllerASG:
    EVAL_INTERVAL_SEC = 10   # Cada cuántos segundos evalúa las políticas

    def __init__(self, monitor: MonitorS, config: dict = None, dry_run: bool = False):
        self.monitor      = monitor
        self.config       = config or ASG_CONFIG
        self.dry_run      = dry_run  # Si True, simula las llamadas a AWS (para pruebas locales)
        self._running     = False
        self._thread      = None
        self._last_action = 0.0      # timestamp de la última acción de escala
        self._lock        = threading.Lock()

        if not dry_run:
            self.ec2 = boto3.client("ec2", region_name=self.config["region"])
        else:
            logger.warning("⚠️  MODO DRY-RUN: no se harán llamadas reales a AWS")
            self.ec2 = None

    # ── Ciclo principal ────────────────────────────────────────
    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._control_loop, daemon=True, name="ControllerASG")
        self._thread.start()
        logger.info("🚀 ControllerASG iniciado.")

    def stop(self):
        self._running = False
        logger.info("🛑 ControllerASG detenido.")

    def _control_loop(self):
        # Esperar a que el MonitorS tenga datos iniciales
        time.sleep(10)
        while self._running:
            self._evaluate_policies()
            time.sleep(self.EVAL_INTERVAL_SEC)

    # ── Evaluación de políticas ────────────────────────────────
    def _evaluate_policies(self):
        alive_count = self.monitor.get_alive_count()
        avg_cpu     = self.monitor.get_average_cpu()
        cfg         = self.config

        logger.info(
            f"📊 Evaluando políticas | Instancias vivas: {alive_count} | "
            f"CPU promedio: {avg_cpu:.1f}% | "
            f"Min: {cfg['min_instances']} | Max: {cfg['max_instances']}"
        )

        # ── Regla 1: garantizar el mínimo de instancias ──────────
        if alive_count < cfg["min_instances"]:
            needed = cfg["min_instances"] - alive_count
            logger.warning(f"⚡ Por debajo del mínimo. Creando {needed} instancia(s)...")
            for _ in range(needed):
                self._scale_out()
            return

        # ── Regla 2: no superar el máximo ───────────────────────
        if alive_count > cfg["max_instances"]:
            excess = alive_count - cfg["max_instances"]
            logger.warning(f"⚡ Por encima del máximo. Terminando {excess} instancia(s)...")
            for _ in range(excess):
                self._scale_in()
            return

        # ── Comprobar cooldown ────────────────────────────────────
        if not self._cooldown_ok():
            logger.info("⏳ En período de cooldown, esperando...")
            return

        # ── Regla 3: scale-out por alta carga ────────────────────
        if avg_cpu > cfg["scale_out_cpu"] and alive_count < cfg["max_instances"]:
            logger.warning(
                f"🔺 CPU {avg_cpu:.1f}% > {cfg['scale_out_cpu']}% → SCALE OUT"
            )
            self._scale_out()

        # ── Regla 4: scale-in por baja carga ─────────────────────
        elif avg_cpu < cfg["scale_in_cpu"] and alive_count > cfg["min_instances"]:
            logger.warning(
                f"🔻 CPU {avg_cpu:.1f}% < {cfg['scale_in_cpu']}% → SCALE IN"
            )
            self._scale_in()
        else:
            logger.info(f"✅ Sin acción de escalamiento necesaria.")

    # ── Scale-out: crear una instancia ────────────────────────
    def _scale_out(self):
        cfg = self.config
        logger.info(f"➕ Lanzando nueva instancia EC2 (AMI: {cfg['ami_id']})...")

        if self.dry_run:
            fake_id = f"i-dryrun-{int(time.time())}"
            logger.info(f"[DRY-RUN] Nueva instancia simulada: {fake_id}")
            # Registrar instancia fake en el MonitorS para demos locales
            self.monitor.register_instance(fake_id, "127.0.0.1", 50051)
            self._reset_cooldown()
            return

        try:
            response = self.ec2.run_instances(
                ImageId         = cfg["ami_id"],
                InstanceType    = cfg["instance_type"],
                MinCount        = 1,
                MaxCount        = 1,
                KeyName         = cfg["key_name"],
                SecurityGroupIds= cfg["security_group_ids"],
                SubnetId        = cfg["subnet_id"],
                UserData        = USER_DATA_SCRIPT,
                TagSpecifications=[{
                    "ResourceType": "instance",
                    "Tags": [{"Key": "Name", "Value": "ASG-AutoInstance"},
                             {"Key": "ManagedBy", "Value": "ControllerASG"}],
                }],
            )
            instance = response["Instances"][0]
            new_id   = instance["InstanceId"]
            logger.info(f"✅ Instancia creada: {new_id} (esperando IP pública...)")

            # Esperar a que la instancia tenga IP
            waiter = self.ec2.get_waiter("instance_running")
            waiter.wait(InstanceIds=[new_id])

            # Obtener la IP pública
            desc = self.ec2.describe_instances(InstanceIds=[new_id])
            public_ip = desc["Reservations"][0]["Instances"][0].get("PublicIpAddress", "")
            logger.info(f"🌐 IP pública de {new_id}: {public_ip}")

            # Registrar en el MonitorS para empezar a monitorear
            self.monitor.register_instance(new_id, public_ip, cfg["agent_port"])
            self._reset_cooldown()

        except Exception as e:
            logger.error(f"❌ Error al crear instancia: {e}")

    # ── Scale-in: terminar una instancia ─────────────────────
    def _scale_in(self):
        # Elegir la instancia con menor carga para terminar
        alive = self.monitor.get_alive_instances()
        if not alive:
            return

        target_id = min(alive, key=lambda k: alive[k].cpu_load)
        logger.info(f"➖ Terminando instancia con menor carga: {target_id} "
                    f"(CPU: {alive[target_id].cpu_load:.1f}%)")

        if self.dry_run:
            logger.info(f"[DRY-RUN] Instancia {target_id} terminada (simulado)")
            self.monitor.deregister_instance(target_id)
            self._reset_cooldown()
            return

        try:
            self.ec2.terminate_instances(InstanceIds=[target_id])
            logger.info(f"✅ Instancia {target_id} terminada en AWS")
            self.monitor.deregister_instance(target_id)
            self._reset_cooldown()
        except Exception as e:
            logger.error(f"❌ Error al terminar instancia {target_id}: {e}")

    # ── Cooldown helpers ───────────────────────────────────────
    def _cooldown_ok(self) -> bool:
        with self._lock:
            return (time.time() - self._last_action) >= self.config["cooldown_sec"]

    def _reset_cooldown(self):
        with self._lock:
            self._last_action = time.time()
