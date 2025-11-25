import socket
from datetime import datetime

HOST = "0.0.0.0"
PORT = 9001
LOG_FILE = "setretail_raw.log"

def main():
    print(f"Listening on {HOST}:{PORT} ...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen(5)

        while True:
            conn, addr = srv.accept()
            print(f"[{datetime.now()}] Connection from {addr}")
            with conn:
                data_chunks = []
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data_chunks.append(chunk)
                if not data_chunks:
                    continue

                data = b"".join(data_chunks)
                try:
                    text = data.decode("utf-8", errors="replace")
                except Exception:
                    text = repr(data)

                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(f"\n----- {datetime.now()} from {addr} -----\n")
                    f.write(text)
                    f.write("\n")

                print(f"[{datetime.now()}] Saved {len(data)} bytes to {LOG_FILE}")

if __name__ == "__main__":
    main()
