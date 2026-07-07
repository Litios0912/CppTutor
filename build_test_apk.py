#!/usr/bin/env python3
import struct, zipfile, os, shutil, subprocess, sys, hashlib
from pathlib import Path

HOME = os.path.expanduser("~")
PROJECT_DIR = os.path.join(HOME, "CppTutor")
SRC_DIR = os.path.join(PROJECT_DIR, "src_min")
MANIFEST_XML = os.path.join(PROJECT_DIR, "AndroidManifest_test.xml")
BUILD_DIR = os.path.join(PROJECT_DIR, "build_test")
CLASSES_DIR = os.path.join(BUILD_DIR, "classes")
APK_UNSIGNED = os.path.join(BUILD_DIR, "Test-unsigned.apk")
APK_FINAL = os.path.join(BUILD_DIR, "Test.apk")
KEYSTORE = os.path.join(BUILD_DIR, "debug.keystore")

ECJ_JAR = "/data/data/com.termux/files/usr/share/dex/ecj.jar"
ANDROID_JAR = "/data/data/com.termux/files/usr/share/java/android.jar"
DALVIKVM = "dalvikvm"
D8 = "d8"
APKSIGNER = "apksigner"

ATTR_RES_IDS = {
    "versionCode": 0x0101021b,
    "versionName": 0x0101021c,
    "minSdkVersion": 0x0101020c,
    "targetSdkVersion": 0x01010270,
    "name": 0x01010003,
    "allowBackup": 0x01010280,
    "label": 0x01010001,
    "exported": 0x01010210,
}

def write_u16(buf, val): buf.extend(struct.pack("<H", val))
def write_u32(buf, val): buf.extend(struct.pack("<I", val))
def write_u8(buf, val): buf.extend(struct.pack("<B", val))

def build_string_pool(strings):
    header_size = 28
    str_count = len(strings)
    str_offsets = []
    str_data = bytearray()
    for s in strings:
        str_offsets.append(len(str_data))
        encoded = s.encode("utf-16-le")
        write_u16(str_data, len(s))
        str_data.extend(encoded)
        str_data.extend(b"\x00\x00")
    while len(str_data) % 4 != 0:
        str_data.extend(b"\x00\x00")
    offsets_size = str_count * 4
    strings_start = header_size + offsets_size
    chunk_size = strings_start + len(str_data)
    chunk = bytearray()
    write_u16(chunk, 0x0001)
    write_u16(chunk, header_size)
    write_u32(chunk, chunk_size)
    write_u32(chunk, str_count)
    write_u32(chunk, 0)
    write_u32(chunk, 0)
    write_u32(chunk, strings_start)
    write_u32(chunk, 0)
    for off in str_offsets:
        write_u32(chunk, off)
    chunk.extend(str_data)
    return chunk

def build_resource_map(str_idx_to_rid):
    """Build XML resource map chunk (type 0x0180).
    Resource map is indexed by string pool position.
    Must cover indices 0..max_idx, with 0 for entries without resource ID.
    """
    max_idx = max(str_idx_to_rid.keys()) if str_idx_to_rid else -1
    if max_idx < 0:
        return bytearray()
    size = max_idx + 1
    chunk = bytearray()
    write_u16(chunk, 0x0180)
    write_u16(chunk, 8)
    write_u32(chunk, 8 + size * 4)
    for i in range(size):
        rid = str_idx_to_rid.get(i, 0)
        write_u32(chunk, rid)
    return chunk

def build_ns_start(ns_idx, prefix_idx, lineno=2):
    chunk = bytearray()
    write_u16(chunk, 0x0100)
    write_u16(chunk, 16)
    write_u32(chunk, 24)
    write_u32(chunk, lineno)
    write_u32(chunk, 0xFFFFFFFF)
    write_u32(chunk, prefix_idx)
    write_u32(chunk, ns_idx)
    return chunk

def build_ns_end(ns_idx, prefix_idx, lineno=2):
    chunk = bytearray()
    write_u16(chunk, 0x0101)
    write_u16(chunk, 16)
    write_u32(chunk, 24)
    write_u32(chunk, lineno)
    write_u32(chunk, 0xFFFFFFFF)
    write_u32(chunk, prefix_idx)
    write_u32(chunk, ns_idx)
    return chunk

