from curses.ascii import isdigit
import os
from pickle import STOP
from site import execusercustomize
from sys import exec_prefix
from urllib.parse import uses_relative
from click import pass_context

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from numpy import lookfor, quantile
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


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
    # firs need to know what shares user have
    # group them together
    users_id = session["user_id"]
    stocks = db.execute(
        "SELECT *, SUM(quantity) AS total_quantity, SUM(buy_price * quantity) AS spent_total FROM purchase WHERE user_id=? GROUP BY symbol HAVING SUM (quantity)", users_id)

    # now we need qurren price, total of each, total balance
    users_current_cash = db.execute("SELECT cash FROM users WHERE id=?", users_id)[0]["cash"]
    total_balance = users_current_cash

    for stock in stocks:
        live_price = lookup(stock["symbol"])["price"]
        total_value = live_price * stock["total_quantity"]
        # adding name it maybe looks nicer in the table
        name = lookup(stock["symbol"])["name"]
        margin = total_value - stock["spent_total"]

        stock.update({"live_price": live_price, "total_value": total_value, "name": name, "margin": margin})
        total_balance += total_value

    return render_template("index.html", stocks=stocks, total_balance=usd(total_balance), cash=usd(users_current_cash), usd=usd)
    return apology("TODO")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")

    if request.method == "POST":
        number = request.form.get("shares")
        symbol = request.form.get("symbol")

        stock = lookup(symbol)

        # check for erros : if inserted number?, if stock exsists, if its positive quantity
        if not number:
            return apology("insert number")
        if stock == None:
            return apology("stock doesn't exsists"+number)
        # checks if input is a number
        try:
            quantity = int(number)
        except:
            return apology("not a int")

        # quantity = int(number)
        if not quantity > 0:
            return apology("must be possitive number not this crap: "+number)

        # check price stock and if you can buy it
        users_id = session["user_id"]
        current_price = stock["price"]
        price = quantity * current_price

        # its list of dic [{'cash': 10000}]
        users_cash = db.execute("SELECT cash FROM users WHERE (id = ?)", users_id)

        # check if we have enough money // meaning users_cash[] in a first list dictionari of list , ["cash"] check "cash" value of that dict.
        if users_cash[0]["cash"] < price:
            return apology("You are ubagas, cant afford")

        # if everything is okay and you can buy it:
        # collecy info of purchase
        cash_left = users_cash[0]["cash"] - price
        db.execute("INSERT INTO purchase (user_id, action, symbol, quantity, buy_price) VALUES (?, ?, ?, ?, ?)",
                   users_id, "buying", symbol, quantity, current_price)
        db.execute("UPDATE users SET cash=? WHERE id=?", cash_left, users_id)

    return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    users_id = session["user_id"]
    history = db.execute("SELECT * FROM purchase WHERE user_id=?", users_id)

    return render_template("history.html", stocks=history, usd=usd)
    return apology("TODO")


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
        # gets what share are looking fore
        quote = request.form.get("symbol")

        # from lookup function gets info about stock as dic
        stock = lookup(quote)
        if stock == None:
            return apology("stock doesn't exsists")
        return render_template("quoted.html", stock=stock, usd=usd)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")

    else:
        name = request.form.get("username")
        password = request.form.get("password")
        re_password = request.form.get("confirmation")

        # usernamecheck = db.execute("SELECT COUNT(username) FROM users WHERE username = ?", name)
        # check if everthing is filled
        if not name or not password or not re_password:
            return apology("Please fill all tables")

        # check if password match
        elif not password == re_password:
            return apology("Passwords does't match")

        # try to insert new user to  sql db, if not possible
        # say that username already exists
        hashed_password = generate_password_hash(password)

        # tryes to insret
        try:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", name, hashed_password)
        # if cant insert returns error message
        except:
            return apology("already exists")

        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    users_id = session["user_id"]
    stocks = db.execute("SELECT symbol FROM purchase WHERE user_id=? GROUP BY symbol ", users_id)

    if request.method == "GET":
        return render_template("sell.html", stocks=stocks)

    if request.method == "POST":
        # geting what shares users wanna sell and how many
        sell_stock = request.form.get("symbol")
        number = request.form.get("shares")

        # if no stock selected
        if sell_stock == None:
            return apology("no stock selected")

        # if no quantity selected
        if not number:
            return apology("are you blind? insert number")
        sell_quantity = int(number)

        # owned quantity of that selected stock
        # onwned_quantity = db.execute("SELECT SUM(quantity) AS quantity FROM purchase WHERE user_id=? AND symbol=?", users_id, sell_stock)[0]["quantity"]
        onwned_quantity = db.execute(
            "SELECT SUM(quantity) AS quantity FROM purchase WHERE user_id=? AND symbol=?", users_id, sell_stock)

        # pops error if smth is wrong with db
        onwned_quantity = onwned_quantity[0].get("quantity") if onwned_quantity else None
        if not onwned_quantity:
            return apology("error")

        # if user dont own that mutch
        if onwned_quantity < sell_quantity:
            return apology("you dont own that mutch looser")

        # check current price
        sell_price = lookup(sell_stock)["price"]
        # total price
        total_price = sell_price * sell_quantity

        # update db
        # insert action to history
        db.execute("INSERT INTO purchase (user_id, action, symbol, quantity, buy_price) VALUES (?, ?, ?, ?, ?)",
                   users_id, "sell", sell_stock, -sell_quantity, -sell_price)
        # update current cash
        db.execute("UPDATE users SET cash = (cash + ?) WHERE id = ?", total_price, users_id)

    # back to hp
    return redirect("/")
