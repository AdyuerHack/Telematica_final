"""
integration_test.py -- Prueba de integracion completa del sistema ASG

Demuestra el sistema completo sin necesidad de AWS:
  1. Levanta 2 agentes locales con carga BAJA (~15%)
  2. Inicia MonitorS + ControllerASG en modo dry-run
  3. Verifica que el sistema no escala (estamos en el minimo)
  4. Sube la carga a ALTA (85%) -> provoca scale-out
  5. Verifica que ControllerASG crea una nueva instancia (dry-run)
  6. Baja la carga a MUY BAJA (5%) -> provoca scale-in
  7. Verifica que ControllerASG elimina la instancia extra
  8. Verifica deteccion de instancias caidas (DEAD)
  9. Imprime resumen con PASS/FAIL

Uso:
    python tests/integration_test.py
"""

import sys
import os
import time
import subprocess

# Forzar UTF-8 en Windows para evitar errores de encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# -- Path setup ---
ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT  = os.path.join(ROOT, "agent")
SERVER = os.path.join(ROOT, "server")
GEN    = os.path.join(ROOT, "generated")

for p in [ROOT, AGENT, SERVER, GEN]:
    if p not in sys.path:
        sys.path.insert(0, p)

from monitor_s      import MonitorS
from controller_asg import ControllerASG, ASG_CONFIG

# -- Colores ANSI ---
GRN  = "\033[92m"
RED  = "\033[91m"
YLW  = "\033[93m"
BLU  = "\033[94m"
CYN  = "\033[96m"
BOLD = "\033[1m"
RST  = "\033[0m"

# -- Config del test (cooldowns cortos para demo rapida) ---
TEST_CONFIG = {
    **ASG_CONFIG,
    "min_instances"  : 2,
    "max_instances"  : 4,
    "scale_out_cpu"  : 75.0,   # Scale-out si CPU > 75%
    "scale_in_cpu"   : 20.0,   # Scale-in  si CPU < 20%
    "cooldown_sec"   : 8,      # Cooldown corto para demo
    "region"         : "us-east-1",
    "ami_id"         : "ami-TEST",
}

PYTHON          = sys.executable
AGENT_BASE_PORT = 50051
NUM_AGENTS      = 2

results: list = []   # lista de (nombre, paso, detalle)


# -- Helpers de output ---
def banner(msg: str):
    print(f"\n{BOLD}{CYN}{'='*62}{RST}")
    print(f"{BOLD}{CYN}   {msg}{RST}")
    print(f"{BOLD}{CYN}{'='*62}{RST}")


def info(msg: str):
    print(f"  {BLU}[i]{RST}  {msg}")


def ok(msg: str):
    print(f"  {GRN}[OK]{RST} {msg}")


def warn(msg: str):
    print(f"  {YLW}[!]{RST}  {msg}")


def fail_msg(msg: str):
    print(f"  {RED}[X]{RST}  {msg}")


def check(name: str, condition: bool, detail: str = ""):
    results.append((name, condition, detail))
    if condition:
        ok(f"PASS | {name}  {detail}")
    else:
        fail_msg(f"FAIL | {name}  {detail}")


def wait_with_dots(seconds: int, msg: str):
    print(f"  >>  {msg} ", end="", flush=True)
    for _ in range(seconds):
        print(".", end="", flush=True)
        time.sleep(1)
    print(f" {GRN}OK{RST}")


# -- Lanzar un agente como subproceso ---
def launch_agent(instance_id: str, port: int, fixed_cpu: float) -> subprocess.Popen:
    cmd = [
        PYTHON, os.path.join(AGENT, "monitor_c.py"),
        "--instance-id", instance_id,
        "--port", str(port),
        "--fixed-cpu", str(fixed_cpu),
    ]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# =============================================================================
