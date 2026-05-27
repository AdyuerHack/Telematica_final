"""
main.py  ──  Punto de entrada del servidor central
Inicia MonitorS y ControllerASG de forma concurrente (threads daemon).
"""

import time
import signal
import logging
import argparse
import sys
import os

# Asegurar que se puedan importar los módulos del proyecto
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "generated"))

from monitor_s      import MonitorS
from controller_asg import ControllerASG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MAIN] %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Servidor Central ASG")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simula las llamadas a AWS (para pruebas locales sin credenciales)"
    )
    parser.add_argument(
        "--demo-agents", type=int, default=0,
        help="Número de agentes locales a registrar automáticamente para demo"
    )
    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("  🚀 Iniciando Servidor Central ASG")
    logger.info(f"  Modo: {'DRY-RUN (sin AWS real)' if args.dry_run else 'PRODUCCIÓN (AWS real)'}")
    logger.info("=" * 50)

    # ── Inicializar componentes ─────────────────────────────────
    monitor    = MonitorS()
    controller = ControllerASG(monitor=monitor, dry_run=args.dry_run)

    # ── Registrar agentes de demo si se solicita ───────────────
    # Útil para mostrar el sistema funcionando localmente
    if args.demo_agents > 0:
        logger.info(f"🧪 Registrando {args.demo_agents} agente(s) de demo local...")
        base_port = 50051
        for i in range(args.demo_agents):
            iid  = f"i-demo-{i+1:03d}"
            port = base_port + i
            monitor.register_instance(iid, "127.0.0.1", port)

    # ── Arrancar los dos servicios ──────────────────────────────
    monitor.start()
    controller.start()

    # ── Esperar señal de terminación (Ctrl+C) ───────────────────
    def handle_sigint(sig, frame):
        logger.info("\n🛑 Señal de interrupción recibida. Apagando...")
        controller.stop()
        monitor.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    logger.info("✅ Sistema activo. Presiona Ctrl+C para detener.\n")
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
