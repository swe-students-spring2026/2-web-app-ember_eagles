import os
import datetime
from flask import Flask, render_template, request, redirect, abort, url_for, make_response
import pymongo
from bson.objectid import ObjectId
from dotenv import load_dotenv, dotenv_values

load_dotenv()  # load environment variables from .env file

def create_app():
    """
    Create and configure the Flask application.
    returns: app: the Flask application object
    """

    app = Flask(__name__)
    # load flask config from env variables
    config = dotenv_values()
    app.config.from_mapping(config)

    connection = pymongo.MongoClient(os.getenv("MONGO_URI"))
    db = connection[os.getenv("MONGO_DBNAME")]

    try:
        connection.admin.command("ping")
        print(" *", "Connected to MongoDB!")
    except Exception as e:
        print(" * MongoDB connection error:", e)

    
    return app

app = create_app()

if __name__ == "__main__":
    FLASK_PORT = os.getenv("FLASK_PORT", "5000")
    FLASK_ENV = os.getenv("FLASK_ENV")
    print(f"FLASK_ENV: {FLASK_ENV}, FLASK_PORT: {FLASK_PORT}")

    app.run(port=FLASK_PORT)