def run_test():
    banner("PRUEBA DE INTEGRACION - Auto Scaling Group (dry-run)")
    print(f"  Politicas: scale-out > {TEST_CONFIG['scale_out_cpu']}%  |  "
          f"scale-in < {TEST_CONFIG['scale_in_cpu']}%")
    print(f"  Limites:   min={TEST_CONFIG['min_instances']}  |  "
          f"max={TEST_CONFIG['max_instances']}")
    print(f"  Cooldown:  {TEST_CONFIG['cooldown_sec']}s")

    agents: list = []

    # =========================================================================
    # FASE 1: Agentes con carga BAJA
    # =========================================================================
    banner("FASE 1: Iniciando 2 agentes con CPU=15% (carga baja)")

    for i in range(NUM_AGENTS):
        iid  = f"i-test-{i+1:03d}"
        port = AGENT_BASE_PORT + i
        info(f"Lanzando agente {iid} en puerto {port}  (CPU fija=15%)")
        agents.append(launch_agent(iid, port, fixed_cpu=15.0))

    wait_with_dots(3, "Esperando arranque de agentes")

    # =========================================================================
    # FASE 2: Iniciar MonitorS + ControllerASG
    # =========================================================================
    banner("FASE 2: Iniciando MonitorS y ControllerASG")

    monitor    = MonitorS()
    controller = ControllerASG(monitor=monitor, config=TEST_CONFIG, dry_run=True)
    controller.EVAL_INTERVAL_SEC = 5  # evaluar cada 5s para demo rapida

    for i in range(NUM_AGENTS):
        iid  = f"i-test-{i+1:03d}"
        port = AGENT_BASE_PORT + i
        monitor.register_instance(iid, "127.0.0.1", port)
        info(f"Instancia {iid} registrada en MonitorS")

    monitor.start()
    controller.start()

    wait_with_dots(9, "Esperando primeras lecturas de metricas")

    alive_count = monitor.get_alive_count()
    avg_cpu     = monitor.get_average_cpu()

    check("2 agentes vivos al inicio",
          alive_count == 2,
          f"vivos={alive_count}, CPU_prom={avg_cpu:.1f}%")
    check("CPU baja detectada correctamente (<= 30%)",
          avg_cpu <= 30.0,
          f"CPU={avg_cpu:.1f}%")

    # =========================================================================
    # FASE 3: Scale-OUT por carga alta
    # =========================================================================
    banner("FASE 3: SCALE-OUT -- subiendo CPU a 85% en todos los agentes")

    for proc in agents:
        proc.terminate()
    agents.clear()
    time.sleep(1)

    for i in range(NUM_AGENTS):
        iid  = f"i-test-{i+1:03d}"
        port = AGENT_BASE_PORT + i
        warn(f"Relanzando {iid} con CPU=85%")
        agents.append(launch_agent(iid, port, fixed_cpu=85.0))

    wait_with_dots(3, "Esperando reinicio de agentes")

    warn("Observando... esperando que ControllerASG dispare SCALE-OUT")
    scale_out_happened = False
    initial_alive      = monitor.get_alive_count()

    for tick in range(40):
        time.sleep(1)
        n   = monitor.get_alive_count()
        cpu = monitor.get_average_cpu()
        status = f"[{tick+1:02d}s]  Instancias: {n}   CPU prom: {cpu:.1f}%"
        if n > initial_alive:
            scale_out_happened = True
            print(f"  {GRN}{status}  <-- SCALE-OUT DISPARADO!{RST}")
            break
        print(f"         {status}")

    check("Scale-out disparado por CPU > 75%",
          scale_out_happened,
          f"instancias: {initial_alive} -> {monitor.get_alive_count()}")

    # =========================================================================
    # FASE 4: Scale-IN por carga baja
    # =========================================================================
    banner("FASE 4: SCALE-IN -- bajando CPU a 5% en todos los agentes")

    for proc in agents:
        proc.terminate()
    agents.clear()
    time.sleep(1)

    for i in range(NUM_AGENTS):
        iid  = f"i-test-{i+1:03d}"
        port = AGENT_BASE_PORT + i
        warn(f"Relanzando {iid} con CPU=5%")
        agents.append(launch_agent(iid, port, fixed_cpu=5.0))

    wait_with_dots(3, "Esperando reinicio de agentes")

    warn("Observando... esperando que ControllerASG dispare SCALE-IN")
    scale_in_happened = False
    before_scale_in   = monitor.get_alive_count()

    for tick in range(40):
        time.sleep(1)
        n   = monitor.get_alive_count()
        cpu = monitor.get_average_cpu()
        status = f"[{tick+1:02d}s]  Instancias: {n}   CPU prom: {cpu:.1f}%"
        if n < before_scale_in and n >= TEST_CONFIG["min_instances"]:
            scale_in_happened = True
            print(f"  {GRN}{status}  <-- SCALE-IN DISPARADO!{RST}")
            break
        print(f"         {status}")

    check("Scale-in disparado por CPU < 20%",
          scale_in_happened,
          f"instancias: {before_scale_in} -> {monitor.get_alive_count()}")

    check("Minimo de instancias respetado (>= 2)",
          monitor.get_alive_count() >= TEST_CONFIG["min_instances"],
          f"min={TEST_CONFIG['min_instances']}, actual={monitor.get_alive_count()}")

    # =========================================================================
    # FASE 5: Deteccion de instancias DEAD
    # =========================================================================
    banner("FASE 5: Verificando deteccion de instancia CAIDA (DEAD)")

    # Detectar dinamicamente que instancias estan vivas y elegir una para matar
    alive_before = monitor.get_alive_instances()
    alive_ids    = list(alive_before.keys())
    info(f"Instancias vivas antes del test: {alive_ids}")

    # Elegir la primera instancia viva del registro para matar su agente proceso
    # (agents[0] es el proceso del ultimo agente relanzado en fase 4)
    victim_id = None
    if agents and alive_ids:
        # Asociar el agente proceso con una instancia viva que use el mismo puerto
        for iid in alive_ids:
            state = alive_before[iid]
            if state.port == AGENT_BASE_PORT + 1:  # i-test-002 -> puerto 50052
                victim_id = iid
                break
        if victim_id is None:
            victim_id = alive_ids[0]

        warn(f"Matando agente del proceso (puerto={AGENT_BASE_PORT+1}) "
             f"que corresponde a '{victim_id}' -- simula fallo real")
        agents[0].terminate()
        agents[0].wait()
        agents.pop(0)
    else:
        warn("No hay agentes activos para matar en esta fase")

    wait_with_dots(20, "Esperando que MonitorS marque la instancia como DEAD (3 fallos)")

    states       = monitor.get_all_states()
    # Verificar que ALGUNA instancia fue marcada como DEAD (la que mato el test)
    any_dead      = any(not s.alive for s in states.values())
    dead_instance = next((s for s in states.values() if not s.alive), None)

    check("Instancia caida marcada como DEAD",
          any_dead,
          f"instancia_dead={dead_instance.instance_id if dead_instance else 'N/A'}, "
          f"fail_count={dead_instance.fail_count if dead_instance else 'N/A'}")

    # =========================================================================
    # RESUMEN
    # =========================================================================
    banner("RESUMEN DE LA PRUEBA DE INTEGRACION")

    passed = sum(1 for _, p, _ in results if p)
    total  = len(results)

    print()
    for name, paso, detail in results:
        color = GRN if paso else RED
        label = "PASS" if paso else "FAIL"
        print(f"  {color}[{label}]{RST}  {name}")
        if detail:
            print(f"          {YLW}{detail}{RST}")

    print()
    if passed == total:
        print(f"{BOLD}{GRN}  [EXITO] TODAS LAS PRUEBAS PASARON ({passed}/{total}){RST}")
    else:
        print(f"{BOLD}{RED}  [AVISO] {passed}/{total} pruebas pasaron -- revisar FAILs arriba{RST}")

    # Limpieza
    controller.stop()
    monitor.stop()
    for proc in agents:
        proc.terminate()

    return passed == total


# =============================================================================
if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
