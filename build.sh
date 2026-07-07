#!/data/data/com.termux/files/usr/bin/bash
set -e

PROJECT="CppTutor"
OUTPUT_DIR="$HOME/$PROJECT/build"
SRC_DIR="$HOME/$PROJECT/src"
ASSETS_DIR="$HOME/$PROJECT/assets"
LIB_DIR="$HOME/$PROJECT/lib"
MANIFEST="$HOME/$PROJECT/AndroidManifest.xml"

ECJ_JAR="/data/data/com.termux/files/usr/share/dex/ecj.jar"
JAVA_RUN="dalvikvm -Xmx256m -Xcompiler-option --compiler-filter=speed"
JAVA_ANDROID_JAR="/data/data/com.termux/files/usr/share/java/android.jar"

AAPT2=aapt2
D8=d8
APKSIGNER=apksigner

echo "=== C++ Tutor APK Builder (aapt2) ==="

rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/classes"
mkdir -p "$OUTPUT_DIR/apk"

echo "[1/4] Compilando Java sources con ECJ..."
SOURCES=$(find "$SRC_DIR" -name "*.java" | tr '\n' ' ')
$JAVA_RUN -cp "$ECJ_JAR" org.eclipse.jdt.internal.compiler.batch.Main \
    -proc:none \
    -1.7 \
    -cp "$JAVA_ANDROID_JAR" \
    -d "$OUTPUT_DIR/classes" \
    $SOURCES
echo "  Java classes compilados."

echo "[2/4] Convirtiendo a DEX con d8..."
$D8 --lib "$JAVA_ANDROID_JAR" \
    --output "$OUTPUT_DIR/apk" \
    --min-api 21 \
    $(find "$OUTPUT_DIR/classes" -name "*.class" | tr '\n' ' ')
echo "  DEX generado."

echo "[3/4] Empaquetando APK con aapt2..."
$AAPT2 link \
    --manifest "$MANIFEST" \
    -A "$ASSETS_DIR" \
    -o "$OUTPUT_DIR/apk/CppTutor-unsigned.apk" \
    --min-sdk-version 21 \
    --target-sdk-version 33 \
    --version-code 1 \
    --version-name "1.0" \
    --replace-version \
    2>&1 || true

if [ ! -f "$OUTPUT_DIR/apk/CppTutor-unsigned.apk" ]; then
    echo "  aapt2 fallo, usando metodo manual..."
    cd "$OUTPUT_DIR/apk"
    cp "$MANIFEST" ./AndroidManifest.xml
    zip -r "CppTutor-unsigned.apk" . 2>/dev/null
fi

# Insertar classes.dex
cd "$OUTPUT_DIR/apk"
if [ -f "CppTutor-unsigned.apk" ] && [ -f "classes.dex" ]; then
    aapt add "CppTutor-unsigned.apk" "classes.dex" 2>/dev/null || \
    zip -f "CppTutor-unsigned.apk" classes.dex 2>/dev/null || true
fi
cd "$HOME/$PROJECT"
echo "  APK empaquetado."

echo "[4/4] Firmando APK..."
KEYSTORE="$OUTPUT_DIR/debug.keystore"
if [ ! -f "$KEYSTORE" ]; then
    keytool -genkey -v -keystore "$KEYSTORE" \
        -alias debug -keyalg RSA -keysize 2048 \
        -validity 10000 \
        -storepass android -keypass android \
        -dname "CN=CppTutor, O=Debug, C=US"
fi

if [ -f "$OUTPUT_DIR/apk/CppTutor-unsigned.apk" ]; then
    $APKSIGNER sign --ks "$KEYSTORE" --ks-pass pass:android \
        --key-pass pass:android --out "$OUTPUT_DIR/CppTutor.apk" \
        "$OUTPUT_DIR/apk/CppTutor-unsigned.apk" 2>&1 || true
fi

if [ -f "$OUTPUT_DIR/CppTutor.apk" ]; then
    echo ""
    echo "=== APK generado: $OUTPUT_DIR/CppTutor.apk ==="
    ls -lh "$OUTPUT_DIR/CppTutor.apk"
else
    echo ""
    echo "=== ERROR: No se pudo generar el APK ==="
    echo "Construyendo APK manualmente con ZIP..."
    
    # Metodo manual final: crear ZIP con estructura APK
    rm -f "$OUTPUT_DIR/CppTutor.apk"
    cd "$OUTPUT_DIR"
    mkdir -p apk_manual
    cp "$MANIFEST" apk_manual/AndroidManifest.xml
    mkdir -p apk_manual/assets
    cp -r "$ASSETS_DIR"/* apk_manual/assets/ 2>/dev/null || true
    cp "$OUTPUT_DIR/apk/classes.dex" apk_manual/ 2>/dev/null || true
    
    cd apk_manual
    zip -r "$OUTPUT_DIR/CppTutor-unaligned.apk" . 2>/dev/null
    
    $APKSIGNER sign --ks "$KEYSTORE" --ks-pass pass:android \
        --key-pass pass:android --out "$OUTPUT_DIR/CppTutor.apk" \
        "$OUTPUT_DIR/CppTutor-unaligned.apk" 2>&1 || true
    
    cd "$HOME/$PROJECT"
    if [ -f "$OUTPUT_DIR/CppTutor.apk" ]; then
        echo "=== APK generado (manual): $OUTPUT_DIR/CppTutor.apk ==="
        ls -lh "$OUTPUT_DIR/CppTutor.apk"
    else
        echo "Fallo total. Ve al directorio build/ para investigar."
    fi
fi
