# Adapted from https://github.com/dannnylin/finstagram-template/blob/master/app.py

from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

app = Flask(__name__)
app.secret_key = "super secret key"
IMAGES_DIR = os.path.join(os.getcwd(), "images")

connection = pymysql.connect(host="localhost",
                             user="root",
                             password="password",
                             db="Finstagram",
                             charset="utf8mb4",
                             port=3306,
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

SALT = 'cs3083'

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/home")
@login_required
def home():
    username = session["username"]
    # fix this
    query = """SELECT photoID, photoPoster, postingDate
               FROM Photo
               WHERE photoPoster = %s"""
    with connection.cursor() as cursor:
        cursor.execute(query, username)
    data = cursor.fetchall()
    return render_template("home.html", username=session["username"], photos = data)

#Feature 1
@app.route("/viewVisiblePhotos")
@login_required
def seeVisiblePhotos():
    username = session["username"]
    query = """SELECT photoID, photoPoster, postingDate, filePath
               FROM Photo
               WHERE photoID in (
               SELECT photoID
               FROM Photo
               WHERE photoID IN 
               (SELECT photoID
                FROM SharedWith NATURAL JOIN BelongTo
                WHERE member_username = %s) UNION
               (SELECT photoID
               FROM Photo Join Follow ON Photo.photoPoster = Follow.username_followed
               WHERE username_follower = %s AND followstatus = 1 AND allFollowers=1))
               ORDER BY postingDate DESC"""
    with connection.cursor() as cursor:
        cursor.execute(query, (username, username))
    data = cursor.fetchall()
    return render_template("visible_list.html", username=session["username"], photos = data)

# Part of Feature 3
@app.route("/upload", methods=["GET"])
@login_required
def upload():
    return render_template("upload.html")
#

# Redirect here to view photo details for Feature 2
# Have link to click to view photo
@app.route("/images/<photo_ID>", methods=["GET"])
@login_required
def images(photo_ID):
    # query to get poster details
    query = """SELECT photoID, firstName, lastName, postingDate, filepath
               FROM Photo JOIN Person ON (photoPoster = username)
               WHERE photoID = %s"""
    with connection.cursor() as cursor:
        cursor.execute(query, photo_ID)
    poster_data = cursor.fetchone()
    # query to get like details
    query = """SELECT DISTINCT COUNT(username) AS total
               FROM Likes
               WHERE photoID = %s"""
    with connection.cursor() as cursor:
        cursor.execute(query, photo_ID)
    likes_data = cursor.fetchone()

    return render_template("images.html", poster_details=poster_data, likes_details=likes_data)

@app.route("/image/<image_name>", methods=["GET"])
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"] + SALT
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()

        with connection.cursor() as cursor:
            query = "SELECT * FROM Person WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data:
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error)

    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error)

@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"] + SALT
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO Person (username, password, firstName, lastName) VALUES (%s, %s, %s, %s)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName))
        except pymysql.err.IntegrityError:
            error = "%s is already taken." % (username)
            return render_template('register.html', error=error)    

        return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")

# Feature 3
@app.route("/uploadStart")
@login_required
def upload_start():
    return render_template("all_followers_redirect.html")

@app.route("/allFollowers")
@login_required
def upload_to_all_followers():
    return render_template("all_followers.html")

#select groups only
@app.route("/groupFollowers")
@login_required
def upload_to_group_followers():
    user = session['username']
    cursor = connection.cursor();
    query = 'SELECT owner_username, groupName FROM BelongTo WHERE %s = member_username'
    cursor.execute(query, user)
    data = cursor.fetchall()
    cursor.close()
    return render_template('group_followers.html', groups=data)


@app.route("/uploadImageAll", methods=["POST"])
@login_required
def upload_image_all():
    if request.files:
        user = session['username']
        image_file = request.files.get("imageToUpload", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)
        query = "INSERT INTO Photo (postingdate, filePath, allFollowers, photoPoster) VALUES (%s, %s, 1, %s)"
        with connection.cursor() as cursor:
            cursor.execute(query, (time.strftime('%Y-%m-%d %H:%M:%S'), image_name, user))
        message = "Image has been successfully uploaded."
        return render_template("upload.html", message=message)
    else:
        message = "Failed to upload image."
        return render_template("upload.html", message=message)

@app.route("/uploadImageGroup", methods=["POST"])
@login_required
def upload_image_group():
    if request.files:
        user = session['username']
        image_file = request.files.get("imageToUpload", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)
        query = "INSERT INTO Photo (postingdate, filePath, allFollowers, photoPoster) VALUES (%s, %s, 0, %s)"
        with connection.cursor() as cursor:
                cursor.execute(query, (time.strftime('%Y-%m-%d %H:%M:%S'), image_name, user))
        # get latest photo by user
        query = "SELECT MAX(photoID) as max FROM Photo WHERE photoPoster = %s"
        with connection.cursor() as cursor:
                cursor.execute(query, (user))
        data = cursor.fetchone()
        data = data.get("max")

        groups = request.form.getlist('groups')
        for line in groups:
            group_arr = line.split('::')
            owner_username = group_arr[0]
            owner_groupName = group_arr[1]
            query = "INSERT INTO SharedWith (groupOwner, groupName, photoID) VALUES (%s, %s, %s)"
            with connection.cursor() as cursor:
                cursor.execute(query, (owner_username, owner_groupName, data))
        message = "Image has been successfully uploaded."
        return render_template("upload.html", message=message)
    else:
        message = "Failed to upload image."
        return render_template("upload.html", message=message)

@app.route("/photoLikes/<photo_ID>")
@login_required
def like_user_details(photo_ID):
    query = """SELECT username, rating
               FROM Likes
               WHERE photoID = %s"""
    with connection.cursor() as cursor:
        cursor.execute(query, photo_ID)
    data = cursor.fetchall()
    return render_template("photo_likes.html", likes=data)

@app.route("/taggedUsers/<photo_ID>")
@login_required
def tagged_user_details(photo_ID):
    query = """ SELECT username, firstName, lastName
                FROM Tagged NATURAL JOIN Person
                WHERE photoID=%s AND tagstatus=1"""
    with connection.cursor() as cursor:
        cursor.execute(query, photo_ID)
    data = cursor.fetchall()
    return render_template("tagged_users.html", tagged=data)

if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run()