import asyncio
import base64
import json
import re

import websockets


async def get_content_via_evaluate(devtools_ws_url, resource_url):
    async with websockets.connect(devtools_ws_url) as websocket:
        # Enable Runtime domain
        await websocket.send(json.dumps({
            "id": 1,  # Unique message ID
            "method": "Runtime.enable"
        }))
        response = await websocket.recv()  # Wait for acknowledgment
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

                    if isinstance(eval_result, dict) and eval_result.get("success"):
                        content = eval_result["content"]
                        # print("Content fetched successfully via Runtime.evaluate!")
                        # with open("downloaded_file_runtime.html", "w", encoding="utf-8") as f:
                        #     f.write(content)
                        # print("Saved content to downloaded_file_runtime.html")
                        return content
                    elif isinstance(eval_result, dict) and eval_result.get("error"):
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


async def get_image_via_evaluate(devtools_ws_url, image_url):
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

                    if isinstance(eval_result, dict) and eval_result.get("success"):
                        base64_data = eval_result["base64"]
                        # print("Image fetched successfully via Runtime.evaluate!")
                        # To save as file:
                        # with open("downloaded_image.png", "wb") as f:
                        #     f.write(base64.b64decode(base64_data))
                        return base64.b64decode(base64_data)
                    elif isinstance(eval_result, dict) and eval_result.get("error"):
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

if __name__ == "__main__":
    # Replace with your actual DevTools WebSocket URL and resource URL
    # 1. Find your page's websocket URL from http://localhost:9222/json
    # It will look like "ws://localhost:9222/devtools/page/XXXXXXXXX"
    DEVTOOLS_WS_URL = "ws://localhost:9223/devtools/page/5A4CF9F84792B821B2FD8B00EE8AC4EA"  # Replace!
    RESOURCE_URL = "httpsr2://id_l2hvb_w_uvc2_vid_ggv_lm_nvbm_zp_zy9_f_r_f_j_m_y_w_iu_v_ghvcml1b_v_jl_y_w_rlci9wd_w_jsa_w_nhd_glvbn_mv_mjkw_m2_e1_yz_mt_nm_iw_yi00_nm_u0_l_tk2_m_dgt_n_dg5_mj_zm_mm_fj_m_g_fj_l2_jvb2su_z_x_b1_yg--/xthoriumhttps/ip0.0.0.0/p/EPUB/dk-nota-666120-012-part.xhtml"

    # Before running, ensure your Electron app is running with --remote-debugging-port=9222
    # And update DEVTOOLS_WS_URL by visiting http://localhost:9222/json in your browser
    # to get the list of targets and pick the correct webSocketDebuggerUrl.
    # For example, if http://localhost:9222/json shows:
    # {
    # ...
    # "id": "ABC123DEF456",
    # "type": "page",
    # "url": "...",
    # "webSocketDebuggerUrl": "ws://localhost:9222/devtools/page/ABC123DEF456"
    # ...
    # }
    # Then DEVTOOLS_WS_URL = "ws://localhost:9222/devtools/page/ABC123DEF456"

    # To run this:
    asyncio.run(get_content_via_evaluate(DEVTOOLS_WS_URL, RESOURCE_URL))
    # print("CDP script is conceptual. Please ensure you have the correct DEVTOOLS_WS_URL.")
    # print("You can get it from http://localhost:9222/json (look for webSocketDebuggerUrl).")
    # print("And replace 'YOUR_PAGE_ID_HERE' in the script.")
