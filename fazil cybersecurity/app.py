from flask import Flask, render_template, request, redirect, session, flash, jsonify
from database.db import *
from blockchain import Blockchain
import secrets
import hashlib
import random
import time
import json
import re
import os

from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

UPLOAD_FOLDER = 'static/uploads/candidates'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static/uploads/users', exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

ADMIN_ID = "admin"
ADMIN_PHONE = "987654321"
ADMIN_PASSWORD = "nnrg"

login_attempts = {}
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_TIME = 120


def is_within_range(serial, max_limit):
    numeric = [f"{i:02d}" for i in range(1, 100)]
    alphabetic = [f"{char}{i}" for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for i in range(10)]
    full_sequence = numeric + alphabetic
    try:
        current_idx = full_sequence.index(serial.upper())
        limit_idx = full_sequence.index(max_limit.upper())
        return current_idx <= limit_idx
    except ValueError:
        return False


def is_rollno_valid(rollno, rules):
    e_code = "15" if rules['entry_code'] == 'both' else rules['entry_code']
    pattern = rf"^{rules['year']}7Z([{e_code}]{rules['course_code']})({'|'.join(rules['allowed_depts'])})([0-9A-Z]{{2}})$"
    match = re.match(pattern, rollno)
    if not match:
        return False
    return is_within_range(match.group(3), rules['max_range'])


def sanitize_input(input_str):
    if input_str is None:
        return ""
    dangerous_chars = ['<', '>', '"', "'", ';', '--', '/*', '*/', 'xp_', 'sp_']
    result = str(input_str)
    for char in dangerous_chars:
        result = result.replace(char, '')
    return result.strip()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, password_hash):
    return hashlib.sha256(password.encode()).hexdigest() == password_hash

def check_rate_limit(identifier):
    current_time = time.time()
    if identifier in login_attempts:
        attempts, first_attempt_time = login_attempts[identifier]
        if current_time - first_attempt_time < LOCKOUT_TIME:
            if attempts >= MAX_LOGIN_ATTEMPTS:
                return False
        else:
            login_attempts[identifier] = (0, current_time)
    return True

def record_failed_attempt(identifier):
    current_time = time.time()
    if identifier in login_attempts:
        attempts, first_attempt_time = login_attempts[identifier]
        login_attempts[identifier] = (attempts + 1, first_attempt_time)
    else:
        login_attempts[identifier] = (1, current_time)

def reset_login_attempts(identifier):
    if identifier in login_attempts:
        del login_attempts[identifier]


create_votes_table()
create_users_table()
create_candidates_table()
create_settings_table()
migrate_candidates_table()
migrate_users_table()

blockchain = Blockchain.load()

@app.route("/")
def home():
    return render_template("login.html")

# ==================== OTP Routes ====================

@app.route("/send_otp", methods=["POST"])
def send_otp():
    data = request.get_json()
    rollno = sanitize_input(data.get("rollno", ""))
    mobile = sanitize_input(data.get("mobile", ""))
    password = sanitize_input(data.get("password", ""))
    user = validate_login(rollno, mobile, password)
    if not user:
        return jsonify({"success": False, "message": "Invalid credentials"})
    if not is_user_approved(rollno):
        return jsonify({"success": False, "message": "Your account is pending approval. Please contact admin."})
    otp = str(random.randint(100000, 999999))
    expiry = time.time() + 300
    otp_store[rollno] = {"otp": otp, "expiry": expiry, "mobile": mobile}
    print(f"\n===== OTP for {rollno} =====\nOTP: {otp}\nMobile: {mobile}\n========================\n")
    return jsonify({"success": True, "message": "OTP sent successfully!", "otp": otp})

@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    data = request.get_json()
    rollno = sanitize_input(data.get("rollno", ""))
    otp = sanitize_input(data.get("otp", ""))
    if rollno not in otp_store:
        return jsonify({"success": False, "message": "OTP expired or not requested"})
    stored_otp = otp_store[rollno]
    if time.time() > stored_otp["expiry"]:
        del otp_store[rollno]
        return jsonify({"success": False, "message": "OTP expired"})
    if stored_otp["otp"] == otp:
        del otp_store[rollno]
        return jsonify({"success": True, "message": "OTP verified"})
    return jsonify({"success": False, "message": "Invalid OTP"})

