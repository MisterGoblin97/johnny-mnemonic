# Сборка «Карточки.app» через PyInstaller. Запускать не напрямую, а через ./build_app.sh:
# скрипт сначала готовит build/icon.icns из assets/icon.png.

APP_NAME = "Карточки"

a = Analysis(["main.py"])
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="cards",  # имя исполняемого файла внутри .app — латиницей
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="cards", upx=False)
app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon="build/icon.icns",
    bundle_identifier="dev.cards-learning",
    info_plist={
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleShortVersionString": "1.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,  # иначе macOS не даст включить тёмную тему
        "LSApplicationCategoryType": "public.app-category.education",
    },
)
