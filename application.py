from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    
    # check current cash from user
    rows = db.execute("SELECT cash FROM users WHERE id=:user_id", user_id=session["user_id"])
    cash = rows[0]["cash"]
    
    # get all the users stocks
    portfolio = db.execute("SELECT symbol, shares FROM portfolio where id=:user_id", user_id=session["user_id"])
    
    # get names, current price for those stocks, calulate total
    stock_total = 0.0
    for i in range(len(portfolio)):
        portfolio[i]["name"] = lookup(portfolio[i]["symbol"])["name"]
        portfolio[i]["price"] = usd(lookup(portfolio[i]["symbol"])["price"])
        portfolio[i]["total"] = usd(portfolio[i]["shares"] * lookup(portfolio[i]["symbol"])["price"])
        stock_total += lookup(portfolio[i]["symbol"])["price"] * portfolio[i]["shares"]
    
    total = usd(stock_total + cash)
    cash = usd(cash)
    
    return render_template("index.html", portfolio=portfolio, cash=cash, total=total)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # ensure that no fields are empty
        if not request.form.get("symbol"):
            return apology("must provide stocks to buy")
            
        elif not request.form.get("shares"):
            return apology("must specify number of shares")
            
        elif not request.form.get("shares").isdigit() or int(request.form.get("shares")) <= 0:
            return apology("must enter positive interger value for share number")
    
        result = lookup(request.form.get("symbol"))
        
        if result == None:
            return apology("symbol entered could not find a valid stock")
    
        # now we know the stock the user wants to buy and how much
        # check to see if the user has enough cash 
        rows = db.execute("SELECT cash FROM users WHERE id=:user_id", user_id=session["user_id"])
        cash = rows[0]["cash"]
        
        #if cash < result["price"] * int(request.form.get("shares")):
        recount = cash - int(request.form.get("shares"))*result["price"]
        if recount < 0:
            return apology("Insufficient funds to buy shares")
        
        #then add the shares to the users history
        db.execute("INSERT INTO history (id, symbol, shares, price) VALUES(:user_id, :symbol, :shares, :price)", 
                    user_id=session["user_id"], symbol=result["symbol"],
                    shares=request.form.get("shares"), price=result["price"])
        
        #add this action to the user's portfolio 
        assets = db.execute("SELECT symbol, shares FROM portfolio WHERE id=:user_id AND symbol=:symbol",
                user_id=session["user_id"], symbol=result["symbol"])
        
        if len(assets) == 0:
            db.execute("INSERT INTO portfolio (id, symbol, shares) VALUES(:user_id, :symbol, :shares)",
                        user_id=session["user_id"], symbol=result["symbol"],
                        shares=request.form.get("shares"))
                        
        else:
            new_shares = assets[0]["shares"] + int(request.form.get("shares"))
            db.execute("UPDATE portfolio SET shares=:share WHERE id=:user_id AND symbol=:symbol",
                        share=new_shares, user_id=session["user_id"], symbol=result["symbol"])
            
        #update cash
        db.execute("UPDATE users SET cash=:cash WHERE id=:user_id", 
                    cash=recount, user_id=session["user_id"])
                    
        # redirect user to home page
        return redirect(url_for("index"))
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else: 
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    if request.method == "GET":
        history = db.execute("SELECT symbol, shares, price, time FROM history WHERE id=:user_id",
                    user_id=session["user_id"])
                    
        for i in range(len(history)):
            if history[i]["shares"] > 0:
                history[i]["action"] = 'Bought ' + str(history[i]["shares"])
            elif history[i]["shares"] < 0:
                history[i]["action"] = 'Sold ' + str(abs(history[i]["shares"]))
            history[i]["name"] = lookup(history[i]["symbol"])["name"]
            history[i]["value"] = usd(history[i]["price"])
        
        return render_template("history.html", history=history)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        #return render_template("success.html")
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        
        # ensure symbol was submitted
        if not request.form.get("quote"):
            return apology("Must provide a symbol to search")

        # look for that stock given the symbol
        result = lookup(request.form.get("quote"))
        
        # ensure such a stock exists
        if result == None:
            return apology("symbol does not exist or could not be found")
            
        return render_template("quoted.html", name=result["name"], symbol=result["symbol"], price=usd(result["price"]))
        
    # else if user reached route via GET (as by clicking a link or via redirect)    
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    
    #forget any user id
    session.clear()
    
    if request.method == "POST":
        
        # ensure username was submitted
        if not request.form.get("username"):
            return apology("Must provide username")
        
        # ensure passwords match and that they are not empty submissions
        elif not request.form.get("password") or not request.form.get("password_confirm"):
            return apology("Must provide passwords to confirm")
        
        elif not request.form.get("password") == request.form.get("password_confirm"):
            return apology("Passwords do not match")
    
        # hash the password
        hash = pwd_context.encrypt(request.form.get("password"))
        
        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=request.form.get("username"), hash=hash)
        
        # check that the username is not taken and that INSERT INTO was performed in SQL
        if not result:
            return apology("Username already taken!")
        
        # automatically sign registrant in
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        session["user_id"] = rows[0]["id"]
        
        return redirect(url_for("index"))
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "POST":
        
        # ensure that no fields are empty
        if not request.form.get("symbol"):
            return apology("must provide stocks to sell")
            
        elif not request.form.get("shares"):
            return apology("must specify number of shares")
            
        elif not request.form.get("shares").isdigit() or int(request.form.get("shares")) <= 0:
            return apology("must enter positive interger value for share number")
            
        # look to see if that user has those shares
        shares = db.execute("SELECT symbol, shares FROM portfolio WHERE id=:user_id AND symbol=:symbol",
                            user_id=session["user_id"], symbol=request.form.get("symbol").upper())
                            
        if len(shares) == 0:
            return apology("You do not own any shares with symbol {}".format(request.form.get("symbol")))

        elif shares[0]["shares"] < int(request.form.get("shares")):
            return apology("You do not own that many shares of stock {}".format(request.form.get("symbol")))
            
        # adjust shares appropriately
        result = lookup(request.form.get("symbol"))
        
        new_shares = shares[0]["shares"] - int(request.form.get("shares"))
        db.execute("UPDATE portfolio SET shares=:shares WHERE id=:user_id AND symbol=:symbol",
                    shares=new_shares, user_id=session["user_id"], symbol=request.form.get("symbol").upper())
        
        #then add the shares to the users history
        db.execute("INSERT INTO history (id, symbol, shares, price) VALUES(:user_id, :symbol, :shares, :price)", 
                    user_id=session["user_id"], symbol=result["symbol"],
                    shares= -1 * int(request.form.get("shares")), price=result["price"])
                    
        # update cash appropriately
        rows = db.execute("SELECT cash FROM users WHERE id=:user_id", user_id=session["user_id"])
        cash = rows[0]["cash"]
        cash += result["price"]
        
        
        db.execute("UPDATE users SET cash=:cash WHERE id=:user_id", cash=cash, user_id=session["user_id"])
        
        # redirect user to home page
        return redirect(url_for("index"))
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("sell.html")