# ==================== Registration ====================

election_rules = {
    'year': '23',
    'entry_code': 'both',
    'course_code': 'A',
    'allowed_depts': ['67'],
    'max_range': 'Z9'
}

@app.route('/update_rules', methods=['POST'])
def update_rules():
    if not session.get("admin"):
        return redirect("/")
    global election_rules
    election_rules['year']          = sanitize_input(request.form.get('year'))
    election_rules['course_code']   = sanitize_input(request.form.get('course_code')).upper()
    election_rules['entry_code']    = request.form.get('entry_code')
    election_rules['allowed_depts'] = request.form.getlist('depts')
    election_rules['max_range']     = sanitize_input(request.form.get('max_range')).upper()
    flash("Eligibility rules updated successfully!")
    return redirect('/admin/rules')


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name     = sanitize_input(request.form["name"])
        rollno   = sanitize_input(request.form["rollno"]).upper()
        mobile   = sanitize_input(request.form["mobile"])
        email    = sanitize_input(request.form["email"])
        password = sanitize_input(request.form["password"])
        current_rules = {
            'year': '23', 'entry_code': 'both', 'course_code': 'A',
            'allowed_depts': ['05', '66', '67'], 'max_range': 'Z9'
        }
        if not is_rollno_valid(rollno, current_rules):
            return render_template('register.html', message="Your Roll Number is not eligible for this election.")
        if len(name) < 2 or len(rollno) < 3 or len(password) < 4:
            return render_template("register.html", message="Invalid input length")
        if user_exists(rollno):
            return render_template("register.html", message="User already registered")
        register_user(name, rollno, mobile, email, hash_password(password), approved=False)
        return render_template("register.html", message="Registration successful! Please wait for admin approval.")
    return render_template("register.html")


# ==================== Login ====================

@app.route("/login", methods=["POST"])
def login():
    rollno   = sanitize_input(request.form["rollno"])
    mobile   = sanitize_input(request.form["mobile"])
    password = sanitize_input(request.form["password"])
    if not check_rate_limit(rollno):
        return render_template("login.html", message="Too many attempts. Please try again later.")
    if rollno.lower() == ADMIN_ID and mobile == ADMIN_PHONE and password == ADMIN_PASSWORD:
        session["admin"] = True
        reset_login_attempts(rollno)
        return redirect("/admin")
    user = validate_login(rollno, mobile, password)
    if not user:
        record_failed_attempt(rollno)
        remaining = MAX_LOGIN_ATTEMPTS - 1
        if rollno in login_attempts:
            attempts, _ = login_attempts[rollno]
            remaining = MAX_LOGIN_ATTEMPTS - attempts
        warning_msg = f"Warning: Only {remaining} attempts remaining!" if remaining <= 3 else ""
        return render_template("login.html", message=f"Invalid Data. {warning_msg}".strip())
    if not is_user_approved(rollno):
        return render_template("login.html", message="Your account is pending approval. Please contact admin.")
    reset_login_attempts(rollno)
    session["rollno"] = rollno
    return redirect("/vote")

# ==================== Admin Routes ====================

@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect("/")
    return render_template("admin.html",
                           results_released=get_setting("results_released"),
                           voting_open=get_setting("voting_open"),
                           pending_users=get_pending_users(),
                           all_users=get_all_users())

@app.route("/approve_user", methods=["POST"])
def approve_user():
    if not session.get("admin"):
        return redirect("/")
    approve_user_by_rollno(request.form.get("rollno"))
    return redirect("/admin")

@app.route("/reject_user", methods=["POST"])
def reject_user():
    if not session.get("admin"):
        return redirect("/")
    delete_user(request.form.get("rollno"))
    return redirect("/admin")

@app.route("/registered_students")
def registered_students():
    if not session.get("admin"):
        return redirect("/")
    return render_template("registered_students.html", users=get_all_users())

# ==================== Roll No Rules Page ====================

@app.route("/admin/rules")
def admin_rules():
    if not session.get("admin"):
        return redirect("/")
    return render_template("admin_rules.html",
                           election_rules=election_rules,
                           message=request.args.get("msg"))

# ==================== Visualize / Analytics Page ====================

