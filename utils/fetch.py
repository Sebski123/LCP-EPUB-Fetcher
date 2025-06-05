import base64
import json
import os

import websockets


async def get_content_via_evaluate(devtools_ws_url: str, resource_url: str):
    """Fetch content from a resource URL using the Chrome DevTools Protocol's Runtime.evaluate method.

    Args:
        devtools_ws_url: _webSocketDebuggerUrl of the Chrome DevTools Protocol_
        resource_url: _URL of the resource to fetch content from, typically a file in the epub_

    Returns:
        The content of the resource as a string, or None if an error occurs.
        If the resource is not needed (like nav.xhtml), it returns None.
    """
    async with websockets.connect(devtools_ws_url) as websocket:
        # Enable Runtime domain
        await websocket.send(json.dumps({
            "id": 1,  # Unique message ID
            "method": "Runtime.enable"
        }))
        _ = await websocket.recv()  # Wait for acknowledgment
        # print(f"Runtime.enable response: {response}")

        # Optional: Get Page Tree to confirm frame context if needed,
        # but Runtime.evaluate by default runs in the main frame's context
        # unless a specific contextId is provided.
        # For fetching a resource URL known to the page, default context is usually fine.

        # JavaScript expression to fetch the content
        # We use an async IIFE (Immediately Invoked Function Expression)
        # to handle the promise from fetch.
        js_resource_url = json.dumps(resource_url)
        expression = f"""
        (async () => {{
            try {{
                const response = await fetch({js_resource_url});
                if (!response.ok) {{
                    return {{ error: `Fetch failed: ${{response.status}} ${{response.statusText}}` }};
                }}
                const content = await response.text();
                return {{ success: true, content: content }};
            }} catch (e) {{
                return {{ error: e.toString() }};
            }}
        }})()
        """

        # Execute the expression
        message_id_evaluate = 2  # Unique message ID
        await websocket.send(json.dumps({
            "id": message_id_evaluate,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "awaitPromise": True,  # Important: wait for the promise to resolve
                "returnByValue": True  # Try to get the full string value
            }
        }))

        # Wait for the response
        while True:
            response_str = await websocket.recv()
            data = json.loads(response_str)

            if data.get("id") == message_id_evaluate:
                if "result" in data and "result" in data["result"]:
                    eval_result = data["result"]["result"]["value"]  # The actual value returned by the JS

                    if isinstance(eval_result, dict) and eval_result.get("success"):  # type: ignore
                        assert isinstance(eval_result["content"], str), "Expected content to be a string"
                        content: str = eval_result["content"]
                        # print("Content fetched successfully via Runtime.evaluate!")
                        # with open("downloaded_file_runtime.html", "w", encoding="utf-8") as f:
                        #     f.write(content)
                        # print("Saved content to downloaded_file_runtime.html")
                        return content
                    elif isinstance(eval_result, dict) and eval_result.get("error"):  # type: ignore
                        print(f"Error during fetch in page context: {eval_result['error']}")
                        return None
                    else:
                        # This case might occur if the JS returns something unexpected
                        print(f"Unexpected result from Runtime.evaluate: {eval_result}")
                        return None

                elif "error" in data:
                    print(
                        f"Error executing Runtime.evaluate: {data['error']['message']} (Code: {data['error'].get('code')})")
                    print(f"Details: {data['error'].get('data')}")
                    return None
                elif "result" in data and "exceptionDetails" in data["result"]:
                    print("Exception during Runtime.evaluate:")
                    print(json.dumps(data["result"]["exceptionDetails"], indent=2))
                    return None
                break  # Exit loop once our message ID is processed
            # else:
            #    print(f"Received other message: {data.get('method', data)}")


async def get_image_via_evaluate(devtools_ws_url: str, image_url: str):
    """Fetch an image from a URL using the Chrome DevTools Protocol's Runtime.evaluate method.

    Args:
        devtools_ws_url: _webSocketDebuggerUrl of the Chrome DevTools Protocol_
        image_url: _URL of the image to fetch, typically a file in the epub_

    Returns:
        The image content as bytes, or None if an error occurs.
        If the image is not needed, it returns None.
    """
    async with websockets.connect(devtools_ws_url) as websocket:
        await websocket.send(json.dumps({
            "id": 1,
            "method": "Runtime.enable"
        }))
        await websocket.recv()

        js_image_url = json.dumps(image_url)
        expression = f"""
        (async () => {{
            try {{
                const response = await fetch({js_image_url});
                if (!response.ok) {{
                    return {{ error: `Fetch failed: ${{response.status}} ${{response.statusText}}` }};
                }}
                const blob = await response.blob();
                const arrayBuffer = await blob.arrayBuffer();
                const uint8Array = new Uint8Array(arrayBuffer);
                // Convert to base64
                let binary = '';
                for (let i = 0; i < uint8Array.length; i++) {{
                    binary += String.fromCharCode(uint8Array[i]);
                }}
                const base64String = btoa(binary);
                return {{ success: true, base64: base64String }};
            }} catch (e) {{
                return {{ error: e.toString() }};
            }}
        }})()
        """

        message_id_evaluate = 2
        await websocket.send(json.dumps({
            "id": message_id_evaluate,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True
            }
        }))

        while True:
            response_str = await websocket.recv()
            data = json.loads(response_str)

            if data.get("id") == message_id_evaluate:
                if "result" in data and "result" in data["result"]:
                    eval_result = data["result"]["result"]["value"]

                    if isinstance(eval_result, dict) and eval_result.get("success"):  # type: ignore
                        assert isinstance(eval_result["base64"], str), "Expected base64 to be a string"
                        base64_data = eval_result["base64"]
                        # print("Image fetched successfully via Runtime.evaluate!")
                        # To save as file:
                        # with open("downloaded_image.png", "wb") as f:
                        #     f.write(base64.b64decode(base64_data))
                        return base64.b64decode(base64_data)
                    elif isinstance(eval_result, dict) and eval_result.get("error"):  # type: ignore
                        print(f"Error during image fetch in page context: {eval_result['error']}")
                        return None
                    else:
                        print(f"Unexpected result from Runtime.evaluate: {eval_result}")
                        return None

                elif "error" in data:
                    print(
                        f"Error executing Runtime.evaluate: {data['error']['message']} (Code: {data['error'].get('code')})")
                    print(f"Details: {data['error'].get('data')}")
                    return None
                elif "result" in data and "exceptionDetails" in data["result"]:
                    print("Exception during Runtime.evaluate:")
                    print(json.dumps(data["result"]["exceptionDetails"], indent=2))
                    return None
                break


async def fetch_file(base_dir: str, ws_url: str, file_type: str, file: str):
    """Fetch a file from the epub using the Thorium Reader's remote debugging interface.

    Args:
        base_dir: _base directory of the epub files_
        ws_url: _webSocketDebuggerUrl of the Thorium Reader_
        file_type: _mime type of the file_
        file: _name of the file to fetch_

    Returns:
        A tuple containing the filename and the content of the file, or None if the file is not needed.
        If the file is nav.xhtml, it returns None, None.
    """
    if file == "nav.xhtml":
        return None, None
    file_path = os.path.normpath(os.path.join(base_dir, file))
    url = file_path
    if file_type.startswith("application/xhtml+xml") or file_type.startswith("text/css"):
        content = await get_content_via_evaluate(ws_url, url)
        return file_path.split("\\")[-1], content
    elif file_type.startswith("image/"):
        content = await get_image_via_evaluate(ws_url, url)
        return file_path.split("\\")[-1], content
    return None, None
