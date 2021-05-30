import os


from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
#if not os.environ.get("API_KEY"):
# raise RuntimeError("API_KEY not set")






@app.route("/")
@login_required
def index():

    user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    stocks = db.execute("SELECT symbol, SUM(amount_of_shares) as shares, operation FROM transactions WHERE user_id = ? GROUP BY symbol HAVING (SUM(amount_of_shares)) > 0;",
        session["user_id"],
    )
    total_cash_stocks = 0
    for stock in stocks:
        quote = lookup(stock["symbol"])
        stock["name"] = quote["name"]
        stock["symbol"] = stock["symbol"]
        stock["price"] = quote["price"]
        stock["shares"] = stock["shares"]
        stock["total"] = stock["price"] * stock["shares"]
        total_cash_stocks = total_cash_stocks + stock["total"]

    total_cash = total_cash_stocks + user_cash[0]["cash"]
    return render_template(
        "index.html", stocks=stocks, user_cash=user_cash[0], total_cash=total_cash)




@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide a symbol", 403)
        if not request.form.get("shares").isdigit():
            return apology("must provide amount of shares")

        symbol = request.form.get("symbol").upper()
        shares = int(request.form.get("shares"))
        stock = lookup(symbol)
        if stock is None:
            return apology("Please enter a valid symbol")

        rows = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
        cash = rows[0]["cash"]
        cash_left = cash - shares * stock["price"]
        type_trans = "Buy"
        if cash_left < 0:
            return apology("Unfortunately, not enough cash left")

        db.execute("UPDATE users SET cash = :cash_left WHERE id = :id", cash_left = cash_left, id = session["user_id"])
        db.execute("""INSERT INTO transactions (user_id, symbol, amount_of_shares, price, operation) VALUES(:user_id, :symbol, :amount_of_shares, :price, :operation)""",
                      user_id = session["user_id"],
                      symbol =symbol.upper(),
                      amount_of_shares = shares,
                      price = stock["price"],
                      operation = type_trans)
        flash("Bought shares!")
        return redirect("/")


    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    stocks = db.execute("SELECT * FROM transactions WHERE user_id = ?", session["user_id"])
    return render_template("history.html", stocks=stocks)


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
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Please insert stock symbol", 400)
        symbol = request.form.get("symbol").upper()
        stock = lookup(symbol)
        if stock == None:
            return apology("Invalid symbol", 400)
        return render_template("quoted.html", stockInfo = {
            "Name": stock["name"],
            "Symbol": stock["symbol"],
            "Price": usd(stock["price"])
        })
    else:
        return render_template("quote.html")

    return apology("TODO")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("Please type password again", 400)
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Please enter the same password")

        try:
            row = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
                            username = request.form.get("username"),
                            hash = generate_password_hash(request.form.get("password")))
        except:
            return apology("Username already taken", 400)

        session["user_id"] = row
        return redirect("/")
    else:
        return render_template("register.html")





@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if request.method == "POST":
        if not request.form.get("oldpass"):
            return apology("must provide old password", 403)

        elif not request.form.get("newpass"):
            return apology("must provide a new password", 403)
        elif not request.form.get("confirmation"):
            return apology("Please insert new password again", 403)
        if request.form.get("newpass") != request.form.get("confirmation"):
            return apology("Please enter the same new password")

        #old_pass = db.execute("SELECT hash FROM users WHERE id = :id", id = session["user_id"])
        rows = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])
        if not check_password_hash(rows[0]["hash"], request.form.get("oldpass")):
            return apology("Invalid current password", 403)

        db.execute("UPDATE users SET hash = :hash WHERE id = :id ", hash = generate_password_hash(request.form.get("newpass")), id = session["user_id"] )

        flash("Password changed!")
        #remember which user has logged in
        session["user_id"] = rows[0]["id"]

        return redirect("/")
    else:
        return render_template("change_password.html")




@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide a symbol", 403)
        if not request.form.get("shares").isdigit():
            return apology("must provide amount of shares")

        symbol = request.form.get("symbol").upper()
        shares = int(request.form.get("shares"))
        stock = lookup(symbol)
        if stock is None:
            return apology("Please enter a valid symbol")

        stocks = db.execute("""SELECT SUM(amount_of_shares) as total_shares FROM transactions WHERE user_id = ? AND symbol = ?; """, session["user_id"], symbol)[0]

        if shares > stocks["total_shares"]:
            return apology("You don't have enough shares to sell this amount")
        price = lookup(symbol)["price"]
        shares_value = price * shares
        operation = 'Sell'

        db.execute(
            "INSERT INTO transactions (user_id, symbol, amount_of_shares, price, operation) VALUES (?, ?, ?, ?, ?)",
            session["user_id"],
            symbol.upper(),
            -shares,
            price,
            operation
        )

        db.execute(
            "UPDATE users SET cash = cash + ? WHERE id = ?",
            shares_value,
            session["user_id"],
        )

        flash("Sold!")
        return redirect("/")


    else:
        rows = db.execute("""SELECT symbol FROM transactions WHERE user_id = :user_id GROUP BY symbol HAVING SUM(amount_of_shares) > 0;""", user_id = session["user_id"])
        return render_template("sell.html", symbol = [row["symbol"] for row in rows])



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
