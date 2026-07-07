#!/usr/bin/env python3
"""
C++ Tutor APK Builder
Compiles Java, generates binary AndroidManifest.xml, packages and signs APK.
"""

import struct
import xml.etree.ElementTree as ET
import zipfile
import os
import shutil
import subprocess
import sys
import hashlib
from pathlib import Path

HOME = os.path.expanduser("~")
PROJECT_DIR = os.path.join(HOME, "CppTutor")
SRC_DIR = os.path.join(PROJECT_DIR, "src")
ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")
MANIFEST_XML = os.path.join(PROJECT_DIR, "AndroidManifest.xml")
BUILD_DIR = os.path.join(PROJECT_DIR, "build")
CLASSES_DIR = os.path.join(BUILD_DIR, "classes")
APK_UNSIGNED = os.path.join(BUILD_DIR, "CppTutor-unsigned.apk")
APK_UNALIGNED = os.path.join(BUILD_DIR, "CppTutor-unaligned.apk")
APK_FINAL = os.path.join(BUILD_DIR, "CppTutor.apk")
KEYSTORE = os.path.join(BUILD_DIR, "debug.keystore")

ECJ_JAR = "/data/data/com.termux/files/usr/share/dex/ecj.jar"
ANDROID_JAR = "/data/data/com.termux/files/usr/share/java/android.jar"
DALVIKVM = "dalvikvm"
D8 = "d8"
APKSIGNER = "apksigner"

# Android framework attribute resource IDs (from android.R.attr)
ATTR_RES_IDS = {
    "versionCode": 0x0101021b,
    "versionName": 0x0101021c,
    "minSdkVersion": 0x0101020c,
    "targetSdkVersion": 0x01010270,
    "name": 0x01010003,
    "allowBackup": 0x01010280,
    "label": 0x01010001,
    "exported": 0x01010210,
    "icon": 0x01010002,
}


def write_u16(buf, val):
    buf.extend(struct.pack("<H", val))


def write_u32(buf, val):
    buf.extend(struct.pack("<I", val))


def build_string_pool(strings):
    """Build Android binary XML string pool chunk (type 0x0001).
    
    UTF-16 format: each string has uint16_t char_count followed by UTF-16LE chars.
    Strings are 4-byte aligned with null padding.
    """
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
    """Build XML namespace start chunk (type 0x0100).
    Structure: ResXMLTree_node (16) + ResXMLTree_namespaceExt (8) = 24 bytes
    """
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
    """Build XML namespace end chunk (type 0x0101)."""
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
    """Build XML start tag chunk (type 0x0102).
    
    Structure: ResXMLTree_node (16) + ResXMLTree_attrExt (20) + N * ResXMLTree_attribute (20 each)
    
    attributes: list of (ns_idx, name_idx, value_str_idx, value_type, value_data)
    """
    attr_count = len(attributes)
    chunk_size = 16 + 20 + attr_count * 20

    chunk = bytearray()
    write_u16(chunk, 0x0102)
    write_u16(chunk, 16)
    write_u32(chunk, chunk_size)
    write_u32(chunk, lineno)
    write_u32(chunk, 0xFFFFFFFF)

    # ResXMLTree_attrExt (starts at byte 16)
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


def write_u8(buf, val):
    buf.extend(struct.pack("<B", val))


def build_end_tag(ns_idx, name_idx, lineno):
    """Build XML end tag chunk (type 0x0103).
    Structure: ResXMLTree_node (16) + ResXMLTree_endElementExt (8) = 24 bytes
    """
    chunk = bytearray()
    write_u16(chunk, 0x0103)
    write_u16(chunk, 16)
    write_u32(chunk, 24)
    write_u32(chunk, lineno)
    write_u32(chunk, 0xFFFFFFFF)
    write_u32(chunk, ns_idx)
    write_u32(chunk, name_idx)
    return chunk


