"""
monitor_s.py  ──  Monitor del lado del servidor (MonitorS)
Responsabilidades:
  • Mantener el registro de instancias activas (IP:puerto)
  • Consultar periódicamente a cada instancia: Ping + GetMetrics
  • Almacenar el estado en memoria compartida (thread-safe)
  • Marcar instancias como DEAD si no responden
"""

import grpc
import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional

import monitor_pb2
import monitor_pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MonitorS] %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
#  Estado de una instancia
# ──────────────────────────────────────────────────────────────
@dataclass
class InstanceState:
    instance_id : str
    host        : str
    port        : int
    alive       : bool  = True
    cpu_load    : float = 0.0
    mem_load    : float = 0.0
    last_seen   : float = field(default_factory=time.time)
    fail_count  : int   = 0


# ──────────────────────────────────────────────────────────────
#  Monitor del servidor  (MonitorS)
# ──────────────────────────────────────────────────────────────
class MonitorS:
    POLL_INTERVAL_SEC  = 5     # cuántos segundos entre cada ronda de consultas
    MAX_FAILS_BEFORE_DEAD = 3  # cuántas fallas seguidas para marcar DEAD
    GRPC_TIMEOUT_SEC   = 3     # timeout por llamada gRPC

    def __init__(self):
        # Diccionario compartido: instance_id → InstanceState
        self._instances: Dict[str, InstanceState] = {}
        self._lock      = threading.Lock()          # protege _instances
        self._running   = False
        self._thread    = None

    # ── API pública ────────────────────────────────────────────
    def register_instance(self, instance_id: str, host: str, port: int):
        """Registrar una instancia para monitorear."""
        with self._lock:
            if instance_id not in self._instances:
                self._instances[instance_id] = InstanceState(instance_id, host, port)
                logger.info(f"✅ Instancia registrada: {instance_id} → {host}:{port}")
            else:
                logger.info(f"ℹ️  Instancia ya registrada: {instance_id}")

    def deregister_instance(self, instance_id: str):
        """Eliminar una instancia del monitoreo."""
        with self._lock:
            if instance_id in self._instances:
                del self._instances[instance_id]
                logger.info(f"❌ Instancia eliminada del monitoreo: {instance_id}")

    def get_all_states(self) -> Dict[str, InstanceState]:
        """Devolver una copia del estado actual de todas las instancias."""
        with self._lock:
            return dict(self._instances)

    def get_alive_instances(self) -> Dict[str, InstanceState]:
        """Devolver solo las instancias que están vivas."""
        with self._lock:
            return {k: v for k, v in self._instances.items() if v.alive}

    def get_average_cpu(self) -> float:
        """Promedio de CPU de las instancias activas."""
        alive = self.get_alive_instances()
        if not alive:
            return 0.0
        return sum(s.cpu_load for s in alive.values()) / len(alive)

    def get_instance_count(self) -> int:
        """Total de instancias (activas + inactivas)."""
        with self._lock:
            return len(self._instances)

    def get_alive_count(self) -> int:
        """Total de instancias activas."""
        return len(self.get_alive_instances())

    # ── Loop de monitoreo ──────────────────────────────────────
    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._monitor_loop, daemon=True, name="MonitorS")
        self._thread.start()
        logger.info("🚀 MonitorS iniciado.")

    def stop(self):
        self._running = False
        logger.info("🛑 MonitorS detenido.")

    def _monitor_loop(self):
        while self._running:
            with self._lock:
                instance_ids = list(self._instances.keys())

            for iid in instance_ids:
                with self._lock:
                    state = self._instances.get(iid)
                if state is None:
                    continue
                self._poll_instance(state)

            self._log_status()
            time.sleep(self.POLL_INTERVAL_SEC)

    def _poll_instance(self, state: InstanceState):
        """Hacer Ping + GetMetrics a una instancia concreta."""
        address = f"{state.host}:{state.port}"
        try:
            with grpc.insecure_channel(address) as channel:
                stub = monitor_pb2_grpc.AgentServiceStub(channel)

                # ── Heartbeat ──────────────────────────────────
                ping_resp = stub.Ping(
                    monitor_pb2.PingRequest(sender_id="MonitorS"),
                    timeout=self.GRPC_TIMEOUT_SEC,
                )
                if not ping_resp.alive:
                    raise Exception("El agente respondió alive=false")

                # ── Métricas ───────────────────────────────────
                metrics_resp = stub.GetMetrics(
                    monitor_pb2.MetricsRequest(requester_id="MonitorS"),
                    timeout=self.GRPC_TIMEOUT_SEC,
                )

            with self._lock:
                if state.instance_id in self._instances:
                    s = self._instances[state.instance_id]
                    s.alive      = True
                    s.cpu_load   = metrics_resp.cpu_load
                    s.mem_load   = metrics_resp.mem_load
                    s.last_seen  = time.time()
                    s.fail_count = 0

        except Exception as e:
            logger.warning(f"⚠️  Fallo al contactar {state.instance_id} ({address}): {e}")
            with self._lock:
                if state.instance_id in self._instances:
                    s = self._instances[state.instance_id]
                    s.fail_count += 1
                    if s.fail_count >= self.MAX_FAILS_BEFORE_DEAD:
                        s.alive = False
                        logger.error(f"💀 Instancia {state.instance_id} marcada como DEAD")

    def _log_status(self):
        """Imprimir tabla de estado en consola."""
        with self._lock:
            states = list(self._instances.values())

        if not states:
            logger.info("Sin instancias registradas.")
            return

        logger.info("=" * 60)
        logger.info(f"{'ID':<20} {'HOST':<16} {'CPU':>6} {'MEM':>6} {'STATUS':<8}")
        logger.info("-" * 60)
        for s in states:
            status = "🟢 VIVA" if s.alive else "🔴 DEAD"
            logger.info(
                f"{s.instance_id:<20} {s.host:<16} "
                f"{s.cpu_load:>5.1f}% {s.mem_load:>5.1f}% {status}"
            )
        avg = self.get_average_cpu()
        logger.info(f"  → CPU promedio: {avg:.1f}%  |  Vivas: {self.get_alive_count()}")
        logger.info("=" * 60)
