from flask import Flask, session, request, jsonify, render_template, redirect, url_for, flash
from flask_pymongo import PyMongo
from pymongo import MongoClient
from flask_cors import CORS
from bson import ObjectId
from datetime import datetime

app = Flask(__name__)
CORS(app)

app.config["MONGO_URI"] = "mongodb+srv://vasudha:vasudha@cluster0.0vkno.mongodb.net/usersDB?authSource=admin&retryWrites=true&w=majority&readPreference=primary"
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
    try:
        # Explicitly fetch only scenarios marked as visible to users
        scenarios = list(mongo.db.admin.find({
            "visible_to_users": True
        }).sort('user_approval_date', -1))
        return render_template('index.html', scenarios=scenarios)
    except Exception as e:
        print(f"Error fetching scenarios: {e}")
        return jsonify({"error": "Failed to fetch scenarios"}), 500

@app.route('/admindashboard')
def admin_dashboard():
    scenarios = mongo.db.admin.find()
    return render_template('admindashboard.html', scenarios=scenarios)

@app.route('/summary')
def summary():
    return render_template('summary.html')

@app.route('/get_prompt', methods=['POST'])
def get_prompt():
    try:
        request_data = request.json
        print("Received Request Data:", request_data)

        scenario_id = request.json.get('scenario_id', '')
        print(f"Extracted Scenario ID: {scenario_id}")

        if not scenario_id:
            return jsonify({"error": "No scenario ID provided"}), 400
        
        try:
            object_id = ObjectId(scenario_id)
        except Exception as e:
            print(f"Invalid ObjectId: {e}")
            return jsonify({"error": "Invalid scenario ID format"}), 400
        
        scenario_data = mongo.db.admin.find_one({"_id": object_id})

        if scenario_data and "prompt" in scenario_data:
            updated_prompt = scenario_data["prompt"]
            return jsonify({"prompt": updated_prompt})
        else:
            return jsonify({"error": "Scenario not found"}), 404
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Failed to fetch prompt"}), 500

@app.route('/index')
def question():
    scenarios = mongo.db.admin.find({"visible_to_users": True})
    return render_template('index.html', scenarios=scenarios)

@app.route('/create', methods=['POST'])
def create_scenario():
    try:
        data = request.json
        result = mongo.db.admin.insert_one({
            "scenario": data['scenario'],
            "prompt": data['prompt'],
            "question": data['question'],
            "visible_to_users": False
        })
        return jsonify({"message": "Roleplay created successfully", "id": str(result.inserted_id)}), 201
    except Exception as e:
        print(f"Error creating scenario: {e}")
        return jsonify({"error": "Failed to create scenario"}), 500

@app.route('/history', methods=['GET'])
def get_history():
    try:
        history = mongo.db.admin.find()
        return jsonify([
            {
                "_id": str(doc['_id']),
                "scenario": doc.get('scenario', ''),
                "prompt": doc.get('prompt', ''),
                "question": doc.get('question', ''),
                "visible_to_users": doc.get('visible_to_users', False),
                "visible_to_admin": doc.get('visible_to_admin', False)
            }
            for doc in history
        ]), 200
    except Exception as e:
        print(f"Error fetching history: {e}")
        return jsonify({"error": "Failed to fetch history"}), 500

@app.route('/delete/<scenario_id>', methods=['DELETE'])
def delete_scenario(scenario_id):
    try:
        object_id = ObjectId(scenario_id)
        result = mongo.db.admin.delete_one({'_id': object_id})
        
        if result.deleted_count > 0:
            return jsonify({"message": "Scenario deleted successfully"}), 200
        else:
            return jsonify({"error": "Scenario not found"}), 404
    except Exception as e:
        print(f"Error deleting scenario: {e}")
        return jsonify({"error": "Failed to delete scenario"}), 500

@app.route('/delete-batch', methods=['POST'])
def delete_batch():
    try:
        scenario_ids = request.json.get('ids', [])
        if not scenario_ids:
            return jsonify({"error": "No scenarios specified"}), 400

        object_ids = [ObjectId(id) for id in scenario_ids]
        result = mongo.db.admin.delete_many({'_id': {'$in': object_ids}})
        
        if result.deleted_count > 0:
            return jsonify({
                "message": f"Successfully deleted {result.deleted_count} scenarios",
                "deleted_count": result.deleted_count
            }), 200
        else:
            return jsonify({"error": "No scenarios found to delete"}), 404
    except Exception as e:
        print(f"Error in batch delete: {e}")
        return jsonify({"error": "Failed to delete scenarios"}), 500

