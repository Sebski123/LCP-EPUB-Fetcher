import asyncio
import os
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
import zipfile
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup  # pyright: ignore[reportMissingTypeStubs]

from utils import find_thorium_path
from utils.fetch import fetch_file, get_pdf_chunks_parallel
from utils.get_path import get_base_path
from utils.hide_windows import monitor_and_hide_program_by_pid


async def main(file_path: str):
    """Main function to fetch content from an epub file using Thorium Reader's remote debugging interface.

    Args:
        epub_path: _path to the epub file to fetch content from_
    """

    # 0. Check if the epub or lcpdf file exists and if there already is a _fetched.epub or _fetched.lcpdf file
    if not os.path.exists(file_path):
        print(f"Error: The file {file_path} does not exist.")
        return
    if file_path.endswith("_fetched.epub") or file_path.endswith("_fetched.lcpdf"):
        print(f"Error: The file {file_path} already seems to be fetched. Please provide a different file.")
        return
    if not (file_path.endswith(".epub") or file_path.endswith(".lcpdf")):
        print(f"Error: The file {file_path} is not a valid epub or lcpdf file.")
        return
    if file_path.endswith(".epub"):
        out_ext = ".epub"
        out_filename = os.path.splitext(file_path)[0] + f"_fetched{out_ext}"
    else:
        out_ext = ".lcpdf"
        out_filename = os.path.splitext(file_path)[0]

    if os.path.exists(out_filename):
        response = input(f"The file {out_filename} already exists. Do you want to replace it? (y/N): ").strip().lower()
        if response != 'y':
            print("Operation cancelled.")
            return

    # 0.5 Check if Thorium Reader is already running, if so, ask to close it
    thorium_path = find_thorium_path()
    for proc in subprocess.run(['tasklist'], capture_output=True, text=True).stdout.splitlines():
        if os.path.basename(thorium_path).lower() in proc.lower():
            response = input(
                "Thorium Reader is already running. Please close it and then press enter to continue. To cancel type 'exit' and press enter").strip().lower()
            if response == 'exit':
                print("Operation cancelled.")
                return
            break

    # 1. Launch Thorium Reader with debug args
    proc = subprocess.Popen(
        [
            thorium_path,
            file_path,
            "--remote-debugging-port=9223",
            "--remote-allow-origins=*",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Start the monitor thread
    # This thread will hide any Thorium Reader window if it becomes visible
    stop_event = threading.Event()
    monitor_thread = threading.Thread(target=monitor_and_hide_program_by_pid, args=(proc.pid, stop_event))
    monitor_thread.start()

    try:
        # 2. Wait for debugger to be ready
        for _ in range(30):
            try:
                resp = requests.get("http://localhost:9223/json", timeout=5)
                if resp.ok:
                    if len(resp.json()) == 3:
                        break
                    else:
                        print("Waiting for Thorium remote debugger to be ready...")
                        time.sleep(1)
            except (requests.ConnectionError, requests.Timeout):
                time.sleep(1)
            except KeyboardInterrupt:
                print("Operation cancelled by user.")
                proc.terminate()
                stop_event.set()
                monitor_thread.join()
                return
        else:
            print("Could not connect to Thorium remote debugger.")
            stop_event.set()
            monitor_thread.join()
            return

        print("Thorium Reader is ready for remote debugging.")

        # Stop the monitor thread
        stop_event.set()
        monitor_thread.join()

        # 3. Find webSocketDebuggerUrl
        targets = resp.json()
        ws_url = None
        for t in targets:
            if t.get("parentId", "") != "":
                # Look for a target with a parentId, which is likely the main page
                ws_url = t.get("webSocketDebuggerUrl")
                url = t.get("url")
                break
        if not ws_url:
            ws_url = targets[0].get("webSocketDebuggerUrl")
        if not ws_url:
            print("Could not find webSocketDebuggerUrl.")
            return

        if out_ext == ".lcpdf":
            # for .lcpdf files, we just fetch the single pdf file inside
            print("Fetching pdf file from lcpdf...")

            # a. extract pdf path from the url
            url_parts = url.split('file=')
            if len(url_parts) != 2:
                print("Could not extract pdf file path from lcpdf url.")
                return
            pdf_path_raw = url_parts[1]

            # b. decode url encoding
            pdf_path = unquote(pdf_path_raw)

            # c. Option to trigger browser download or fetch via chunks
            browser_download = '--browser-download' in sys.argv
            if browser_download:
                from utils.fetch import trigger_browser_blob_download
                print("Triggering browser download via Blob URL...")
                # Use the output filename as the download name
                await trigger_browser_blob_download(ws_url, pdf_path, os.path.basename(out_filename))
                input("Press Enter to continue...")
                return
            # e. Write the PDF file in chunks using the new parallel chunk fetcher
            with open(out_filename, "wb") as f:
                async for chunk in get_pdf_chunks_parallel(ws_url, pdf_path, chunk_size=512*1024, max_concurrency=8):
                    if chunk:
                        f.write(chunk)
            print(f"Fetched and wrote PDF to {out_filename}")

        else:  # .epub
            # 4. Extract package.opf from epub
            with zipfile.ZipFile(file_path, 'r') as zf:
                opf_path = None
                # Find the path to package.opf from META-INF/container.xml
                with zf.open("META-INF/container.xml") as f:
                    tree = ET.parse(f)
                    rootfile = tree.find(".//{*}rootfile")
                    assert rootfile is not None, "No rootfile found in container.xml"
                    opf_path = rootfile.attrib['full-path']
                with zf.open(opf_path) as f:
                    opf_xml = f.read()
                tree = ET.fromstring(opf_xml)
                ns = {'opf': 'http://www.idpf.org/2007/opf'}
                manifest = tree.find('.//opf:manifest', ns)
                assert manifest is not None, "No manifest found in package.opf"
                file_list = [(item.attrib['media-type'], item.attrib['href'])
                             for item in manifest.findall('opf:item', ns)]

            # 5. Fetch each file using get_content_via_evaluate, with progress (parallelized)
            resource_url = await get_base_path(ws_url)
            assert resource_url is not None, "Could not get base path from Thorium Reader"
            base_dir = resource_url + os.path.dirname(opf_path)
            fetched_files: dict[str, str | bytes] = {}
            total_files = len(file_list)

            print(f"Fetching {total_files-1} files from epub...")  # Exclude nav.xhtml

            tasks = [
                fetch_file(base_dir, ws_url, file_type, file)
                for _, (file_type, file) in enumerate(file_list, 1)
            ]
            results = await asyncio.gather(*tasks)
            for filename, content in results:
                if filename and content:
                    fetched_files[filename] = content
            print(f"Fetched {len(fetched_files)} files.")

            # 6. Filter the fetched files
            # the fetched xhtml files contains a bunch of javascript/css that is not needed
            # in the HEAD section we only need the title and the link to the css file, and meta tags
            print("Filtering fetched files...")
            for filename, content in fetched_files.items():
                if filename.endswith(".xhtml"):
                    # Filter the content to keep only the title, link to css, and meta tags
                    soup = BeautifulSoup(content, 'html.parser')
                    head = soup.head
                    if head:
                        # Keep only title and link tags
                        title = head.find('title')
                        links = head.find_all('link', rel='stylesheet')
                        metas = head.find_all('meta')
                        new_head = soup.new_tag('head')  # type: ignore
                        if title:
                            new_head.append(title)
                        for link in links:
                            # Skip Thorium/Readium specific styles
                            if "thorium" in link.get('href', '') or "readium" in link.get('href', ''):
                                continue
                            new_head.append(link)
                        for meta in metas:
                            new_head.append(meta)
                        head.replace_with(new_head)
                    # Remove readium-related attributes from the html tag
                    html_tag = soup.find('html')
                    if html_tag:
                        attrs_to_remove: list[str] = [
                            attr for attr in html_tag.attrs if 'readium' in attr.lower()]  # type: ignore
                        for attr in attrs_to_remove:
                            del html_tag[attr]  # type: ignore
                    fetched_files[filename] = str(soup)

            # 7. Repackage into new epub
            print("Repackaging epub with fetched content...")
            out_filename = os.path.splitext(file_path)[0] + "_fetched.epub"
            if os.path.exists(out_filename):
                os.remove(out_filename)  # Remove existing file if it exists

            with zipfile.ZipFile(out_filename, 'w') as out_zf:
                # Write mimetype first, uncompressed
                with zipfile.ZipFile(file_path, 'r') as zf:
                    out_zf.writestr("mimetype", zf.read("mimetype"), compress_type=zipfile.ZIP_STORED)
                # Write all other files, replacing with fetched if available
                with zipfile.ZipFile(file_path, 'r') as zf:
                    for item in zf.infolist():
                        filename = item.filename.split("/")[-1]
                        if filename == "mimetype" or filename == "encryption.xml" or filename == "license.lcpl":
                            continue
                        data = fetched_files.get(filename)
                        if data is None:
                            # continue  # Skip if no fetched content
                            data = zf.read(item.filename)
                        out_zf.writestr(item, data)
            print(f"Repackaged epub written to {out_filename}")

    finally:
        proc.terminate()


if __name__ == "__main__":
    if len(sys.argv) != 2 and len(sys.argv) != 3:
        print("Usage: python main.py <epub_path>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
