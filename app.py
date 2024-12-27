from flask import Flask,session,request, jsonify, render_template, redirect, url_for, flash
from flask_pymongo import PyMongo
from pymongo import MongoClient
from flask_cors import CORS
from bson import ObjectId


app = Flask(__name__)
CORS(app)


app.config["MONGO_URI"] =  "mongodb+srv://vasudha:vasudha@cluster0.0vkno.mongodb.net/usersDB?authSource=admin&retryWrites=true&w=majority&readPreference=primary"
mongo = PyMongo(app)

try:
    client = MongoClient('mongodb+srv://vasudha:vasudha@cluster0.0vkno.mongodb.net/usersDB?authSource=admin&retryWrites=true&w=majority&readPreference=primary')
    db = client.get_database("usersDB")
    print("Databases:", client.list_database_names())
    print("Connection successful!")
except Exception as e:
    print("Connection failed:", e)

@app.route('/')
def home():
    # Query the 'admin' collection for all scenarios
    scenarios = mongo.db.admin.find()  
    # Render 'index.html' and pass 'scenarios' to it
    return render_template('index.html', scenarios=scenarios)

@app.route('/admindashboard')
def admin_dashboard():
    return render_template('admindashboard.html')

@app.route('/get_prompt', methods=['POST'])
def get_prompt():
    try:
        # Get the selected scenario ID
        request_data = request.json
        print("Received Request Data:",request_data)

                # Get the selected scenario ID
        scenario_id = request.json.get('scenario_id', '')
        print(f"Extracted Scenario ID: {scenario_id}")


        if not scenario_id:
            return jsonify({"error": "No scenario ID provided"}), 400
        
        try:
            object_id = ObjectId(scenario_id)
            print(f"Converted ObjectId: {object_id}")
        except Exception as e:
            print(f"Invalid ObjectId: {e}")
            return jsonify({"error": "Invalid scenario ID format"}), 400
        
        # Query MongoDB for the corresponding prompt
        scenario_data = mongo.db.admin.find_one({"_id": object_id})
        print(f"Queried Scenario Data: {scenario_data}")

        if scenario_data and "prompt" in scenario_data:
            print(f"Fetched Prompt: {scenario_data['prompt']}")
            # Store the prompt in the session
            updated_prompt = scenario_data["prompt"]
            return jsonify({"prompt": updated_prompt})
        else:
            return jsonify({"error": "Scenario not found"}), 404
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Failed to fetch prompt"}), 500


@app.route('/index')
def question():
    scenarios = mongo.db.admin.find()  # Replace 'scenarios' with your collection name
    return render_template('index.html', scenarios=scenarios)


# Route to create a new roleplay scenario
@app.route('/create', methods=['POST'])
def create_scenario():
    data = request.json
    mongo.db.admin.insert_one({
        "scenario": data['scenario'],
        "prompt": data['prompt'],
        "question": data['question']
    })
    return jsonify({"message": "Roleplay created successfully"}), 201


@app.route('/history', methods=['GET'])
def get_history():
    history = mongo.db.admin.find()
    return jsonify([
        {
            "_id": str(doc['_id']),
            "scenario": doc.get('scenario', ''),  # Default to empty string if key is missing
            "prompt": doc.get('prompt', ''),
            "question": doc.get('question', '')  # Use .get() to handle missing keys
        }
        for doc in history
    ]), 200


if __name__ == '__main__':
    app.run(debug=True)