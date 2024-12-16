from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
from deep_translator import GoogleTranslator
import random
from string import ascii_uppercase

app = Flask(__name__)
app.config["SECRET_KEY"] = "arshmalek"
socketio = SocketIO(app)

rooms = {}

def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)
        
        if code not in rooms:
            break
    
    return code

@app.route("/", methods=["POST", "GET"])
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        language = request.form.get("language", "en")  # Add a language option
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if not name:
            return render_template("home.html", error="Please enter a name.", code=code, name=name)

        if join != False and not code:
            return render_template("home.html", error="Please enter a room code.", code=code, name=name)
        
        room = code
        if create != False:
            room = generate_unique_code(4)
            rooms[room] = {"members": 0, "messages": [], "languages": {}}
        elif code not in rooms:
            return render_template("home.html", error="Room does not exist.", code=code, name=name)
        
        session["room"] = room
        session["name"] = name
        session["language"] = language  # Save user's preferred language
        rooms[room]["languages"][name] = language  # Track user's language in the room
        return redirect(url_for("room"))

    return render_template("home.html")

@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))

    return render_template("room.html", code=room, messages=rooms[room]["messages"])

# WebRTC Signaling and Voice Calling functionality
@socketio.on("offer")
def offer(data):
    room = session.get("room")
    if room not in rooms:
        return
    # Send the offer to the other user in the room
    other_user = next((user for user in rooms[room]["languages"] if user != session["name"]), None)
    if other_user:
        send({"type": "offer", "offer": data["offer"], "from": session["name"]}, to=other_user)

@socketio.on("answer")
def answer(data):
    room = session.get("room")
    if room not in rooms:
        return
    # Send the answer to the person who initiated the call
    send({"type": "answer", "answer": data["answer"], "from": session["name"]}, to=data["from"])

@socketio.on("ice_candidate")
def ice_candidate(data):
    room = session.get("room")
    if room not in rooms:
        return
    # Send the ICE candidate to the other user
    send({"type": "ice_candidate", "candidate": data["candidate"], "from": session["name"]}, to=data["to"])

@socketio.on("message")
def message(data):
    room = session.get("room")
    name = session.get("name")
    if room not in rooms:
        return 
    
    content = {
        "name": name,
        "message": data["data"]
    }

    # Translate message for each user in the room
    for member_name, language in rooms[room]["languages"].items():
        translated_message = data["data"]  # Default message
        if session["language"] != "en":  # Translate only if user language is not English
            translated_message = GoogleTranslator(source='en', target=session["language"]).translate(data["data"])
        
        content = {
            "name": name,
            "message": translated_message
        }
        send(content, to=room)
    
    # Save original message in the room's chat history
    rooms[room]["messages"].append({"name": name, "message": data["data"]})
    print(f"{name} said: {data['data']} (Translated for all users)")

@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return
    
    join_room(room)
    send({"name": name, "message": "has entered the room"}, to=room)
    rooms[room]["members"] += 1
    print(f"{name} joined room {room}")

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]
    
    send({"name": name, "message": "has left the room"}, to=room)
    print(f"{name} has left the room {room}")

if __name__ == "__main__":
    socketio.run(app, debug=True)
