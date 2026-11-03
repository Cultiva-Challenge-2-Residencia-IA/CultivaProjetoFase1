#!/usr/bin/env bash
# Prepara o ambiente de desenvolvimento sem instalar nada no sistema.
# Tudo fica dentro do repositório:
#   .uv/      binário do uv
#   .python/  Python 3.12 baixado pelo uv
#   .uv-cache cache de pacotes
#   .venv/    ambiente virtual do projeto (Python 3.12)
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

export UV_PYTHON_INSTALL_DIR="$ROOT/.python"
export UV_CACHE_DIR="$ROOT/.uv-cache"
export UV_TOOL_DIR="$ROOT/.uv/tools"
export UV_PYTHON_PREFERENCE=only-managed

if [ ! -x "$ROOT/.uv/bin/uv" ]; then
  echo "> instalando o uv em .uv/ (usando um venv temporário)"
  python3 -m venv "$ROOT/.uv/bootstrap"
  "$ROOT/.uv/bootstrap/bin/pip" install --quiet uv
  mkdir -p "$ROOT/.uv/bin"
  cp "$ROOT/.uv/bootstrap/bin/uv" "$ROOT/.uv/bin/uv"
  rm -rf "$ROOT/.uv/bootstrap"
fi

UV="$ROOT/.uv/bin/uv"

echo "> baixando o Python 3.12 para .python/"
"$UV" python install 3.12

echo "> criando .venv e instalando as dependências"
"$UV" sync

echo "> pronto. Use 'make test', 'make lint', 'make api' ou 'make eval-local'."