@app.route('/toggle_admin_visibility', methods=['POST'])
def toggle_admin_visibility():
    """Super admin endpoint to toggle visibility for admins"""
    try:
        scenario_ids = request.json.get('ids', [])
        if not scenario_ids:
            return jsonify({"error": "No scenarios specified"}), 400

        object_ids = [ObjectId(id) for id in scenario_ids]
        
        # Update visibility for admins
        result = mongo.db.admin.update_many(
            {'_id': {'$in': object_ids}},
            {'$set': {'visible_to_admin': True}}
        )
        
        # # Set others to not visible to admin
        # mongo.db.admin.update_many(
        #     {'_id': {'$nin': object_ids}},
        #     {'$set': {'visible_to_admin': False}}
        # )

        return jsonify({
            "message": f"Successfully updated admin visibility for {result.modified_count} scenarios",
            "modified_count": result.modified_count
        }), 200
    except Exception as e:
        print(f"Error toggling admin visibility: {e}")
        return jsonify({"error": "Failed to update scenarios"}), 500

@app.route('/toggle_visibility', methods=['POST'])
def toggle_visibility():
    """Super admin endpoint to toggle visibility for users"""
    try:
        scenario_ids = request.json.get('ids', [])
        if not scenario_ids:
            return jsonify({"error": "No scenarios specified"}), 400

        object_ids = [ObjectId(id) for id in scenario_ids]
        
        # Update visibility for users
        result = mongo.db.admin.update_many(
            {'_id': {'$in': object_ids}},
            {'$set': {'visible_to_users': True}}
        )

        return jsonify({
            "message": f"Successfully updated visibility for {result.modified_count} scenarios",
            "modified_count": result.modified_count
        }), 200
    except Exception as e:
        print(f"Error toggling visibility: {e}")
        return jsonify({"error": "Failed to update scenarios"}), 500
@app.route('/admin')
def admin_view():
    """Route for the regular admin dashboard"""
    return render_template('admin_dashboard.html')

@app.route('/admin/scenarios')
def get_admin_scenarios():
    """Get scenarios that are visible to admin (approved by super admin)"""
    try:
        # Get all scenarios that super admin has made visible to admin
        scenarios = list(mongo.db.admin.find({"visible_to_admin": True}))
        return jsonify([
            {
                "_id": str(doc['_id']),
                "scenario": doc.get('scenario', ''),
                "prompt": doc.get('prompt', ''),
                "question": doc.get('question', ''),
                "visible_to_users": doc.get('visible_to_users', False)
            }
            for doc in scenarios
        ]), 200
    except Exception as e:
        print(f"Error fetching admin scenarios: {e}")
        return jsonify({"error": "Failed to fetch scenarios"}), 500

