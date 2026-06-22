from app.desktop.paths import init_desktop_paths


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    paths = init_desktop_paths()
    for name, path in paths.items():
        print(f"{name}={path}")
