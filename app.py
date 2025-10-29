from flask import Flask, jsonify, render_template, request
from pymongo import MongoClient
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Requests

# MongoDB Atlas connection
uri = "mongodb+srv://Ration_db_user:Majorproject2025@cluster0.iqejzl1.mongodb.net/?appName=Cluster0"
client = MongoClient(uri)
db = client["ration_db"]

# Globals for queue management
current_dispensing = None
waiting_queue = []

@app.route('/')
def home():
    return jsonify({"message": "Smart Ration API running!"})


@app.route('/insert_sample')
def insert_sample():
    ration_data = {
        "card_number": "KA1234567890",
        "name": "Ajay Kumar",
        "family_members": 4,
        "ration_allocated_kg": 10,
        "ration_collected_kg": 0,
        "collection_date": None
    }

    db.members.insert_one(ration_data)  # inserts into "members" collection
    return "Sample data inserted into MongoDB."


@app.route('/view_members')
def view_members():
    members = db.members.find()
    output = []
    for member in members:
        output.append({
            "name": member.get("name"),
            "card_number": member.get("card_number"),
            "family_members": member.get("family_members"),
            "ration_allocated_kg": member.get("ration_allocated_kg"),
            "ration_collected_kg": member.get("ration_collected_kg"),
            "collection_date": member.get("collection_date")
        })
    return jsonify(output)


@app.route('/dashboard')
def dashboard():
    members = db.members.find()
    return render_template('members.html', members=members)


def format_member(member):
    return {
        "name": member.get("name"),
        "card_number": member.get("card_number"),
        "family_members": member.get("family_members"),
        "ration_allocated_kg": member.get("ration_allocated_kg"),
        "ration_collected_kg": member.get("ration_collected_kg"),
        "collection_date": (
            member.get("collection_date").isoformat()
            if member.get("collection_date")
            else None
        )
    }


@app.route('/verify_card', methods=['POST'])
def verify_card():
    data = request.get_json()
    card_number = data.get('card_number')
    member = db.members.find_one({"card_number": card_number})
    if member:
        return jsonify(format_member(member))
    else:
        return jsonify({"error": "Card not found"}), 404


@app.route('/add-to-queue', methods=['POST'])
def add_to_queue():
    global waiting_queue
    card_number = request.json.get('card_number')
    member = db.members.find_one({'card_number': card_number})

    if member and member.get('ration_collected_kg', 0) == 0:
        waiting_queue.append(card_number)
        return jsonify({"status": "added_to_queue"})
    else:
        return jsonify({"status": "already_collected_or_invalid"})


@app.route('/get-next-command', methods=['GET'])
def get_next_command():
    global current_dispensing, waiting_queue
    if current_dispensing is None and waiting_queue:
        current_dispensing = waiting_queue.pop(0)
        member = db.members.find_one({'card_number': current_dispensing})
        return jsonify({
            "card_number": current_dispensing,
            "grain_qty": member["ration_allocated_kg"]
        })
    else:
        return jsonify({"status": "wait"})


@app.route('/confirm-dispense', methods=['POST'])
def confirm_dispense():
    global current_dispensing
    card_number = request.json.get("card_number")
    if card_number != current_dispensing:
        return jsonify({"status": "invalid_or_already_cleared"}), 400

    member = db.members.find_one({"card_number": card_number})
    if not member:
        return jsonify({"error": "card not found"}), 404

    try:
        db.members.update_one(
            {"card_number": card_number},
            {"$set": {
                "ration_collected_kg": member.get("ration_allocated_kg", 0),
                "collection_date": datetime.now()
            }}
        )
        current_dispensing = None
        return jsonify({"status": "confirmed"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
