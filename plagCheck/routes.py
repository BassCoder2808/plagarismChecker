import os
import secrets
import math
import urllib
import re
from PIL import Image
from flask import render_template,url_for,flash,redirect,request,abort,jsonify
from plagCheck.forms import RegistrationForm,LoginForm,AccountUpdateForm,RequestResetForm,ResetPasswordForm,SuggestionForm
from plagCheck import app,db,bcrypt,mail
from plagCheck.models import User
from flask_login import login_user,current_user,logout_user,login_required
from flask_mail import Message
from requests import get
from bs4 import BeautifulSoup

@app.route("/")
@app.route("/home")
def home():
    return render_template('home.html',title='Home Page')

@app.route("/register",methods=['GET','POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(name=form.username.data,email=form.email.data,password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash(f"Your account has been successfully been created for {form.username.data}. Now you can LogIN!!!",'success')
        return redirect(url_for('login'))
    return render_template('register.html',form=form,title="User Registration")

@app.route("/login",methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password,form.password.data):
            login_user(user,remember=form.remember.data)
            next_page = request.args.get('next')
            if next_page:
                print(next_page)
                list1 = next_page.split("/")
                print(list1)
                return redirect(url_for(list1[1]))
            flash("You have been logged in successfully",'success')
            return redirect(url_for('home'))
        else:
            flash("You cannot be logged in!!!!","danger")
    return render_template('login.html',form=form,title='Login Page')


@app.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out successfully!!!!","success")
    return redirect(url_for('home'))

def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path,'static/profile_pics',picture_fn)
    output_size = (125,125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_fn


@app.route("/account",methods=['GET','POST'])
@login_required
def account():
    image_file = url_for('static',filename='profile_pics/'+current_user.image_file)
    form = AccountUpdateForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        current_user.name = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash("Your account has been updated successfully!!!",'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.name
        form.email.data = current_user.email
    return render_template("account.html",title="Profile Page",image_file=image_file,form=form)


def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message("Password Reset Email",sender="noreply@demo.com",recipients=[user.email])
    msg.body = f'''
        To reset your password visit the following link.
        {url_for('reset_token',token=token,_external=True)}
        If you did not make the change request please ignore it.
        Nothing will be changed!!!
    '''
    mail.send(msg)



@app.route("/reset_password",methods=['GET','POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email = form.email.data).first()
        send_reset_email(user)
        flash('An email has been sent with the instructions to reset password!','info')
        return redirect(url_for('login'))
    return render_template('reset_request.html',title='Reset Password',form=form)


@app.route("/reset_password/<token>",methods=['GET','POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    user = User.verified_reset_token(token)
    if user is None:
        flash("The token is invalid or expired","warning")
        return redirect(url_for('reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash(f"Your password has been changed! Now You will be able to login!!! ","success")
        return redirect(url_for('login'))
    return render_template('reset_token.html',title='Reset Password',form=form)


def send_suggestion_email(user,form):
    msg = Message(form.title.data,sender=user.email,recipients=['vedantjolly2001@gmail.com'])
    msg.body = f'The suggestion by the user is that {form.content.data}'
    mail.send(msg)

@app.route("/suggestions",methods=['GET','POST'])
@login_required
def suggestions():
    form = SuggestionForm()
    if form.validate_on_submit():
        send_suggestion_email(current_user,form)
        flash('Thank you for your valuable feedback !!! We will surely try to improve','info')
        return redirect(url_for('home'))
    return render_template('suggestion.html',title='Suggestion Page',form=form)



@app.route("/checkPlagarism")
@login_required
def checkPlagarism():
    return render_template('index.html')

@app.route('/cosineSimilarity',methods=['POST'])
@login_required
def cosineSimilarity():

    # basically a linked list which is used to unique words in our document
    # basically this will act as our dictionary
    universalSet = []
    percentageMatched = 0

    # this is used to get our input query
    inputQuery = request.form.get('plagtext')

    # we convert it into lower case so that all the combinations which are
    # same are matched only once
    # like eg: work and Work
    lowercaseQuery = inputQuery.lower()

    # Here we have removed the punctuation and replaced it with space
    # as they all are unnecessary
    queryWordList = re.sub("[^\w]", " ",lowercaseQuery).split()

    # querying through our input
    for word in queryWordList:
        if word not in universalSet:
            universalSet.append(word)


    # Here we are checking if the user has provided an optional input or not
    database = request.form.get('orgtext')
    if(not database):
            keyword = inputQuery
            print(keyword)
            # this is the search url which we are going to use
            url = "https://google.com/search?q="+keyword
            html = get(url).text
            # creating a web scraper with python
            soup = BeautifulSoup(html,features="html.parser")

            # removing all the script and style elements as we are only
            # interested with text
            for script in soup(["script", "style"]):
                script.extract()

            # extracting the text from the web page
            text = soup.get_text()
            print(text)

            # cleaning our text
            # break into lines and remove leading and trailing space on each
            lines = (line.strip() for line in text.splitlines())
            # break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # drop blank lines
            database = '\n'.join(chunk for chunk in chunks if chunk)


    database = database.lower()
    databaseWordList = re.sub("[^\w]", " ",database).split()

    for word in databaseWordList:
        if word not in universalSet:
            universalSet.append(word)



    # From here we are starting the main implementation of our code.
    # For the Plagarism detector we are using Cosine Similarity algorithm
    queryTF = []
    databaseTF = []

    for word in universalSet:
        queryTfCounter = 0
        databaseTfCounter = 0

        for word1 in queryWordList:
            if word == word1:
                queryTfCounter += 1
        queryTF.append(queryTfCounter)

        for word2 in databaseWordList:
            if word == word2:
                databaseTfCounter += 1
        databaseTF.append(databaseTfCounter)

    dotProduct = 0
    for i in range (len(queryTF)):
        dotProduct += queryTF[i]*databaseTF[i]

    queryVectorMagnitude = 0
    for i in range (len(queryTF)):
        queryVectorMagnitude += queryTF[i]**2
    queryVectorMagnitude = math.sqrt(queryVectorMagnitude)

    databaseVectorMagnitude = 0
    for i in range (len(databaseTF)):
        databaseVectorMagnitude += databaseTF[i]**2
    databaseVectorMagnitude = math.sqrt(databaseVectorMagnitude)

    percentageMatched = (float)(dotProduct / (queryVectorMagnitude * databaseVectorMagnitude))*100


    output = percentageMatched
    output = round(output,2)
    return render_template('index.html', plag_meter='Plagiarism Match: {}%'.format(output))

