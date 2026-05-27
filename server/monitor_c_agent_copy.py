"""
monitor_c.py  ──  Agente que corre dentro de cada instancia EC2
Implementa:
  • Servidor gRPC (AgentService): Ping, GetMetrics, Register
  • Simulador de carga: sube y baja la CPU de forma gradual y natural
"""

import grpc
import time
import math
import random
import logging
import argparse
import threading
from concurrent import futures

# Importar los stubs generados por protoc
import monitor_pb2
import monitor_pb2_grpc

# ──────────────────────────────────────────────────────────────
#  Configuración de logging
# ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AGENTE %(instance_id)s] %(levelname)s - %(message)s",
)


# ──────────────────────────────────────────────────────────────
#  Simulador de carga (CPU)
#  Genera una señal suave que combina senos y ruido leve.
#  La carga oscila entre ~10% y ~95% de forma continua.
# ──────────────────────────────────────────────────────────────
class LoadSimulator:
    def __init__(self, seed: float = None, fixed_cpu: float = None):
        self._lock      = threading.Lock()
        self._fixed_cpu = fixed_cpu  # Si no es None, siempre retorna este valor
        self._cpu       = fixed_cpu if fixed_cpu is not None else 30.0   # carga inicial
        self._mem     = 40.0
        self._phase   = random.uniform(0, 2 * math.pi)  # fase aleatoria para variar por instancia
        self._running = False
        self._thread  = None

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def set_fixed_cpu(self, value: float):
        """Forzar CPU a un valor fijo (para tests)."""
        with self._lock:
            self._fixed_cpu = value
            self._cpu = value

    def _run(self):
        t = 0.0
        while self._running:
            # Si hay un valor fijo (modo test), no simular
            with self._lock:
                if self._fixed_cpu is not None:
                    t += 1.0
                    time.sleep(1.0)
                    continue

            # Señal base: onda seno de período ~60 segundos + armónico
            base = (
                math.sin(2 * math.pi * t / 60 + self._phase) * 30
                + math.sin(2 * math.pi * t / 20 + self._phase * 1.5) * 15
                + 55  # offset: centra en ~55%
            )
            noise = random.gauss(0, 3)  # ruido gaussiano leve
            with self._lock:
                self._cpu = max(5.0, min(97.0, base + noise))
                self._mem = max(10.0, min(90.0, base * 0.6 + 20 + random.gauss(0, 2)))
            t += 1.0
            time.sleep(1.0)

    @property
    def cpu(self) -> float:
        with self._lock:
            return round(self._cpu, 2)

    @property
    def mem(self) -> float:
        with self._lock:
            return round(self._mem, 2)


# ──────────────────────────────────────────────────────────────
#  Implementación del servicio gRPC
# ──────────────────────────────────────────────────────────────
class AgentServicer(monitor_pb2_grpc.AgentServiceServicer):

    def __init__(self, instance_id: str, simulator: LoadSimulator):
        self.instance_id = instance_id
        self.simulator   = simulator
        self.logger      = logging.LoggerAdapter(
            logging.getLogger(__name__), {"instance_id": instance_id}
        )

    # ── Heartbeat ──────────────────────────────────────────────
    def Ping(self, request, context):
        self.logger.info(f"Ping recibido de '{request.sender_id}'")
        return monitor_pb2.PingResponse(
            alive       = True,
            instance_id = self.instance_id,
            timestamp   = int(time.time()),
        )

    # ── Métricas ────────────────────────────────────────────────
    def GetMetrics(self, request, context):
        cpu = self.simulator.cpu
        mem = self.simulator.mem
        self.logger.info(f"GetMetrics → CPU={cpu:.1f}%  MEM={mem:.1f}%")
        return monitor_pb2.MetricsResponse(
            instance_id = self.instance_id,
            cpu_load    = cpu,
            mem_load    = mem,
            timestamp   = int(time.time()),
        )

    # ── Registro (el agente puede reportarse a sí mismo) ────────
    def Register(self, request, context):
        # En este flujo el agente es servidor; este método
        # queda por si se quiere un patrón "pull" inverso.
        return monitor_pb2.RegisterResponse(
            accepted = True,
            message  = f"Instancia {request.instance_id} registrada OK",
        )


# ──────────────────────────────────────────────────────────────
#  Punto de entrada
# ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Agente MonitorC para instancia EC2")
    parser.add_argument("--instance-id", default="i-local-test",  help="ID de la instancia EC2")
    parser.add_argument("--port",        type=int, default=50051,  help="Puerto gRPC del agente")
    parser.add_argument("--fixed-cpu",   type=float, default=None, help="Forzar CPU a este valor (0-100). Para tests.")
    args = parser.parse_args()

    # Iniciar simulador de carga
    simulator = LoadSimulator(fixed_cpu=args.fixed_cpu)
    simulator.start()
    logging.info(f"Simulador de carga iniciado para instancia {args.instance_id}")

    # Iniciar servidor gRPC
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    monitor_pb2_grpc.add_AgentServiceServicer_to_server(
        AgentServicer(args.instance_id, simulator), server
    )
    server.add_insecure_port(f"0.0.0.0:{args.port}")
    server.start()
    logging.info(f"[AGENTE {args.instance_id}] Escuchando en puerto {args.port}...")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logging.info("Agente detenido por el usuario.")
        simulator.stop()
        server.stop(0)


if __name__ == "__main__":
    main()
