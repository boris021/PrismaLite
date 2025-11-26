from fastapi.staticfiles import StaticFiles

app.mount("/ui/static", StaticFiles(directory="app/ui"), name="ui")
