from flask import Flask, request, render_template, redirect, session, url_for
app = Flask(__name__)


@app.route('/')
def home():
    if session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST','GET'])
def login():
    return render_template('login.html')

@app.route('/signup', methods=['POST','GET'])
def signup():
    return render_template('signup.html')

if(__name__ == "__main__"):
    app.run(debug=True)