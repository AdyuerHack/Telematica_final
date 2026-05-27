#!/usr/bin/env bash
# generate_proto.sh  ──  Genera los stubs Python a partir del .proto
# Ejecutar desde la raíz del proyecto:  bash generate_proto.sh

set -e

PROTO_DIR="proto"
OUT_DIR="generated"

mkdir -p "$OUT_DIR"

python -m grpc_tools.protoc \
    -I "$PROTO_DIR" \
    --python_out="$OUT_DIR" \
    --grpc_python_out="$OUT_DIR" \
    "$PROTO_DIR/monitor.proto"

echo "✅ Stubs generados en ./$OUT_DIR/"