# Value types from android.util.TypedValue
TYPE_NULL = 0x00
TYPE_REFERENCE = 0x01
TYPE_STRING = 0x03
TYPE_INT_DEC = 0x10
TYPE_FLOAT = 0x04
TYPE_INT_HEX = 0x11
TYPE_INT_BOOLEAN = 0x12


def axml_int_value(v):
    """Convert a string to typed int value."""
    if v.startswith("0x"):
        return TYPE_INT_HEX, int(v, 16)
    return TYPE_INT_DEC, int(v)


def generate_axml(manifest_path):
    """Generate binary AndroidManifest.xml from plain XML."""
    tree = ET.parse(manifest_path)
    root = tree.getroot()

    # Collect all strings we need
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
        if "}" in tag:
            tag = tag.split("}", 1)[1]
        add_str(tag)

        if depth == 0:
            add_str("")  # empty namespace for root

        for key, val in elem.attrib.items():
            if "}" in key:
                attr_name = key.split("}", 1)[1]
            else:
                attr_name = key
            add_str(attr_name)
            add_str(val)

        for child in elem:
            collect_element(child, depth + 1)

    collect_element(root)

    intents = ["action", "category"]
    for intent in intents:
        add_str(intent)

    # Build string pool
    str_pool = build_string_pool(strings)

    # Build resource map: string pool index -> resource ID for android: attributes
    str_idx_to_rid = {}
    def build_res_map(elem):
        for key, val in elem.attrib.items():
            if "}" in key:
                ns, attr_name = key.split("}", 1)[0][1:], key.split("}", 1)[1]
                if ns == ns_android_uri and attr_name in ATTR_RES_IDS:
                    attr_name_idx = str_set[attr_name]
                    if attr_name_idx not in str_idx_to_rid:
                        str_idx_to_rid[attr_name_idx] = ATTR_RES_IDS[attr_name]
        for child in elem:
            build_res_map(child)
    build_res_map(root)

    # Build chunks
    chunks = bytearray()

    # XML document header
    write_u16(chunks, 0x0003)  # type = 3 (XML)
    write_u16(chunks, 0x0008)  # header_size = 8
    xml_size_pos = len(chunks)
    write_u32(chunks, 0)  # placeholder for total size

    chunks.extend(str_pool)

    if str_idx_to_rid:
        chunks.extend(build_resource_map(str_idx_to_rid))

    def write_element(elem, depth=0, lineno=10):
        tag = elem.tag
        if "}" in tag:
            tag = tag.split("}", 1)[1]
        tag_idx = str_set[tag]

        # Build attribute list for this element
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

            # Determine value type
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

        # Namespace for element
        if depth == 0:
            elem_ns = 0xFFFFFFFF  # root element has no namespace
        else:
            elem_ns = 0xFFFFFFFF

        chunks.extend(build_start_tag(elem_ns, tag_idx, attrs, lineno))

        for child in elem:
            write_element(child, depth + 1, lineno + 1)

        end_ns = 0xFFFFFFFF if depth > 0 else 0xFFFFFFFF
        chunks.extend(build_end_tag(end_ns, tag_idx, lineno))

    # Write namespace declaration
    chunks.extend(build_ns_start(ns_uri_idx, ns_prefix_idx, 2))
    write_element(root, 0, 3)
    chunks.extend(build_ns_end(ns_uri_idx, ns_prefix_idx, 30))

    # Fix total XML size
    total_size = len(chunks)
    struct.pack_into("<I", chunks, xml_size_pos, total_size)

    return bytes(chunks)


def compile_java():
    """Compile Java sources to .class files using ECJ."""
    print("[1/4] Compiling Java sources with ECJ...")
    os.makedirs(CLASSES_DIR, exist_ok=True)

    sources = list(Path(SRC_DIR).rglob("*.java"))
    if not sources:
        print("  No Java sources found!")
        return False

    cmd = [
        DALVIKVM, "-Xmx256m",
        "-cp", ECJ_JAR,
        "org.eclipse.jdt.internal.compiler.batch.Main",
        "-proc:none", "-1.7",
        "-cp", ANDROID_JAR,
        "-d", CLASSES_DIR,
    ] + [str(s) for s in sources]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("  ECJ errors:")
        print(result.stdout)
        print(result.stderr)
        return False

    print(f"  Compiled {len(sources)} files.")
    return True


