import os
import datetime
from click import group
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
    groups = db["groups"]
    reviews = db["reviews"]

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

    @app.route("/profile", methods = ["GET"])
    def profile():
        return render_template("profile.html", username=session["username"])
    
    @app.route("/profile/edit", methods = ["POST"])
    def profile_edit():
        new_username = request.form.get("username", "").strip()
        new_password = request.form.get("password", "")

        if not new_username or not new_password:
            flash("Please enter username and password.")
            return redirect(url_for("profile"))

        user_id = session["user_id"]
        users.update_one({"_id": ObjectId(user_id)}, {"$set": {"username": new_username, "password": new_password}})
        session["username"] = new_username
        flash("Profile updated successfully.")
        return redirect(url_for("profile"))
    
    @app.route("/groups", methods = ["GET"])
    def groups():
        user_id = ObjectId(session["user_id"])
        my_groups = list(groups.find({"members": user_id}))
        return render_template("groups.html", groups=my_groups)
    
    @app.route("/groups/<group_id>")
    def group_details(group_id):
        return render_template("group-details.html", group_id=group_id)
    
    @app.route("/groups/<group_id>/leave", methods=["POST"])
    def leave_group(group_id):

        user_oid = ObjectId(session["user_id"])
        gid = ObjectId(group_id)

        group = groups.find_one({"_id": gid})
        if not group:
            flash("Group not found.")
            return redirect(url_for("groups"))

        if group.get("owner_id") == user_oid:
            flash("Group owner cannot leave the group.")
            return redirect(url_for("group_details", group_id=group_id))

        groups.update_one(
            {"_id": gid},
            {"$pull": {"members": user_oid}}
        )

        flash("You have left the group.")
        return redirect(url_for("groups"))

    @app.route("/create_group", methods = ["GET"])
    def create_group():
        return render_template("create-group.html")
    
    @app.route("/create_group", methods = ["POST"])
    def create_group_post():
        group_name = request.form.get("group_name", "").strip()
        group_description = request.form.get("group_description", "").strip()

        if not group_name or not group_description:
            flash("Please enter group name and description.")
            return redirect(url_for("create_group"))
        
        owner_id = ObjectId(session["user_id"])

        groups.insert_one({
            "name": group_name,
            "description": group_description,
            "owner_id": owner_id,
            "members": [owner_id]
        })
        flash("Group created successfully.")
        return redirect(url_for("groups"))
    
    @app.route("/join_group/<group_id>", methods=["POST"])
    def join_group(group_id):

        user_oid = ObjectId(session["user_id"])

        try:
            gid = ObjectId(group_id)
        except Exception:
            flash("Invalid group id.")
            return redirect(url_for("groups"))

        group = groups.find_one({"_id": gid})
        if not group:
            flash("Group not found.")
            return redirect(url_for("groups"))

        result = groups.update_one(
        {"_id": gid},
        {"$addToSet": {"members": user_oid}}
    )

        if result.modified_count == 0:
            flash("You are already a member of this group.")
        else:
            flash("Joined group successfully.")

        return redirect(url_for("group_details", group_id=group_id))
    
    @app.route("/review", methods=["POST"])
    def review():
        restaurant_name = request.form.get("restaurant_name", "").strip()
        address = request.form.get("address", "").strip()
        review_text = request.form.get("review_text", "").strip()
        rating = request.form.get("rating", "").strip()

        if not review_text or not restaurant_name or not address:
            flash("Please enter a restaurant name, address, and review text.")
            return redirect(url_for("groups"))

        reviews.insert_one({
            "text": review_text,
            "restaurant_name": restaurant_name,
            "address": address,
            "rating": rating,
            "user_id": ObjectId(session["user_id"])
        })

        flash("Review submitted successfully.")
        return redirect(url_for("restaurant-list"))
    
    @app.route("/review/<review_id>/delete", methods=["POST"])
    def delete_review(review_id):
        try:
            rid = ObjectId(review_id)
        except Exception:
            flash("Invalid review id.")
            return redirect(url_for("restaurant-list"))

        result = reviews.delete_one({"_id": rid, "user_id": ObjectId(session["user_id"])})
        flash("Review deleted successfully.")

    @app.route("/review/<review_id>", methods=["GET"])
    def view_review(review_id):
        try:
            rid = ObjectId(review_id)
        except Exception:
            flash("Invalid review id.")
            return redirect(url_for("restaurant-list"))

        review = reviews.find_one({"_id": rid})
        if not review:
            flash("Review not found.")
            return redirect(url_for("restaurant-list"))

        return render_template("view-review.html", review=review)
    
    @app.route("/review/<review_id>/edit", methods=["GET"])
    def edit_review_form(review_id):
        try:
            rid = ObjectId(review_id)
        except Exception:
            flash("Invalid review id.")
            return redirect(url_for("restaurant-list"))

        review = reviews.find_one({"_id": rid})
        if not review:
            flash("Review not found.")
            return redirect(url_for("restaurant-list"))

        return render_template("edit-review.html", review=review)

    @app.route("/review/<review_id>/edit", methods=["POST"])
    def edit_review(review_id):
        try:
            rid = ObjectId(review_id)
        except Exception:
            flash("Invalid review id.")
            return redirect(url_for("restaurant-list"))
        
        address = request.form.get("address", "").strip()
        rating = request.form.get("rating", "").strip()
        restaurant_name = request.form.get("restaurant_name", "").strip()
        review_text = request.form.get("review_text", "").strip()
        if not review_text:
            flash("Please enter a review text.")
            return redirect(url_for("restaurant-list"))

        result = reviews.update_one(
            {"_id": rid},
            {"$set": {
                "text": review_text,
                "address": address,
                "rating": rating,
                "restaurant_name": restaurant_name
            }})
        

        flash("Review updated successfully.")

        return redirect(url_for("restaurant-list"))

    return app

app = create_app()

if __name__ == "__main__":
    FLASK_PORT = os.getenv("FLASK_PORT", "5000")
    FLASK_ENV = os.getenv("FLASK_ENV")
    print(f"FLASK_ENV: {FLASK_ENV}, FLASK_PORT: {FLASK_PORT}")

    app.run(port=FLASK_PORT)

