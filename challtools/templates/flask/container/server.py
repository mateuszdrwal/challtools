from flask import Flask
from flask.typing import ResponseReturnValue

app = Flask(__name__)


@app.route("/")
def index() -> ResponseReturnValue:
    return "Template challenge running!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
