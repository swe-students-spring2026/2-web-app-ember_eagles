import os
import datetime
# from tokenize import group (this shouldnt be here as it has no relation to this app.)
from flask import Flask, render_template, request, session, redirect, abort, url_for, make_response, flash
import pymongo
from bson.objectid import ObjectId
from dotenv import load_dotenv, dotenv_values
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()  # load environment variables from .env file

def create_app():
    """
    Create and configure the Flask application.
    returns: app: the Flask application object
    """

    app = Flask(__name__,
        template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend"),
        static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend"),
        static_url_path="")
    # load flask config from env variables
    config = dotenv_values()
    app.config.from_mapping(config)

    connection = pymongo.MongoClient(os.getenv("MONGO_URI"))
    db = connection[os.getenv("MONGO_DBNAME")]
    users = db["users"]
    groups = db["groups"]
    reviews = db["reviews"]
    restaurants = db["restaurants"]

    try:
        connection.admin.command("ping")
        print(" *", "Connected to MongoDB!")
    except Exception as e:
        print(" * MongoDB connection error:", e)


    @app.before_request
    def require_login():
        allowed_routes = ["login", "login_post", "signup", "signup_post", "static"]

        if request.endpoint in allowed_routes:
            return

        if "user_id" not in session:
            return redirect(url_for("login"))

    @app.route("/")
    def restaurant_list():
        user_id = session.get("user_id")
        if not user_id:
            return redirect(url_for("login"))

        user_oid = ObjectId(user_id)

        my_groups = list(groups.find(
            {"members": user_oid},
            {"name": 1}
        ))
        my_group_ids = [g["_id"] for g in my_groups]

        if not my_group_ids:
            return render_template(
                "restaurant-list.html",
                username=session.get("username"),
                groups=[],
                selected_group_id="",
                restaurants=[]
            )

        selected_group_id = request.args.get("group_id", "").strip()

        if selected_group_id:
            try:
                gid = ObjectId(selected_group_id)
            except Exception:
                flash("Invalid group.")
                return redirect(url_for("restaurant_list"))

            if gid not in my_group_ids:
                flash("You are not a member of this group.")
                return redirect(url_for("restaurant_list"))

            group_ids_to_use = [gid]
        else:
            group_ids_to_use = my_group_ids
            
        restaurant_ids = reviews.distinct(
            "restaurant_id",
            {"group_id": {"$in": group_ids_to_use}}
        )
        
        if not restaurant_ids:
            return render_template(
                "restaurant-list.html",
                username=session.get("username"),
                groups=my_groups,
                selected_group_id=selected_group_id,
                restaurants=[]
            )

        review_docs = list(reviews.find(
            {"group_id": {"$in": group_ids_to_use}, "restaurant_id": {"$in": restaurant_ids}},
            {"restaurant_id": 1, "rating": 1}
        ))
        rating_sum = {}
        rating_cnt = {}

        for r in review_docs:
            rid = r["restaurant_id"]
            rating = r.get("rating")
            if rating is None:
                continue
            rating_sum[rid] = rating_sum.get(rid, 0) + float(rating)
            rating_cnt[rid] = rating_cnt.get(rid, 0) + 1

        restaurants_list = list(restaurants.find(
            {"_id": {"$in": restaurant_ids}},
            {"name": 1, "address": 1}
        ))

        for r in restaurants_list:
            rid = r["_id"]
            r["avg_rating"] = rating_sum.get(rid, 0) / rating_cnt.get(rid, 1) if rating_cnt.get(rid, 0) > 0 else 0

        return render_template(
        "restaurant-list.html",
        username=session.get("username"),
        groups=my_groups,
        selected_group_id=selected_group_id,
        restaurants=restaurants_list
    )

# Authentication routes
    @app.route("/login", methods = ["GET"])
    def login():
        return render_template("signin.html")
    
    @app.route("/login", methods = ["POST"])
    def login_post():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter username and password.")
            return redirect(url_for("login"))

        user = users.find_one({"username": username}) # you can no longer query mongoDB by password since its hashed, so username only and then use check_password_hash to verify.
        if not user or not check_password_hash(user['password'], password):
            flash("Invalid username or password.")
            return redirect(url_for("login"))
        session["user_id"] = str(user["_id"])
        session["username"] = user["username"]
        return redirect(url_for("restaurant_list"))
    
    @app.route("/logout", methods = ["GET"])
    def logout():
        session.clear()
        return redirect(url_for("login"))
    
    @app.route('/signup', methods=['GET']) # this serves as the actual signup HTML form to the user
    def signup():
        return render_template('signin.html', initial_form='signup')

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
            "password": generate_password_hash(password)
        })
        flash("Account created successfully.")
        return redirect(url_for("login"))
    
