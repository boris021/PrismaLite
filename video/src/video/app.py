from fastapi import FastAPI


app = FastAPI(title="PrismaLite Video Stub", version="0.1.0")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/hls/live/{camera_id}/index.m3u8", tags=["hls"])
async def live_playlist(camera_id: str) -> str:
    return (
        "#EXTM3U\n"
        "#EXT-X-VERSION:3\n"
        "#EXT-X-TARGETDURATION:10\n"
        "#EXT-X-MEDIA-SEQUENCE:0\n"
        "#EXTINF:10,\n"
        f"/hls/live/{camera_id}/segment0.ts\n"
    )

