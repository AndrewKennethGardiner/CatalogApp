# A program to create a Catalog
# Tables are utilised from the database_setup file
# There is a User table - created to keep track of who owns data
# and also to ensure that only owners have access
# There is a Category table that is the high level table
# The Category table has items that are in the Items table


from flask import Flask, render_template, request
from flask import redirect, url_for, flash, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Category, Item, User
from flask import session as login_session
import random
import string

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests
import ctypes
import dicttoxml
from xml.dom.minidom import parseString
from sqlite3 import Row

app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']

APPLICATION_NAME = "Catalog Application"

engine = create_engine('sqlite:///catalog.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# The first group of functions deal with the login process
# Thanks to the Udacity 'Authentification and Authorisation' progam that was
# so useful in setting up the OAuth and login processes

# Create a state token to prevent request forgery
# store it in the session for later validation
# Create anti-forgery state token
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


# Set up the Facebook Connection - thanks again to Udacity and Facebook
@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = request.data
    print "access token received %s " % access_token

    app_id = json.loads(open('fb_client_secrets.json', 'r').read())[
        'web']['app_id']
    app_secret = json.loads(
        open('fb_client_secrets.json', 'r').read())['web']['app_secret']
    url = 'https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s' % (
        app_id, app_secret, access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]

    # Use token to get user info from API
    userinfo_url = "https://graph.facebook.com/v2.2/me"
    # strip expire tag from access token
    token = result.split("&")[0]

    url = 'https://graph.facebook.com/v2.4/me?%s&fields=name,id,email' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    # print "url sent for API access:%s"% url
    # print "API JSON result: %s" % result
    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    login_session['facebook_id'] = data["id"]

    # The token must be stored in the login_session in order to properly
    # logout, let's strip out the information before the
    # equals sign in our token
    stored_token = token.split("=")[1]
    login_session['access_token'] = stored_token

    # Get user picture
    url = 'https://graph.facebook.com/v2.4/me/picture?%s&redirect=0&height=200&width=200' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    data = json.loads(result)

    login_session['picture'] = data["data"]["url"]

    # see if user exists
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']

    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px; border-radius: 150px; -webkit-border-radius: 150px; -moz-border-radius: 150px;"> '

    flash("Now logged in as %s" % login_session['username'])
    return output


# Facebook disconnection function
@app.route('/fbdisconnect')
def fbdisconnect():
    facebook_id = login_session['facebook_id']
    # The access token must me included to successfully logout
    access_token = login_session['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' % (facebook_id, access_token)
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    return "you have been logged out"


# Google connection function
@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps
                                 ('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['credentials'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    # ADD PROVIDER TO LOGIN SESSION
    login_session['provider'] = 'google'

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(data["email"])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px; border-radius: 150px; -webkit-border-radius: 150px; -moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output


# Google disconnection function
@app.route('/gdisconnect')
def gdisconnect():
    # Only disconnect a connected user.
    credentials = login_session.get('credentials')
    if credentials is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = credentials
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] != '200':
        # For whatever reason, the given token was invalid.
        response = make_response(
            json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


# Disconnect based on provider
# Thanks again to Udacity program
@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            del login_session['gplus_id']
            del login_session['credentials']
        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        flash("You have successfully been logged out.")
        return redirect(url_for('catalogList'))
    else:
        flash("You were not logged in")
        return redirect(url_for('catalogList'))


# A funciton to create a user from the login session
def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


# A function to get user information based on the users id
# Not called- can be deleted.
def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


# A function that uses the unique email to get the user id
def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# A function that returns the category name when passed the category id
# Needed so the url can use categorn name and be more readable
# Not called can be deleted.
def getCategoryName(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    return category.name


# A function that returns the category id given teh category name
# The category name must be unique
def getCategoryId(category_name):
    category = session.query(Category).filter_by(name=category_name).one()
    return category.id


# Ouputs the JSON based on a category name
@app.route('/catalog/<category_name>/items/JSON/')
def categoryJSON(category_name):
    category = session.query(Category).filter_by(name=category_name).one()
    itemsFound = session.query(Item).filter_by(
        category_id=category.id).all()
    return jsonify(Items=[i.serialize for i in itemsFound])


# Outputs a JSON based on a particular item in a category
@app.route('/catalog/<category_name>/<item_name>/JSON')
def categoryItemJSON(category_name, item_name):
    category_id = getCategoryId(category_name)
    itemFound = session.query(Item).filter_by(name=item_name).filter_by(
        category_id=category_id).one()
    return jsonify(Item=itemFound.serialize)


# Ouputs the XML based on a category name
@app.route('/catalog/<category_name>/items/XML/')
def categoryXML(category_name):
    category = session.query(Category).filter_by(name=category_name).one()
    # The result does not output the <> required or at least does not show them in Chrome
    # my_rows = []
    # for u in session.query(Item.name, Item.description, Item.picture).filter_by(category_id=category.id):
    #    newrow = "".join((u.name,u.description,u.picture))
    #    myrows = my_rows.append(newrow)
    # xml = dicttoxml.dicttoxml(my_rows, custom_root='catalog', attr_type=False)
    # return xml
    my_query = session.query(Item.name, Item.description, Item.picture).filter_by(category_id=category.id).all()
    xml = dicttoxml.dicttoxml(my_query, custom_root='catalog', attr_type=False)
    fred = parseString(xml).toprettyxml()
    return xml


# This is the main function and the start point for the application
# The /root directory points to the catalog directory
@app.route('/')
@app.route('/catalog/')
def catalogList():
    category = session.query(Category)
    item = session.query(Item).order_by('-id')
    # If the user has not logged in then a html page is called that does
    # not allow editing.
    # If the user is logged in then a html with different links
    if 'username' not in login_session:
        return render_template('publicMenu.html', category=category, item=item)
    else:
        # This menu has a link to a 'New Category' as the user is logged in
        return render_template('menu.html', category=category, item=item)


# This function shows a Category on the left of the screen
# and the items in that category on the right
@app.route('/catalog/<category_name>/', methods=['GET', 'POST'])
def categoryList(category_name):
    category = session.query(Category).filter_by(name=category_name).one()
    # order by id gives the most recent first
    item = session.query(Item).filter_by(category_id=category.id)
    # If the user is not logged in they are directed to a html page
    # that does not allow editing
    if 'username' not in login_session:
        return render_template('publicCategoryList.html',
                               category=category, item=item)
    else:
        # The program allows a user who does not own a category to create an
        # item in that category
        # If the user owns the Category then they are sent to the html
        # that allows the category details to be edited.
        # If the user is logged in but does not own the category
        # they are sent to a html where they can still review items.
        if login_session['user_id'] != category.user_id:
            return render_template('categoryList.html',
                                   category=category, item=item)
        else:
            return render_template('editCategoryList.html',
                                   category=category, item=item)


# A function that allows a user that is logged in to create a new category.
@app.route('/catalog/new/', methods=['GET', 'POST'])
def newCategory():
    # If the user is not logged in they are sent to the log in page
    if 'username' not in login_session:
        return redirect('/catalog/login')
    if request.method == 'POST':
        newCategory = Category(name=request.form['name'],
                               picture=request.form['picture'],
                               user_id=login_session['user_id'])
        # The primary ID in the Catalog table is the 'id' field.
        # The 'name' field was created with the unique identifier.
        # To ensure that the error was trapped a test was created
        # if the proposed new name was already used.
        x = session.query(Category).all()
        failTest = False
        for a in x:
            if a.name == newCategory.name:
                flash("This Category already exists!")
                failTest = True
                break
        if not failTest:
            session.add(newCategory)
            session.commit()
            flash("New Category Created!")
        return redirect(url_for('catalogList'))
    else:
        return render_template('newCategory.html')


# A function that allows a category to be edited.
@app.route('/catalog/<category_id>/edit/', methods=['GET', 'POST'])
def editCategory(category_id):
    editedCategory = session.query(Category).filter_by(id=category_id).one()
    # A user that is not logged in is not allowed to edit.
    if 'username' not in login_session:
        return render_template('publicCategoryList.html',
                               category_name=EditedCategory.name)
    # A user that is logged in but is not the creator of this category
    # does not have the ability to change the details.
    if login_session['user_id'] != editedCategory.user_id:
        return render_template('CategoryList.html',
                               category_name=category_name,
                               item_name=item_name, itemToEdit=editedItem)
    # Finally if you are logged and own the category item you can edit it.
    if request.method == 'POST':
        if request.form['name']:
            editedCategory.name = request.form['name']
        if request.form['picture']:
            editedCategory.picture = request.form['picture']
        # Again is the category name that is amended already exists the changes
        # are abandoned.
        x = session.query(Category).all()
        failTest = False
        for a in x:
            if a.name == editedCategory.name and a.id != editedCategory.id:
                flash("This Category already exists!")
                failTest = True
                break
        if not failTest:
            session.add(editedCategory)
            session.commit()
            flash("Category has been edited!")
    return redirect(url_for('categoryList', category_name=editedCategory.name))


# A function that creates an item that is linked to the 'category name'
@app.route('/catalog/<category_name>/new/', methods=['GET', 'POST'])
def newItem(category_name):
    # If a user is not logged in then they can not create a new item.
    # They are sent to the login page.
    if 'username' not in login_session:
        return redirect('/catalog/login')
    category_id = getCategoryId(category_name)
    current_category = session.query(Category).filter_by(id=category_id).one()
    # A decison was made that regardless of whether the logged in user was the
    # owner of the category if they were logged in they could add an item to
    # the category and own that item.
    if request.method == 'POST':
        newItem = Item(
            name=request.form['name'],
            description=request.form['description'],
            picture=request.form['picture'], category_id=category_id,
            user_id=login_session['user_id'])
        session.add(newItem)
        session.commit()
        flash("New Item Created!")
        return redirect(url_for('categoryList', category_name=category_name))
    else:
        return render_template('newItem.html', current_category=current_category)


# A function that allows an item to be edited by the owner of the item.
@app.route('/catalog/<category_name>/<item_name>/edit/',
           methods=['GET', 'POST'])
def editItem(category_name, item_name):
    category_id = getCategoryId(category_name)
    editedItem = session.query(Item).filter_by(name=item_name).filter_by(category_id=category_id).one()
    # If the user is not logged in then they are sent to a 'public' html.
    # At this time they can simply look at the item.
    if 'username' not in login_session:
        return render_template('publicItem.html', category_name=category_name,
                               item_name=item_name, itemToEdit=editedItem)
    # If the user is logged in but does not own the item then they can look
    # at the item but not amend it.
    # Arguably the owner of the category should be able to amend - decided no.
    if login_session['user_id'] != editedItem.user_id:
        return render_template('publicItem.html', category_name=category_name,
                               item_name=item_name, itemToEdit=editedItem)
    # If you own the item you can amend it.
    if request.method == 'POST':
        if request.form['name']:
            editedItem.name = request.form['name']
        if request.form['description']:
            editedItem.description = request.form['description']
        if request.form['picture']:
            editedItem.picture = request.form['picture']
        session.add(editedItem)
        session.commit()
        flash("Item has been edited!")
        return redirect(url_for('categoryList', category_name=category_name))
    else:
        return render_template('editItem.html', category_name=category_name,
                               item_name=item_name, itemToEdit=editedItem)


# A function that allows an item to be deleted by the owner of the item.
@app.route('/catalog/<category_name>/<item_name>/delete/',
           methods=['GET', 'POST'])
def deleteItem(category_name, item_name):
    # If user not logged in then they can not delete.
    if 'username' not in login_session:
        return redirect('/catalog/login')
    # If user does not own item then they can not delete it.
    # We get the current item using the category id function
    category_id = getCategoryId(category_name)
    itemToDelete = session.query(Item).filter_by(name=item_name).filter_by(category_id=category_id).one()
    if login_session['user_id'] != itemToDelete.user_id:
        return render_template('publicItem.html', category_name=category_name,
                               item_name=item_name, itemToEdit=itemToDelete)
    # Allow the user to delete an item.
    if request.method == 'POST':
        session.delete(itemToDelete)
        session.commit()
        flash("Item has been deleted!")
        return redirect(url_for('categoryList', category_name=category_name))
    else:
        return render_template('deleteItem.html',
                               category_name=category_name,
                               itemToDelete=itemToDelete)

# The main code.
# This code sets the port to be 8000.
if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
