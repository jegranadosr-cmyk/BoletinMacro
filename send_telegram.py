import os
import sys
import json
import urllib.request


def send_media_group(token, chat_id, image_paths, caption=None):
    boundary = "----UnvestingBoundary7a8b9c"
    url = f"https://api.telegram.org/bot{token}/sendMediaGroup"

    media = []
    for i, path in enumerate(image_paths):
        attach_name = f"photo{i}"
        entry = {"type": "photo", "media": f"attach://{attach_name}"}
        if i == 0 and caption:
            entry["caption"] = caption
        media.append(entry)

    body = bytearray()

    def add_field(name, value):
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(f"{value}\r\n".encode())

    add_field("chat_id", chat_id)
    add_field("media", json.dumps(media))

    for i, path in enumerate(image_paths):
        attach_name = f"photo{i}"
        filename = os.path.basename(path)
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{attach_name}"; filename="{filename}"\r\n'.encode()
        )
        body.extend(b"Content-Type: image/png\r\n\r\n")
        with open(path, "rb") as f:
            body.extend(f.read())
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(url, data=bytes(body), method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
    return result


if __name__ == "__main__":
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars", file=sys.stderr)
        sys.exit(1)
    out = send_media_group(token, chat_id, ["render_out/page1.png", "render_out/page2.png"])
    print(json.dumps(out, indent=2))
