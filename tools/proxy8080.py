import asyncio, socket, sys

async def handle(r, w):
    try:
        tr, tw = await asyncio.open_connection("127.0.0.1", 8081)
        async def fwd(a, b):
            try:
                while True:
                    d = await a.read(65536)
                    if not d: break
                    b.write(d); await b.drain()
            finally:
                b.close()
        await asyncio.gather(fwd(r, tw), fwd(tr, w), return_exceptions=True)
    except Exception as e:
        pass
    finally:
        w.close()

async def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", 8080))
    except OSError as e:
        print(f"BIND FAILED: {e}", flush=True)
        sys.exit(1)
    s.listen(200)
    srv = await asyncio.start_server(handle, sock=s)
    print("proxy 8080->8081 ready", flush=True)
    async with srv:
        await srv.serve_forever()

asyncio.run(main())