# Restaurant routes
    @app.route("/restaurant/<restaurant_id>", methods=["GET"])
    def restaurant_details(restaurant_id):
        try:
            rid = ObjectId(restaurant_id)
        except Exception:
            flash("Invalid restaurant id.")
            return redirect(url_for("restaurant_list"))

        restaurant = restaurants.find_one({"_id": rid})
        if not restaurant:
            flash("Restaurant not found.")
            return redirect(url_for("restaurant_list"))

        selected_group_id = request.args.get("group_id", "").strip()
        selected_sort = request.args.get("sort", "").strip()

        user_oid = ObjectId(session["user_id"])
        filter_groups = list(groups.find({"members": user_oid}, {"name": 1}))

        review_filter = {"restaurant_id": rid}

        if selected_group_id:
            try:
                gid = ObjectId(selected_group_id)
            except Exception:
                flash("Invalid group filter.")
                return redirect(url_for("restaurant_details", restaurant_id=restaurant_id))

            my_group_ids = [g["_id"] for g in filter_groups]
            if gid not in my_group_ids:
                flash("You are not a member of this group.")
                return redirect(url_for("restaurant_details", restaurant_id=restaurant_id))

            review_filter["group_id"] = gid

        cursor = reviews.find(review_filter)

        if selected_sort == "rating_high":
            cursor = cursor.sort("rating", -1)
        elif selected_sort == "rating_low":
            cursor = cursor.sort("rating", 1)
        else:
            cursor = cursor.sort("created_at", -1)

        restaurant_reviews = list(cursor)

        # average rating
        ratings = [r["rating"] for r in restaurant_reviews if r.get("rating") is not None]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

        # users
        user_ids = {r["author_id"] for r in restaurant_reviews}
        user_map = {
            u["_id"]: u["username"]
            for u in users.find({"_id": {"$in": list(user_ids)}})
        }

        # groups
        group_ids = {r["group_id"] for r in restaurant_reviews}
        group_map = {
            g["_id"]: g["name"]
            for g in groups.find({"_id": {"$in": list(group_ids)}})
        }

        for r in restaurant_reviews:
            r["author_name"] = user_map.get(r["author_id"], "Unknown")
            r["group_name"] = group_map.get(r["group_id"], "Unknown")

        return render_template(
        "restaurant-detail.html",
        restaurant=restaurant,
        reviews=restaurant_reviews,
        avg_rating=avg_rating,
        review_count=len(restaurant_reviews),
        filter_groups=filter_groups,
        selected_group_id=selected_group_id,
        selected_sort=selected_sort
    )
    
# Profile routes
    @app.route("/profile", methods = ["GET"])
    def profile():
        user_oid = ObjectId(session["user_id"])
        user = users.find_one({"_id": user_oid}, {"username": 1, "password": 1})
        return render_template("profile.html", user=user)
    
    @app.route("/profile", methods = ["POST"])
    def profile_edit():
        user_oid = ObjectId(session["user_id"])
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not username or not password:
            flash("Please enter username and password.")
            return redirect(url_for("profile"))

        existing = users.find_one({"username": username, "_id": {"$ne": user_oid}})
        if existing:
            flash("Username already taken.")
            return redirect(url_for("profile"))
        
        users.update_one({"_id": user_oid}, {"$set": {"username": username, "password": generate_password_hash(password)}})
        session["username"] = username
        flash("Profile updated successfully.")
        return redirect(url_for("profile"))
    
