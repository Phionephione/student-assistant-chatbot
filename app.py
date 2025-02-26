from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
import google.generativeai as genai
import os
from dotenv import load_dotenv
from docx import Document
from io import BytesIO
import requests
from bs4 import BeautifulSoup
from serpapi import GoogleSearch  # Import serpapi

load_dotenv()

app = Flask(__name__)
app.secret_key = "super secret key"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-pro')

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

users = {}

# Store the conversation history
conversation_history = {}


@app.route("/", methods=["GET"])
def index():
    if 'username' in session:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if username in users:
            return render_template("register.html", error="Username already exists")

        users[username] = {"email": email, "password": password}
        conversation_history[username] = []
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username in users and users[username]["password"] == password:
            session['username'] = username
            return redirect(url_for("chat"))
        else:
            return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")


@app.route("/chat", methods=["GET"])
def chat():
    if 'username' in session:
        return render_template("chat.html", name=session['username'])
    else:
        return redirect(url_for('login'))


@app.route("/logout")
def logout():
    session.pop('username', None)
    return redirect(url_for("login"))

def get_reference_links(query, num_links=3):
    """Searches Google and returns a list of reference links."""
    try:
        params = {
            "engine": "google",
            "q": query,
            "api_key": SERPAPI_API_KEY,
            "num": num_links
        }

        search = GoogleSearch(params)
        results = search.get_dict()
        links = [result["link"] for result in results.get("organic_results", [])]
        return links
    except Exception as e:
        print(f"Error fetching reference links: {e}")
        return []


def get_images(query, num_images=3):
    """Searches Google Images and returns a list of image URLs."""
    try:
        params = {
            "engine": "google_images",
            "q": query,
            "api_key": SERPAPI_API_KEY,
            "num": num_images
        }

        search = GoogleSearch(params)
        results = search.get_dict()
        images = [result["original"] for result in results.get("images_results", [])]
        return images
    except Exception as e:
        print(f"Error fetching images: {e}")
        return []

@app.route("/get_response", methods=["POST"])
def get_response():
    user_input = request.form["user_input"]
    username = session['username']

    try:
        gemini_response = model.generate_content(user_input)
        answer_text = gemini_response.text

        #Store the response in conversation history without links and images
        conversation_history[username].append({
            "question": user_input,
            "answer": answer_text,
            "links": [], # Store links as empty list initially
            "images": [] # Store images as empty list initially
        })
        return jsonify({"response": answer_text, "index": len(conversation_history[username]) - 1})  # Return the index
    except Exception as e:
        return jsonify({"response": f"Error: {str(e)}"})

@app.route("/get_references", methods=["POST"])
def get_references():
    username = session['username']
    index = int(request.form["index"])

    if 0 <= index < len(conversation_history[username]):
        question = conversation_history[username][index]["question"]
        reference_links = get_reference_links(question)
        image_urls = get_images(question)

        conversation_history[username][index]["links"] = reference_links
        conversation_history[username][index]["images"] = image_urls
        return jsonify({"links": reference_links, "images": image_urls})
    else:
        return jsonify({"error": "Invalid index"})


@app.route("/download_chat")
def download_chat():
    username = session['username']
    history = conversation_history[username]

    document = Document()
    document.add_heading("Conversation History", 0)

    for item in history:
        document.add_paragraph(f"Question: {item['question']}")
        document.add_paragraph(f"Answer: {item['answer']}")

        if item["links"]:
            document.add_paragraph("References:")
            for link in item["links"]:
                document.add_paragraph(link, style='List Bullet')

        document.add_paragraph("")  # Add a blank line between entries

    # Save the document to a BytesIO object
    doc_io = BytesIO()
    document.save(doc_io)
    doc_io.seek(0)  # important to reset the stream position

    return send_file(
        doc_io,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name=f"conversation_{username}.docx"
    )

@app.route("/contact")
def contact():
    return render_template("contact.html")

if __name__ == "__main__":
    app.run()