def convert_to_dex():
    """Convert .class files to .dex using d8."""
    print("[2/4] Converting to DEX with d8...")
    class_files = list(Path(CLASSES_DIR).rglob("*.class"))
    if not class_files:
        print("  No class files found!")
        return False

    os.makedirs(os.path.join(BUILD_DIR, "apk"), exist_ok=True)

    cmd = [
        D8, "--lib", ANDROID_JAR,
        "--output", os.path.join(BUILD_DIR, "apk"),
        "--min-api", "21",
    ] + [str(cf) for cf in class_files]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("  d8 errors:")
        print(result.stdout)
        print(result.stderr)
        return False

    print("  DEX generated.")
    return True


def package_apk():
    """Package APK with proper 4-byte alignment for stored entries."""
    print("[3/4] Packaging APK...")

    dex_dir = os.path.join(BUILD_DIR, "apk")
    dex_file = os.path.join(dex_dir, "classes.dex")
    if not os.path.exists(dex_file):
        dex_files = sorted(Path(dex_dir).glob("classes*.dex"))
        if dex_files:
            dex_file = str(dex_files[0])
        else:
            print("  No classes.dex found!")
            return False

    print("  Generating binary AndroidManifest.xml...")
    try:
        axml = generate_axml(MANIFEST_XML)
    except Exception as e:
        print(f"  AXML generation failed: {e}")
        return False

    with open(dex_file, 'rb') as f:
        dex_data = f.read()

    assets = []
    if os.path.isdir(ASSETS_DIR):
        for fname in sorted(os.listdir(ASSETS_DIR)):
            fpath = os.path.join(ASSETS_DIR, fname)
            if os.path.isfile(fpath):
                with open(fpath, 'rb') as f:
                    assets.append(("assets/" + fname, f.read()))

    pos = 0
    with zipfile.ZipFile(APK_UNSIGNED, 'w', zipfile.ZIP_DEFLATED) as zf:
        for arcname, data, method in [
            ("AndroidManifest.xml", axml, zipfile.ZIP_STORED),
            ("classes.dex", dex_data, zipfile.ZIP_STORED),
        ] + [(a, d, zipfile.ZIP_DEFLATED) for a, d in assets]:
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

    print(f"  APK created: {APK_UNSIGNED} ({os.path.getsize(APK_UNSIGNED)} bytes)")
    return True


def sign_apk():
    """Sign the APK with debug keystore."""
    print("[4/4] Signing APK...")

    if not os.path.exists(KEYSTORE):
        print("  Generating debug keystore...")
        cmd = [
            "keytool", "-genkey", "-v",
            "-keystore", KEYSTORE,
            "-alias", "debug",
            "-keyalg", "RSA",
            "-keysize", "2048",
            "-validity", "10000",
            "-storepass", "android",
            "-keypass", "android",
            "-dname", "CN=CppTutor, O=Debug, C=US",
        ]
        subprocess.run(cmd, check=True)

    cmd = [
        APKSIGNER, "sign",
        "--ks", KEYSTORE,
        "--ks-pass", "pass:android",
        "--key-pass", "pass:android",
        "--out", APK_FINAL,
        APK_UNSIGNED,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("  Signing failed:")
        print(result.stdout)
        print(result.stderr)
        return False

    print(f"  Signed APK: {APK_FINAL} ({os.path.getsize(APK_FINAL)} bytes)")
    return True


def main():
    os.makedirs(BUILD_DIR, exist_ok=True)

    if not compile_java():
        sys.exit(1)
    if not convert_to_dex():
        sys.exit(1)
    if not package_apk():
        sys.exit(1)
    if not sign_apk():
        sys.exit(1)

    print(f"\n=== SUCCESS: {APK_FINAL} ===")
    size = os.path.getsize(APK_FINAL)
    print(f"  Size: {size} bytes ({size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
