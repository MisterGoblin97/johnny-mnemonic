#!/bin/zsh
# Собирает «Карточки.app» и кладёт его в «Программы».
# Запускайте заново после каждого изменения кода: ./build_app.sh
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="Карточки"
PYTHON="${PYTHON:-python3.14}"

if pgrep -f "$APP_NAME.app/Contents/MacOS/" >/dev/null; then
  echo "Сначала закройте «$APP_NAME», потом запустите сборку ещё раз." >&2
  exit 1
fi

echo "→ Окружение для сборки (.venv)"
[[ -x .venv/bin/python ]] || "$PYTHON" -m venv .venv
.venv/bin/pip install --quiet --upgrade pyinstaller

echo "→ Иконка"
iconset=build/icon.iconset
rm -rf "$iconset" && mkdir -p "$iconset"
for size in 16 32 128 256 512; do
  sips -z $size $size assets/icon.png --out "$iconset/icon_${size}x${size}.png" >/dev/null
  sips -z $((size * 2)) $((size * 2)) assets/icon.png --out "$iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$iconset" -o build/icon.icns

echo "→ Сборка"
.venv/bin/pyinstaller --noconfirm --clean --log-level WARN cards.spec

echo "→ Установка"
dest=/Applications
[[ -w $dest ]] || dest="$HOME/Applications"
mkdir -p "$dest"
rm -rf "$dest/$APP_NAME.app"
ditto "dist/$APP_NAME.app" "$dest/$APP_NAME.app"
touch "$dest/$APP_NAME.app"  # чтобы Finder и Dock подхватили новую иконку

echo "Готово: $dest/$APP_NAME.app"