def build_start_tag(ns_idx, name_idx, attributes, lineno):
    attr_count = len(attributes)
    chunk_size = 16 + 20 + attr_count * 20
    chunk = bytearray()
    write_u16(chunk, 0x0102)
    write_u16(chunk, 16)
    write_u32(chunk, chunk_size)
    write_u32(chunk, lineno)
    write_u32(chunk, 0xFFFFFFFF)
    write_u32(chunk, ns_idx)
    write_u32(chunk, name_idx)
    write_u16(chunk, 20)
    write_u16(chunk, 20)
    write_u16(chunk, attr_count)
    write_u16(chunk, 0)
    write_u16(chunk, 0)
    write_u16(chunk, 0)
    for ns_i, name_i, val_i, vtype, vdata in attributes:
        write_u32(chunk, ns_i)
        write_u32(chunk, name_i)
        write_u32(chunk, val_i)
        write_u16(chunk, 8)
        write_u8(chunk, 0)
        write_u8(chunk, vtype)
        write_u32(chunk, vdata)
    return chunk

def build_end_tag(ns_idx, name_idx, lineno):
    chunk = bytearray()
    write_u16(chunk, 0x0103)
    write_u16(chunk, 16)
    write_u32(chunk, 24)
    write_u32(chunk, lineno)
    write_u32(chunk, 0xFFFFFFFF)
    write_u32(chunk, ns_idx)
    write_u32(chunk, name_idx)
    return chunk

TYPE_NULL = 0x00
TYPE_REFERENCE = 0x01
TYPE_STRING = 0x03
TYPE_INT_DEC = 0x10
TYPE_FLOAT = 0x04
TYPE_INT_HEX = 0x11
TYPE_INT_BOOLEAN = 0x12

def axml_int_value(v):
    if v.startswith("0x"):
        return TYPE_INT_HEX, int(v, 16)
    return TYPE_INT_DEC, int(v)

def generate_axml(manifest_path):
    import xml.etree.ElementTree as ET
    tree = ET.parse(manifest_path)
    root = tree.getroot()
    strings = []
    str_set = {}
    def add_str(s):
        if s not in str_set:
            str_set[s] = len(strings)
            strings.append(s)
        return str_set[s]
    ns_android_uri = "http://schemas.android.com/apk/res/android"
    ns_android_prefix = "android"
    ns_uri_idx = add_str(ns_android_uri)
    ns_prefix_idx = add_str(ns_android_prefix)
    def collect_element(elem, depth=0):
        tag = elem.tag
        if "}" in tag: tag = tag.split("}", 1)[1]
        add_str(tag)
        for key, val in elem.attrib.items():
            if "}" in key: attr_name = key.split("}", 1)[1]
            else: attr_name = key
            add_str(attr_name)
            add_str(val)
        for child in elem:
            collect_element(child, depth + 1)
    collect_element(root)
    intents = ["action", "category"]
    for intent in intents: add_str(intent)
    str_pool = build_string_pool(strings)

    # Build resource map: string pool index -> resource ID for android: attributes
    str_idx_to_rid = {}
    def build_res_map(elem):
        for key, val in elem.attrib.items():
            if "}" in key:
                ns_attr, attr_name = key.split("}", 1)[0][1:], key.split("}", 1)[1]
                if ns_attr == ns_android_uri and attr_name in ATTR_RES_IDS:
                    attr_name_idx = str_set[attr_name]
                    if attr_name_idx not in str_idx_to_rid:
                        str_idx_to_rid[attr_name_idx] = ATTR_RES_IDS[attr_name]
        for child in elem:
            build_res_map(child)
    build_res_map(root)

    chunks = bytearray()
    write_u16(chunks, 0x0003)
    write_u16(chunks, 0x0008)
    xml_size_pos = len(chunks)
    write_u32(chunks, 0)
    chunks.extend(str_pool)
    if str_idx_to_rid:
        chunks.extend(build_resource_map(str_idx_to_rid))
    def write_element(elem, depth=0, lineno=10):
        tag = elem.tag
        if "}" in tag: tag = tag.split("}", 1)[1]
        tag_idx = str_set[tag]
        attrs = []
        for key, val in elem.attrib.items():
            if "}" in key:
                ns_uri = key.split("}", 1)[0][1:]
                attr_name = key.split("}", 1)[1]
                ns_idx = str_set[ns_uri]
            else:
                ns_idx = 0xFFFFFFFF
                attr_name = key
            attr_name_idx = str_set[attr_name]
            val_idx = str_set[val]
            if attr_name in ("versionCode", "minSdkVersion", "targetSdkVersion"):
                vtype, vdata = axml_int_value(val)
            elif attr_name == "versionName":
                vtype, vdata = TYPE_STRING, val_idx
            elif val == "true":
                vtype, vdata = TYPE_INT_BOOLEAN, 1
            elif val == "false":
                vtype, vdata = TYPE_INT_BOOLEAN, 0
            elif val.startswith("0x"):
                vtype, vdata = TYPE_INT_HEX, int(val, 16)
            elif val.isdigit():
                vtype, vdata = TYPE_INT_DEC, int(val)
            else:
                vtype, vdata = TYPE_STRING, val_idx
            attrs.append((ns_idx, attr_name_idx, val_idx, vtype, vdata))
        elem_ns = 0xFFFFFFFF
        chunks.extend(build_start_tag(elem_ns, tag_idx, attrs, lineno))
        for child in elem:
            write_element(child, depth + 1, lineno + 1)
        chunks.extend(build_end_tag(0xFFFFFFFF, tag_idx, lineno))
    chunks.extend(build_ns_start(ns_uri_idx, ns_prefix_idx, 2))
    write_element(root, 0, 3)
    chunks.extend(build_ns_end(ns_uri_idx, ns_prefix_idx, 20))
    total_size = len(chunks)
    struct.pack_into("<I", chunks, xml_size_pos, total_size)
    return bytes(chunks)

