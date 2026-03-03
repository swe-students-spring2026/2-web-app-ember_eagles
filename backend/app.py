import os
import datetime
from flask import Flask, render_template, request, session, redirect, abort, url_for, make_response, flash
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
    users = db["users"]

    try:
        connection.admin.command("ping")
        print(" *", "Connected to MongoDB!")
    except Exception as e:
        print(" * MongoDB connection error:", e)

    @app.route("/")
    def home():
        return render_template("home.html", username=session.get("username"))
    
    @app.route("/login", methods = ["GET"])
    def login():
        return render_template("login.html")
    
    @app.route("/login", methods = ["POST"])
    def login_post():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter username and password.")
            return redirect(url_for("login"))

        user = users.find_one({"username": username, "password": password})
        if not user:
            flash("Invalid username or password.")
            return redirect(url_for("login"))
        session["user_id"] = str(user["_id"])
        session["username"] = user["username"]
        return redirect(url_for("home"))
    
    @app.route("/logout", methods = ["GET"])
    def logout():
        session.clear()
        return redirect(url_for("login"))
    
    @app.route("/signup", methods = ["GET"])
    def signup():
        return render_template("signup.html")
    
    @app.route("/signup", methods = ["POST"])
    def signup_post():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter username and password.")
            return redirect(url_for("signup"))

        user = users.find_one({"username": username})
        if user:
            flash("Username already exists.")
            return redirect(url_for("signup"))

        users.insert_one({
            "username": username,
            "password": password
        })
        flash("Account created successfully.")
        return redirect(url_for("login"))

    return app

app = create_app()

if __name__ == "__main__":
    FLASK_PORT = os.getenv("FLASK_PORT", "5000")
    FLASK_ENV = os.getenv("FLASK_ENV")
    print(f"FLASK_ENV: {FLASK_ENV}, FLASK_PORT: {FLASK_PORT}")

    app.run(port=FLASK_PORT)