@app.route("/visualize")
def visualize():
    if not session.get("admin"):
        return redirect("/")

    positions = ["President", "Vice President", "Secretary", "Treasury"]

    # get_results() returns rows: candidate, votes
    vote_data = {}
    for pos in positions:
        rows = get_results(pos)
        vote_data[pos] = [
            {"name": str(row["candidate"]), "votes": int(row["votes"])}
            for row in rows
        ]
        vote_data[pos].sort(key=lambda x: x["votes"], reverse=True)

    # Blockchain stats
    block_count   = len(blockchain.chain)
    pending_count = len(blockchain.pending_transactions)
    chain_valid   = bool(blockchain.is_chain_valid())

    # Voter turnout
    all_users        = get_all_users()
    total_registered = len(all_users)
    total_votes      = sum(1 for u in all_users if u["voted"] == 1)
    turnout_pct      = round((total_votes / total_registered * 100) if total_registered else 0)

    # Hourly placeholder
    hourly_data = {
        "labels": ["08:00","09:00","10:00","11:00","12:00",
                   "13:00","14:00","15:00","16:00","17:00"],
        "counts": [4, 9, 21, 38, 52, 61, 74, 88, total_votes, total_votes]
    }

    # Dept placeholder
    dept_data = {
        "labels": ["CSE", "AIML", "DS", "ECE", "EEE", "Civil"],
        "counts": [42, 31, 28, 18, 11, 6]
    }

    # Insights
    insights = []
    if chain_valid:
        insights.append({"type": "ok",
            "text": f"Blockchain integrity check passed — all {block_count} blocks verified."})
    else:
        insights.append({"type": "alert",
            "text": "Blockchain validation FAILED. Possible tampering detected!"})

    for pos, rows in vote_data.items():
        if len(rows) >= 2 and rows[0]["votes"] > 0:
            gap = rows[0]["votes"] - rows[1]["votes"]
            insights.append({
                "type": "info" if gap > 5 else "warn",
                "text": (f"{pos}: {rows[0]['name']} leads by {gap} "
                         f"vote{'s' if gap != 1 else ''} "
                         f"({'comfortable' if gap > 5 else 'tight'} margin).")
            })

    if total_registered == 0:
        insights.append({"type": "warn", "text": "No registered students yet."})
    elif turnout_pct < 40:
        insights.append({"type": "warn",
            "text": f"Low turnout — only {turnout_pct}% of registered students have voted."})
    else:
        insights.append({"type": "ok",
            "text": f"Healthy turnout at {turnout_pct}% ({total_votes}/{total_registered} students)."})

    if pending_count > 0:
        insights.append({"type": "info",
            "text": f"{pending_count} transaction(s) pending. Auto-mines when 5 accumulate."})

    return render_template(
        "visualize.html",
        vote_data_json   = json.dumps(vote_data),
        hourly_data_json = json.dumps(hourly_data),
        dept_data_json   = json.dumps(dept_data),
        insights_json    = json.dumps(insights),
        block_count      = block_count,
        pending_count    = pending_count,
        chain_valid      = chain_valid,
        total_votes      = total_votes,
        total_registered = total_registered,
        turnout_pct      = turnout_pct,
    )

# ==================== Other Routes ====================

@app.route("/results")
def results():
    results_released = get_setting("results_released")
    if results_released != "true" and not session.get("admin"):
        return render_template("results.html", results_not_released=True)
    return render_template("results.html",
                           president=get_results("President"),
                           vice=get_results("Vice President"),
                           secretary=get_results("Secretary"),
                           treasury=get_results("Treasury"))

@app.route("/student_results")
def student_results():
    if get_setting("results_released") != "true":
        return render_template("student_results.html", results_released=False)
    return render_template("student_results.html",
                           results_released=True,
                           president=get_results("President"),
                           vice=get_results("Vice President"),
                           secretary=get_results("Secretary"),
                           treasury=get_results("Treasury"))

