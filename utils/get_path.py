import asyncio
import json
from typing import Any

import websockets


async def find_matching_urls_in_frames(devtools_ws_url: str, url_substring_to_find: str):
    """Finds URLs in the frame tree of a web page that match a given substring.

    Args:
        devtools_ws_url: _webSocketDebuggerUrl of the Thorium Reader_
        url_substring_to_find: _substring to search for in the URLs_

    Returns:
        A list of URLs that contain the specified substring.
        If no URLs are found, an empty list is returned.
    """
    found_urls: list[str] = []
    async with websockets.connect(devtools_ws_url) as websocket:
        # Enable Page domain
        await websocket.send(json.dumps({
            "id": 1,
            "method": "Page.enable"
        }))
        await websocket.recv()  # Wait for acknowledgment
        # print("Page.enable response received.")

        # Get the frame tree
        message_id_get_frame_tree = 2
        await websocket.send(json.dumps({
            "id": message_id_get_frame_tree,
            "method": "Page.getFrameTree"
        }))

        # Wait for the response
        while True:
            response_str = await websocket.recv()
            data = json.loads(response_str)

            if data.get("id") == message_id_get_frame_tree:
                if "result" in data and "frameTree" in data["result"]:
                    frame_tree_root: dict[str, dict[str, str]] = data["result"]["frameTree"]

                    def extract_urls_recursive(frame_node: dict[str, Any]):
                        frame = frame_node.get("frame")
                        if frame:
                            url: str = frame.get("url")
                            # print(f"Checking frame URL: {url}") # Debug print
                            if url and url_substring_to_find in url:
                                found_urls.append(url)

                        if "childFrames" in frame_node:
                            for child_frame_node in frame_node["childFrames"]:
                                extract_urls_recursive(child_frame_node)

                    extract_urls_recursive(frame_tree_root)
                elif "error" in data:
                    print(f"Error calling Page.getFrameTree: {data['error']['message']}")
                break  # Exit loop once our message ID is processed
            # else:
            #    print(f"Received other message: {data.get('method', data)}")

    return found_urls


async def get_base_path(devtools_ws_url: str):
    """Gets the base path from the Thorium Reader's frame tree by searching for a specific URL substring.

    Args:
        devtools_ws_url: _webSocketDebuggerUrl of the Thorium Reader_

    Returns:
        The base path of the Thorium Reader's frame tree if a matching URL is found, otherwise None.
    """
    SUBSTRING_TO_FIND = "httpsr2://"
    urls = await find_matching_urls_in_frames(devtools_ws_url, SUBSTRING_TO_FIND)
    if urls:
        for url in urls:
            # print(url)
            # If you want to extract the ID part specifically from the first found URL:
            if url.startswith("httpsr2://"):
                parts = url.split("/")
                base_url = "/".join(parts[:6])  # This will give you the base URL up to the protocol and ID
                return base_url + "/"

if __name__ == "__main__":
    DEVTOOLS_WS_URL = "ws://localhost:9223/devtools/page/AE2A68C6A2D2CA37336371B00B0E25B7"  # <<< REPLACE THIS
    res = asyncio.run(get_base_path(DEVTOOLS_WS_URL))
    print(f"Base path: {res}")