# Group routes
    @app.route("/groups", methods = ["GET"])
    def groups_page():
        user_id = ObjectId(session["user_id"])
        my_groups = list(groups.find({"members": user_id},{"name": 1, "description": 1, "owner_id": 1, "members": 1})) # we need to include the members field in the mongodb res.
        for g in my_groups:
            g["member_count"] = len(g.get("members", []))
            g["is_owner"] = (g.get("owner_id") == user_id)
        return render_template("groups.html", groups=my_groups)
    
    @app.route("/groups/<group_id>", methods = ["GET"])
    def group_details(group_id):

        user_oid = ObjectId(session["user_id"])
        gid = ObjectId(group_id)

        group = groups.find_one({"_id": gid})
        if not group:
            flash("Group not found.")
            return redirect(url_for("groups_page"))

        # --- NEW: convert member ObjectIds to usernames ---
        member_ids = group.get("members", [])
        member_docs = list(users.find({"_id": {"$in": member_ids}}, {"username": 1}))
        group["members"] = [u["username"] for u in member_docs]

        # Reviews mapping (unchanged)
        review_docs = list(reviews.find({"group_id": gid}))
        author_ids = {r["author_id"] for r in review_docs if "author_id" in r}
        rest_ids = {r["restaurant_id"] for r in review_docs if "restaurant_id" in r}

        user_map = {u["_id"]: u["username"]
                for u in users.find({"_id": {"$in": list(author_ids)}}, {"username": 1})} if author_ids else {}

        rest_map = {x["_id"]: x["name"]
                for x in restaurants.find({"_id": {"$in": list(rest_ids)}}, {"name": 1})} if rest_ids else {}

        for r in review_docs:
            r["author_name"] = user_map.get(r.get("author_id"), "Unknown")
            r["restaurant_name"] = rest_map.get(r.get("restaurant_id"), "Unknown")

        return render_template("group-detail.html", group = group, reviews=review_docs)
    
    @app.route("/groups/<group_id>/leave", methods=["POST"])
    def leave_group(group_id):

        user_oid = ObjectId(session["user_id"])
        gid = ObjectId(group_id)

        group = groups.find_one({"_id": gid})
        if not group:
            flash("Group not found.")
            return redirect(url_for("groups_page"))

        if group.get("owner_id") == user_oid:
            flash("Group owner cannot leave the group.")
            return redirect(url_for("group_details", group_id=group_id))

        groups.update_one(
            {"_id": gid},
            {"$pull": {"members": user_oid}}
        )

        flash("You have left the group.")
        return redirect(url_for("groups_page"))

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
        return redirect(url_for("groups_page"))
    
    @app.route("/join_group", methods = ["GET"])
    def join_group_form():
        
        return render_template("join-group.html")
    
    @app.route("/join_group", methods=["POST"])
    def join_group():

        user_oid = ObjectId(session["user_id"])
        group_id = request.form.get("group_id", "").strip()

        try:
            gid = ObjectId(group_id)
        except Exception:
            flash("Invalid group id.")
            return redirect(url_for("join_group_form"))

        group = groups.find_one({"_id": gid})
        if not group:
            flash("Group not found.")
            return redirect(url_for("join_group_form"))

        result = groups.update_one(
        {"_id": gid},
        {"$addToSet": {"members": user_oid}}
    )

        if result.modified_count == 0:
            flash("You are already a member of this group.")
        else:
            flash("Joined group successfully.")

        return redirect(url_for("groups_page"))
    
    # Restaurant review routes
    @app.route("/review", methods=["GET"])
    def my_reviews():
        user_id = ObjectId(session["user_id"])
        my_reviews = list(reviews.find({"author_id": user_id}))
        rest_ids = [r["restaurant_id"] for r in my_reviews if r.get("restaurant_id")]
        rest_map = {x["_id"]: x["name"] for x in restaurants.find({"_id": {"$in": rest_ids}}, {"name": 1})} if rest_ids else {}
        for r in my_reviews:
            r["restaurant_name"] = rest_map.get(r.get("restaurant_id"), "Unknown")
        return render_template("my-reviews.html", reviews=my_reviews)
    
    @app.route("/review/new", methods=["GET"])
    def review():
        user_oid = ObjectId(session["user_id"])

        my_groups = list(groups.find(
        {"members": user_oid},
        {"name": 1}
        ))

        return render_template("review.html", groups=my_groups, form_action=url_for("review_post"))
    
    @app.route("/review/new", methods=["POST"])
    def review_post():
        restaurant_name = request.form.get("restaurant_name", "").strip()
        address = request.form.get("address", "").strip()
        review_text = request.form.get("review_text", "").strip()
        rating = int(request.form.get("rating", "0"))
        group = request.form.get("group_id", "").strip()
        gid = ObjectId(group) if group else None


        if not review_text or not restaurant_name or not address:
            flash("Please enter a restaurant name, address, and review text.")
            return redirect(url_for("review"))
        
        rest = restaurants.find_one({"name": restaurant_name, "address": address})
        if not rest:
            rest_id = restaurants.insert_one({
            "name": restaurant_name,
            "address": address,
            }).inserted_id
        else:
            rest_id = rest["_id"]

        reviews.insert_one({
            "text": review_text,
            "restaurant_id": rest_id,
            "address": address,
            "rating": rating,
            "author_id": ObjectId(session["user_id"]),
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow(),
            "group_id": gid
        })

        flash("Review submitted successfully.")
        return redirect(url_for("my_reviews"))
    
    @app.route("/review/<review_id>/delete", methods=["POST"])
    def delete_review(review_id):
        try:
            rid = ObjectId(review_id)
        except Exception:
            flash("Invalid review id.")
            return redirect(url_for("my_reviews"))

        result = reviews.delete_one({"_id": rid, "author_id": ObjectId(session["user_id"])})
        flash("Review deleted successfully.")
        return redirect(url_for("my_reviews"))

    @app.route("/review/<review_id>", methods=["GET"])
    def view_review(review_id):
        try:
            rid = ObjectId(review_id)
        except Exception:
            flash("Invalid review id.")
            return redirect(url_for("my_reviews"))

        review = reviews.find_one({"_id": rid})
        if not review:
            flash("Review not found.")
            return redirect(url_for("my_reviews"))
        rest = restaurants.find_one({"_id": review["restaurant_id"]}, {"name": 1}) if review.get("restaurant_id") else None
        review["restaurant_name"] = rest["name"] if rest else "Unknown"
        return render_template("view-review.html", review=review)
    
    @app.route("/review/<review_id>/edit", methods=["GET"])
    def edit_review_form(review_id):
        try:
            rid = ObjectId(review_id)
        except Exception:
            flash("Invalid review id.")
            return redirect(url_for("my_reviews"))

        review = reviews.find_one({"_id": rid})
        if not review:
            flash("Review not found.")
            return redirect(url_for("my_reviews"))
        if review.get("author_id") != ObjectId(session["user_id"]):
            flash("You can only edit your own reviews.")
            return redirect(url_for("my_reviews"))
        rest = restaurants.find_one({"_id": review["restaurant_id"]}, {"name": 1,"address": 1}) if review.get("restaurant_id") else None
        review["restaurant_name"] = rest["name"] if rest else "Unknown"
        my_groups = list(groups.find({"members": ObjectId(session["user_id"])}, {"name": 1}))
        return render_template("review.html", review=review, groups=my_groups, form_action=url_for("edit_review", review_id=review_id),
        mode="edit")

    @app.route("/review/<review_id>/edit", methods=["POST"])
    def edit_review(review_id):
        try:
            rid = ObjectId(review_id)
        except Exception:
            flash("Invalid review id.")
            return redirect(url_for("my_reviews"))

        existing = reviews.find_one({"_id": rid, "author_id": ObjectId(session["user_id"])})
        if not existing:
            flash("Review not found or you can only edit your own reviews.")
            return redirect(url_for("my_reviews"))
        
        restaurant_name = request.form.get("restaurant_name", "").strip()
        address = request.form.get("address", "").strip()
        review_text = request.form.get("review_text", "").strip()
        group = request.form.get("group_id", "").strip()
        rating_raw = request.form.get("rating", "").strip()
        try:
            rating = int(rating_raw) if rating_raw != "" else None
        except ValueError:
            rating = None
        gid = ObjectId(group) if group else None

        if not review_text or not restaurant_name or not address:
            flash("Please enter a restaurant name, an address, and your review text.")
            return redirect(url_for("edit_review_form", review_id=review_id))

        rest = restaurants.find_one({"name": restaurant_name, "address": address})
        if not rest:
            rest_id = restaurants.insert_one({
            "name": restaurant_name,
            "address": address,
            }).inserted_id
        else:
            rest_id = rest["_id"]

        reviews.update_one(
            {"_id": rid},
            {"$set": {
                "text": review_text,
                "address": address,
                "rating": rating,
                "restaurant_id": rest_id,
                "updated_at": datetime.datetime.utcnow(),
                "group_id": gid
            }})
        
        flash("Review updated successfully.")

        return redirect(url_for("my_reviews"))

    return app

app = create_app()

if __name__ == "__main__":
    FLASK_PORT = os.getenv("FLASK_PORT", "5000")
    FLASK_ENV = os.getenv("FLASK_ENV")
    print(f"FLASK_ENV: {FLASK_ENV}, FLASK_PORT: {FLASK_PORT}")

    app.run(port=FLASK_PORT)

