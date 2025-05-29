import asyncio
import os
import subprocess
import sys
import time
import zipfile

import requests

from utils.fettch import get_content_via_evaluate, get_image_via_evaluate
from utils.get_path import get_base_path


async def main(epub_path):
    # 1. Launch Thorium Reader with debug args
    thorium_path = R"C:\Users\sebth\AppData\Local\Programs\Thorium\Thorium.exe"  # Adjust if needed
    proc = subprocess.Popen([
        thorium_path,
        epub_path,
        "--remote-debugging-port=9223",
        "--remote-allow-origins=*",
    ])

    try:
        # 2. Wait for debugger to be ready
        for _ in range(30):
            try:
                resp = requests.get("http://localhost:9223/json")
                if resp.ok:
                    if len(resp.json()) == 3:
                        break
                    else:
                        print("Waiting for Thorium remote debugger to be ready...")
                        time.sleep(1)
            except Exception:
                time.sleep(1)
        else:
            print("Could not connect to Thorium remote debugger.")
            return

        # 3. Find webSocketDebuggerUrl
        targets = resp.json()
        ws_url = None
        for t in targets:
            if t.get("parentId", "") != "":
                # Look for a target with a parentId, which is likely the main page
                ws_url = t.get("webSocketDebuggerUrl")
                break
        if not ws_url:
            ws_url = targets[0].get("webSocketDebuggerUrl")
        if not ws_url:
            print("Could not find webSocketDebuggerUrl.")
            return

        # 4. Extract package.opf from epub
        with zipfile.ZipFile(epub_path, 'r') as zf:
            opf_path = None
            # Find the path to package.opf from META-INF/container.xml
            with zf.open("META-INF/container.xml") as f:
                import xml.etree.ElementTree as ET
                tree = ET.parse(f)
                rootfile = tree.find(".//{*}rootfile")
                opf_path = rootfile.attrib['full-path']
            with zf.open(opf_path) as f:
                opf_xml = f.read()
            tree = ET.fromstring(opf_xml)
            ns = {'opf': 'http://www.idpf.org/2007/opf'}
            manifest = tree.find('.//opf:manifest', ns)
            file_list = [(item.attrib['media-type'], item.attrib['href']) for item in manifest.findall('opf:item', ns)]

        # 5. Fetch each file using get_content_via_evaluate
        recource_url = await get_base_path(ws_url)
        base_dir = recource_url + os.path.dirname(opf_path)
        fetched_files = {}
        for file_type, file in file_list:
            if file == "nav.xhtml":
                continue
            if file_type.startswith("application/xhtml+xml") or file_type.startswith("text/css"):
                file_path = os.path.normpath(os.path.join(base_dir, file))
                url = file_path  # "file:///" + os.path.abspath(file_path).replace("\\", "/")
                content = await get_content_via_evaluate(ws_url, url)
                fetched_files[file_path.split("\\")[-1]] = content
            elif file_type.startswith("image/"):
                file_path = os.path.normpath(os.path.join(base_dir, file))
                url = file_path  # "file:///" + os.path.abspath(file_path).replace("\\", "/")
                content = await get_image_via_evaluate(ws_url, url)
                fetched_files[file_path.split("\\")[-1]] = content

        # 6. Repackage into new epub
        out_epub = os.path.splitext(epub_path)[0] + "_fetched.epub"
        with zipfile.ZipFile(out_epub, 'w') as out_zf:
            # Write mimetype first, uncompressed
            with zipfile.ZipFile(epub_path, 'r') as zf:
                out_zf.writestr("mimetype", zf.read("mimetype"), compress_type=zipfile.ZIP_STORED)
            # Write all other files, replacing with fetched if available
            with zipfile.ZipFile(epub_path, 'r') as zf:
                for item in zf.infolist():
                    filename = item.filename.split("/")[-1]
                    if filename == "mimetype" or filename == "encryption.xml" or filename == "license.lcpl":
                        continue
                    data = fetched_files.get(filename)
                    if data is None:
                        # continue  # Skip if no fetched content
                        data = zf.read(item.filename)
                    out_zf.writestr(item, data)
        print(f"Repackaged epub written to {out_epub}")
    finally:
        pass
        proc.terminate()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python main.py <epub_path>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