# Build
os.makedirs(CLASSES_DIR, exist_ok=True)
print("[1/3] Compiling...")
sources = list(Path(SRC_DIR).rglob("*.java"))
cmd = [DALVIKVM, "-Xmx256m", "-cp", ECJ_JAR, "org.eclipse.jdt.internal.compiler.batch.Main", "-proc:none", "-1.7", "-cp", ANDROID_JAR, "-d", CLASSES_DIR] + [str(s) for s in sources]
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print(result.stdout, result.stderr); sys.exit(1)
print(f"  OK ({len(sources)} files)")

print("[2/3] DEX...")
class_files = list(Path(CLASSES_DIR).rglob("*.class"))
cmd = [D8, "--lib", ANDROID_JAR, "--output", BUILD_DIR, "--min-api", "21"] + [str(cf) for cf in class_files]
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print(result.stdout, result.stderr); sys.exit(1)
print("  OK")

print("[3/3] Packaging APK...")
dex_file = os.path.join(BUILD_DIR, "classes.dex")
if not os.path.exists(dex_file):
    dex_files = sorted(Path(BUILD_DIR).glob("classes*.dex"))
    if dex_files: dex_file = str(dex_files[0])
    else: print("No DEX"); sys.exit(1)

axml = generate_axml(MANIFEST_XML)

with open(dex_file, 'rb') as f: dex_data = f.read()

pos = 0
with zipfile.ZipFile(APK_UNSIGNED, 'w', zipfile.ZIP_DEFLATED) as zf:
    for arcname, data, method in [
        ("AndroidManifest.xml", axml, zipfile.ZIP_STORED),
        ("classes.dex", dex_data, zipfile.ZIP_STORED),
    ]:
        info = zipfile.ZipInfo(arcname)
        info.compress_type = method
        info.extra = b''
        if method == zipfile.ZIP_STORED:
            base = pos + 30 + len(arcname)
            padding = (4 - base % 4) % 4
            if padding:
                info.extra = b'\x00' * padding
        zf.writestr(info, data)
        pos = pos + 30 + len(arcname) + len(info.extra) + len(data)

print(f"  Unsigned: {os.path.getsize(APK_UNSIGNED)} bytes")

print("[4/4] Signing...")
if not os.path.exists(KEYSTORE):
    subprocess.run(["keytool", "-genkey", "-v", "-keystore", KEYSTORE, "-alias", "debug",
        "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
        "-storepass", "android", "-keypass", "android",
        "-dname", "CN=Test, O=Debug, C=US"], check=True)

cmd = [APKSIGNER, "sign", "--ks", KEYSTORE, "--ks-pass", "pass:android",
       "--key-pass", "pass:android", "--out", APK_FINAL, APK_UNSIGNED]
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print(result.stdout, result.stderr); sys.exit(1)

print(f"  Signed: {os.path.getsize(APK_FINAL)} bytes")
print(f"\n=== DONE: {APK_FINAL} ===")
