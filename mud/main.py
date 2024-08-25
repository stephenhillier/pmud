import logging
import uvicorn


def main():
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("mud.server:app", port=8000, reload=True)


if __name__ == "__main__":
    main()
