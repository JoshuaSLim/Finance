import os
import re

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]

    total_shares = db.execute("SELECT symbol, SUM(shares) AS shares, price FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
    get_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = get_cash[0]["cash"]

    return render_template("index.html", database=total_shares, cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        if not symbol:
            return apology("Not a symbol")

        stock = lookup(symbol.upper())

        if stock == None:
            return apology("Stock does not exist with that symbol")

        if shares < 0:
            return apology("Not enough share")

        share_purchased = shares * stock["price"]

        user_id = session["user_id"]
        get_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        current_amount = get_cash[0]["cash"]

        if current_amount < share_purchased:
            return apology("Not enough cash for purchasing")

        new_amount = current_amount - share_purchased

        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_amount, user_id)

        date = datetime.datetime.now()

        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES(?, ?, ?, ?, ?)", user_id, stock["symbol"], shares, stock["price"], date)

        flash("Buy")

        return redirect("/")




@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    history = db.execute("SELECT * FROM transactions WHERE user_id=?", user_id)
    return render_template("history.html", transactions = history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("Not a symbol")

        stock_quote = lookup(symbol.upper())

        if stock_quote == None:
            return apology("Symbol does not exist")

        return render_template("quoted.html", name = stock_quote["name"], price = stock_quote["price"], symbol = stock_quote["symbol"])


def valid_password(password):
    """Require users passwords to have some number of letters, numbers, and/or symbols"""
    if not re.search("[a-zA-Z]", password):
        return False

    if not re.search("[0-9]", password):
        return False

    if not re.search("[!@#$%^*()_+-]", password):
        return False

    return True

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")

    if not request.form.get("username"):
        return apology("must provide username", 400)

    if not request.form.get("password"):
        return apology("must provide password", 400)

    if not request.form.get("confirmation"):
        return apology("must confirm password", 400)

    if request.form.get("password") != request.form.get("confirmation"):
        return apology("passwords much match", 400)

    if db.execute("SELECT username FROM users WHERE username = ?", request.form.get("username")):
        return apology("username already exists, please choose a different username", 400)

    if not valid_password(request.form.get("password")):
        return apology("password must contain at least one letter, number, and symbol", 400)

    else:
        hash = generate_password_hash(request.form.get("password"))

        db.execute("INSERT INTO users (username,hash) VALUES(?,?)", request.form.get("username"), hash)

        return redirect("/login")


def usd(amount):
    """Format a number as currency."""
    return "${0:,.2f}".format(amount)

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]

    if request.method == "GET":
        stocks = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
        return render_template("sell.html", symbols = [row["symbol"] for row in stocks])
    else:
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        if not symbol:
            return apology("Not a symbol")

        stock = lookup(symbol.upper())

        if stock == None:
            return apology("Stock does not exist with that symbol")

        if shares < 0:
            return apology("Not enough share")

        current_shares = db.execute("SELECT shares FROM transactions WHERE user_id = ? and symbol = ?", user_id, symbol)

        if shares > current_shares[0]["shares"]:
            shares = current_shares[0]["shares"]

        transaction = shares * stock["price"]

        get_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        current_amount = get_cash[0]["cash"]

        new_amount = current_amount + transaction
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_amount, user_id)

        date = datetime.datetime.now()

        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES(?, ?, ?, ?, ?)", user_id, stock["symbol"], (-1 * shares), stock["price"], date)

        flash("Sold")

    return redirect("/")