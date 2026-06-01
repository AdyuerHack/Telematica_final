# Logs de Demo — Custom ASG en AWS Real
## ST0263 Telemática — Proyecto 2

---

## 🚀 Arranque del Sistema

```
16:01:28 🚀 Iniciando Servidor Central ASG
16:01:28    Modo: PRODUCCIÓN (AWS real)
16:01:29 🚀 MonitorS iniciado
16:01:29 🚀 ControllerASG iniciado
16:01:29 ✅ Sistema activo
```

---

## ⚡ Creación de instancias mínimas (min=2)

```
16:01:39 📊 Instancias vivas: 0 | CPU: 0.0% | Min: 2 | Max: 5
16:01:39 ⚡ Por debajo del mínimo. Creando 2 instancia(s)...
16:01:39 ➕ Lanzando nueva instancia EC2 (AMI: ami-017a2c16b02373a3a)...
16:01:40 ✅ Instancia creada: i-0e304517996efd789 (esperando IP pública...)
16:02:10 🌐 IP pública de i-0e304517996efd789: 13.218.139.248
16:02:10 ✅ Instancia registrada: i-0e304517996efd789 → 13.218.139.248:50051
16:02:10 ➕ Lanzando nueva instancia EC2 (AMI: ami-017a2c16b02373a3a)...
16:02:11 ✅ Instancia creada: i-0476b9f156810f2aa (esperando IP pública...)
16:02:42 🌐 IP pública de i-0476b9f156810f2aa: 54.92.177.199
16:02:42 ✅ Instancia registrada: i-0476b9f156810f2aa → 54.92.177.199:50051
```

### Estado con 2 instancias vivas:
```
ID                   HOST              CPU    MEM    STATUS
i-0e304517996efd789  13.218.139.248   73.2%  63.0%  🟢 VIVA
i-0476b9f156810f2aa  54.92.177.199    77.5%  66.9%  🟢 VIVA
→ CPU promedio: 75.3% | Vivas: 2
```

---

## 🔺 SCALE OUT — 2 → 3 instancias

```
16:03:53 📊 Instancias vivas: 3 | CPU promedio: 81.5% | Min: 2 | Max: 5
16:03:53 🔺 CPU 81.5% > 10.0% → SCALE OUT
16:03:53 ➕ Lanzando nueva instancia EC2 (AMI: ami-017a2c16b02373a3a)...
16:03:54 ✅ Instancia creada: i-03c3494bd2f56fd0f (esperando IP pública...)
```

### Estado con 3 instancias vivas:
```
ID                   HOST              CPU    MEM    STATUS
i-0e304517996efd789  13.218.139.248   88.1%  72.6%  🟢 VIVA
i-0476b9f156810f2aa  54.92.177.199    78.4%  67.5%  🟢 VIVA
i-06ef2e26377bdbb04  54.83.129.166    40.0%  48.0%  🟢 VIVA
→ CPU promedio: 68.8% | Vivas: 3
```

---

## 🔺 SCALE OUT — 3 → 4 → 5 instancias (máximo)

```
16:05:11 ID                   HOST              CPU    MEM    STATUS
         i-0e304517996efd789  13.218.139.248   29.4%  44.5%  🟢 VIVA
         i-0476b9f156810f2aa  54.92.177.199    22.1%  31.3%  🟢 VIVA
         i-06ef2e26377bdbb04  54.83.129.166    55.3%  51.5%  🟢 VIVA
         i-03c3494bd2f56fd0f  18.208.162.152   25.9%  37.1%  🟢 VIVA
         → CPU promedio: 33.2% | Vivas: 4

16:05:16 🌐 IP pública de i-023cc5f41fa951546: 3.85.48.43
16:05:16 ✅ Instancia registrada: i-023cc5f41fa951546 → 3.85.48.43:50051

16:05:18 ID                   HOST              CPU    MEM    STATUS
         i-0e304517996efd789  13.218.139.248   40.0%  41.8%  🟢 VIVA
         i-0476b9f156810f2aa  54.92.177.199    40.2%  47.5%  🟢 VIVA
         i-06ef2e26377bdbb04  54.83.129.166    19.7%  30.3%  🟢 VIVA
         i-03c3494bd2f56fd0f  18.208.162.152   45.9%  53.1%  🟢 VIVA
         i-023cc5f41fa951546  3.85.48.43       41.0%  46.4%  🟢 VIVA
         → CPU promedio: 37.4% | Vivas: 5 ← MÁXIMO ALCANZADO ✅
```

---

## 🔻 SCALE IN — 5 → 4 instancias

```
16:05:35 📊 Instancias vivas: 5 | CPU promedio: 51.4% | Min: 2 | Max: 5
16:05:35 🔻 CPU 51.4% < 90.0% → SCALE IN
16:05:35 ➖ Terminando instancia con menor carga: i-023cc5f41fa951546 (CPU: 23.8%)
16:05:36 ✅ Instancia i-023cc5f41fa951546 terminada en AWS
16:05:36 ❌ Instancia eliminada del monitoreo: i-023cc5f41fa951546
```

### Estado después del Scale-In:
```
ID                   HOST              CPU    MEM    STATUS
i-0e304517996efd789  13.218.139.248   89.3%  73.5%  🟢 VIVA
i-0476b9f156810f2aa  54.92.177.199    92.3%  77.1%  🟢 VIVA
i-06ef2e26377bdbb04  54.83.129.166    34.2%  46.4%  🟢 VIVA
i-03c3494bd2f56fd0f  18.208.162.152   75.4%  63.5%  🟢 VIVA
→ CPU promedio: 72.8% | Vivas: 4
```

---

## 🔺 SCALE OUT nuevamente — 4 → 5

```
16:05:55 📊 Instancias vivas: 4 | CPU promedio: 73.0% | Min: 2 | Max: 5
16:05:55 🔺 CPU 73.0% > 10.0% → SCALE OUT
16:05:55 ➕ Lanzando nueva instancia EC2 (AMI: ami-017a2c16b02373a3a)...
16:05:56 ✅ Instancia creada: i-0d752bb53c49a9297 (esperando IP pública...)
```

---

## 📊 Resumen de la Demo

| Evento | Hora | Instancias |
|--------|------|-----------|
| Arranque del sistema | 16:01:28 | 0 |
| Creación mínimo (2) | 16:01:39 | 2 |
| Scale-Out (CPU > 10%) | 16:03:53 | 3 |
| Scale-Out (CPU > 10%) | 16:05:16 | 4 → 5 |
| Scale-In (CPU < 90%) | 16:05:35 | 4 |
| Scale-Out (CPU > 10%) | 16:05:55 | 5 |

---

## ✅ Conclusión

El sistema Custom ASG demostró:
- Creación automática de instancias EC2 reales en AWS
- Scale-Out cuando CPU supera el umbral
- Scale-In cuando CPU baja del umbral
- Respeto de límites min=2 y max=5
- Cooldown entre acciones de escalamiento
- Monitoreo en tiempo real via gRPC