@app.route('/admin/toggle_visibility', methods=['POST'])
def admin_toggle_visibility():
    """Admin endpoint to toggle user visibility"""
    try:
        scenario_ids = request.json.get('ids', [])
        action = request.json.get('action', 'add')  # Add this line
        if not scenario_ids:
            return jsonify({"error": "No scenarios specified"}), 400

        object_ids = [ObjectId(id) for id in scenario_ids]
        
        # Verify these scenarios are visible to admin first
        visible_to_admin = mongo.db.admin.count_documents({
            '_id': {'$in': object_ids},
            'visible_to_admin': True
        })
        
        if visible_to_admin != len(scenario_ids):
            return jsonify({"error": "Unauthorized access to some scenarios"}), 403

        # Update visibility for users
        if action == 'add':
            result = mongo.db.admin.update_many(
                {'_id': {'$in': object_ids}},
                {
                    '$set': {
                        'visible_to_users': True,
                        'user_approval_date': datetime.now()
                    }
                }
            )
        else:
            result = mongo.db.admin.update_many(
                {'_id': {'$in': object_ids}},
                {
                    '$set': {
                        'visible_to_users': False
                    },
                    '$unset': {
                        'user_approval_date': ''
                    }
                }
            )

        return jsonify({
            "message": f"Successfully {'added to' if action == 'add' else 'removed from'} user view",
            "modified_count": result.modified_count
        }), 200
    except Exception as e:
        print(f"Error toggling user visibility: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/remove_admin_visibility', methods=['POST'])
def remove_admin_visibility():
    """Remove scenarios from admin view"""
    try:
        scenario_ids = request.json.get('ids', [])
        if not scenario_ids:
            return jsonify({"error": "No scenarios specified"}), 400

        object_ids = [ObjectId(id) for id in scenario_ids]
        
        result = mongo.db.admin.update_many(
            {'_id': {'$in': object_ids}},
            {'$set': {'visible_to_admin': False}}
        )

        return jsonify({
            "message": f"Successfully removed admin visibility for {result.modified_count} scenarios",
            "modified_count": result.modified_count
        }), 200
    except Exception as e:
        print(f"Error removing admin visibility: {e}")
        return jsonify({"error": "Failed to update scenarios"}), 500

@app.route('/admin/current-user-scenarios')
def get_current_user_scenarios():
    """Get scenarios that are currently visible to users"""
    try:
        scenarios = mongo.db.admin.find({"visible_to_users": True})
        return jsonify([{
            "_id": str(doc['_id']),
            "scenario": doc.get('scenario', ''),
            "prompt": doc.get('prompt', ''),
            "question": doc.get('question', ''),
            "approval_date": doc.get('user_approval_date', None)
        } for doc in scenarios]), 200
    except Exception as e:
        print(f"Error fetching user scenarios: {e}")
        return jsonify({"error": "Failed to fetch scenarios"}), 500

@app.route('/superadmin/toggle_admin_visibility', methods=['POST'])
def superadmin_toggle_admin_visibility():
    try:
        scenario_ids = request.json.get('ids', [])
        action = request.json.get('action', 'add')  # 'add' or 'remove'
        
        if not scenario_ids:
            return jsonify({"error": "No scenarios specified"}), 400

        object_ids = [ObjectId(id) for id in scenario_ids]
        
        if action == 'add':
            # Update visibility and add approval date for admin
            result = mongo.db.admin.update_many(
                {'_id': {'$in': object_ids}},
                {
                    '$set': {
                        'visible_to_admin': True,
                        'admin_approval_date': datetime.now().isoformat()
                    }
                }
            )
        else:  # remove
            # Remove visibility from admin
            result = mongo.db.admin.update_many(
                {'_id': {'$in': object_ids}},
                {
                    '$set': {'visible_to_admin': False},
                    '$unset': {'admin_approval_date': ''}
                }
            )

        return jsonify({
            "message": f"Successfully {'added to' if action == 'add' else 'removed from'} admin view",
            "modified_count": result.modified_count
        }), 200
    except Exception as e:
        print(f"Error toggling admin visibility: {e}")
        return jsonify({"error": "Failed to update scenarios"}), 500

@app.route('/superadmin/toggle_user_visibility', methods=['POST'])
def superadmin_toggle_user_visibility():
    """Super admin endpoint to toggle visibility for users"""
    try:
        scenario_ids = request.json.get('ids', [])
        action = request.json.get('action', 'add')  # 'add' or 'remove'
        
        if not scenario_ids:
            return jsonify({"error": "No scenarios specified"}), 400

        object_ids = [ObjectId(id) for id in scenario_ids]
        
        update_data = {
            '$set': {
                'visible_to_users': action == 'add',
                'user_approval_date': datetime.now().isoformat() if action == 'add' else None
            }
        }

        result = mongo.db.admin.update_many(
            {'_id': {'$in': object_ids}},
            update_data
        )

        return jsonify({
            "message": f"Successfully {'added to' if action == 'add' else 'removed from'} user view",
            "modified_count": result.modified_count
        }), 200
    except Exception as e:
        print(f"Error toggling user visibility: {e}")
        return jsonify({"error": "Failed to update scenarios"}), 500


@app.route('/superadmin/current-user-scenarios', methods=['GET'])
def superadmin_get_user_scenarios():
    """Get scenarios that are currently visible to users (for super admin view)"""
    try:
        scenarios = mongo.db.admin.find({"visible_to_users": True})
        return jsonify([{
            "_id": str(doc['_id']),
            "scenario": doc.get('scenario', ''),
            "approval_date": doc.get('user_approval_date', None),
            "admin_approval_date": doc.get('admin_approval_date', None)
        } for doc in scenarios]), 200
    except Exception as e:
        print(f"Error fetching user scenarios: {e}")
        return jsonify({"error": "Failed to fetch scenarios"}), 500


@app.route('/superadmin/current-admin-scenarios', methods=['GET'])
def superadmin_get_admin_scenarios():
    """Get scenarios that are currently visible to admin"""
    try:
        scenarios = mongo.db.admin.find({"visible_to_admin": True})
        return jsonify([{
            "_id": str(doc['_id']),
            "scenario": doc.get('scenario', ''),
            "approval_date": doc.get('admin_approval_date', None),
            "user_visible": doc.get('visible_to_users', False)
        } for doc in scenarios]), 200
    except Exception as e:
        print(f"Error fetching admin scenarios: {e}")
        return jsonify({"error": "Failed to fetch scenarios"}), 500


if __name__ == '__main__':
    app.run(debug=True)