@app.route("/release_results", methods=["POST"])
def release_results():
    if not session.get("admin"):
        return redirect("/")
    action = request.form.get("action")
    messages = {
        "release":      ("results_released", "true",  "Results Released Successfully"),
        "hide":         ("results_released", "false", "Results Hidden Successfully"),
        "open_voting":  ("voting_open",      "true",  "Voting Opened Successfully"),
        "close_voting": ("voting_open",      "false", "Voting Closed Successfully"),
    }
    if action in messages:
        key, val, message = messages[action]
        update_setting(key, val)
    elif action == "clear_candidates":
        clear_all_candidates()
        message = "All Candidates Cleared Successfully"
    elif action == "clear_votes":
        # Clears votes table + resets voted flag on all users so they can vote again
        clear_all_votes()
        message = "All Votes Cleared — Students Can Vote Again"
    else:
        message = ""
    return render_template("admin.html", message=message,
                           results_released=get_setting("results_released"),
                           voting_open=get_setting("voting_open"),
                           pending_users=get_pending_users(),
                           all_users=get_all_users())

@app.route("/vote")
def vote():
    voting_open = get_setting("voting_open") or "true"
    rollno = session.get("rollno")
    return render_template("vote.html",
                           president=get_candidates_by_position("President"),
                           vice_president=get_candidates_by_position("Vice President"),
                           secretary=get_candidates_by_position("Secretary"),
                           treasury=get_candidates_by_position("Treasury"),
                           user=get_user_by_rollno(rollno) if rollno else None,
                           voting_open=voting_open)

@app.route("/add_candidate", methods=["POST"])
def add_candidate_route():
    name     = request.form["candidate_name"]
    symbol   = request.form["candidate_symbol"]
    position = request.form["position"]
    image_filename = None
    if 'candidate_image' in request.files:
        file = request.files['candidate_image']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            image_filename = f"{name.replace(' ', '_')}_{position}_{int(time.time())}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
    result = add_candidate(name, symbol, position, image_filename)
    message = "Candidate Added Successfully" if result else "Symbol already used in this position"
    return render_template("admin.html", message=message,
                           results_released=get_setting("results_released"),
                           voting_open=get_setting("voting_open"),
                           pending_users=get_pending_users(),
                           all_users=get_all_users())

@app.route("/submit_vote", methods=["POST"])
def submit_vote():
    rollno = session.get("rollno")
    if not rollno:
        return redirect("/")
    if has_voted(rollno):
        return render_template("vote.html",
                               message="Your Vote Has Been Cast", msg_color="red",
                               president=get_candidates_by_position("President"),
                               vice_president=get_candidates_by_position("Vice President"),
                               secretary=get_candidates_by_position("Secretary"),
                               treasury=get_candidates_by_position("Treasury"))
    for pos, key in [("President","president"),("Vice President","vice_president"),
                     ("Secretary","secretary"),("Treasury","treasury")]:
        candidate = request.form.get(key)
        save_vote(rollno, pos, candidate)
        blockchain.new_transaction(rollno, pos, candidate)
    mark_voted(rollno)
    if len(blockchain.pending_transactions) >= 5:
        blockchain.mine_pending_transactions("auto")
        blockchain.save()
        print("Auto-mined block after 5 votes")
    blockchain.save()
    return render_template("vote.html",
                           message="Vote cast successfully! Recorded on blockchain.",
                           msg_color="green",
                           president=get_candidates_by_position("President"),
                           vice_president=get_candidates_by_position("Vice President"),
                           secretary=get_candidates_by_position("Secretary"),
                           treasury=get_candidates_by_position("Treasury"))

@app.route("/blockchain")
def blockchain_view():
    total_txs = sum(len(block.transactions) for block in blockchain.chain)
    return render_template("blockchain.html",
                           blocks=blockchain.chain,
                           pending=blockchain.pending_transactions,
                           total_txs=total_txs,
                           valid=blockchain.is_chain_valid())

@app.route("/mine", methods=["GET", "POST"])
def mine_block():
    if not session.get("admin"):
        return redirect("/")
    blockchain.mine_pending_transactions("admin")
    blockchain.save()
    return redirect("/blockchain")

@app.route("/verify_chain")
def verify_chain():
    if blockchain.is_chain_valid():
        flash("Blockchain is valid! ✅")
    else:
        flash("Blockchain invalid! ⚠️")
    return redirect("/blockchain")

if __name__ == "__main__":
    app.secret_key = "voting_secret"
    app.run(debug=True)