import os, webapp2, math, re, json, datetime # import stock python methods
import jinja2 # need to install jinja2 (not stock)
import caching, cacheupdate, dbmodels, hashing, validuser, gqlqueries
from dbmodels import Users, Wiki
import time

# setup jinja2
template_dir = os.path.join(os.path.dirname(__file__), 'templates') #s et template_dir to main.py dir(current dir)/templates
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True) # set jinja2's working directory to template_dir

class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw): # simplifies self.response.out.write to self.write
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params): # creates the string that will render html using jinja2 with html template named template and parameters named params
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw): # writes the html string created in render_str to the page
        self.write(self.render_str(template, **kw))

    def __init__(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        c = self.request.cookies.get('user') # pull cookie value
        uid = ""
        if c:
            uid = hashing.check_secure_val(c)

        self.user = uid and caching.cached_get_user_by_id(uid)

        if not self.user and self.request.path in auth_paths:
            self.redirect('/login')

class MainHandler(Handler):
    def render_main(self):
        # pull username
        if self.user:
            user = self.user.username # get username from user object
        else:
            user = ""

        # self.render("home.html", user=user, fakeBbArticle=fakeBbArticle, yahooArticle=yahooArticle)
        self.write("home")

    def get(self):
        self.render_main()

class Registration(Handler):
    def render_reg(self, username="", email="", usernameError="", passwordError="", passVerifyError="", emailError=""):
        # pull username
        if self.user:
            user = self.user.username # get username from user object
        else:
            user = ""

        self.render("registration.html", username=username, email=email, usernameError=usernameError, passwordError=passwordError, passVerifyError=passVerifyError, emailError=emailError, user=user)

    def get(self):
        self.render_reg()

    def post(self):
        username = self.request.get("username")
        password = self.request.get("password")
        passVerify = self.request.get("passVerify")
        email = self.request.get("email")
        error = False

        # check password
        if not password: # check if password is blank
            passwordError = "Password cannot be empty"
            error = True
        elif not validuser.valid_password(password): # check if password is valid
            passwordError = "Invalid Password"
            error = True
        else:
            passwordError = ""
        # check password verification
        if not passVerify: # check if password verification is blank
            passVerifyError = "Password Verification cannot be empty"
            error = True
        elif password != passVerify: # check if password matches password verification
            passVerifyError = "Passwords do not match"
            error = True
        else:
            passVerifyError = ""
        # check username
        if not username: # check if username is blank
            usernameError = "Username cannot be empty"
            error = True
        elif not validuser.valid_username(username): # check if username if valid
            usernameError = "Invalid Username"
            error = True
        elif caching.cached_check_username(username): # check if username is unique
            usernameError = "That username is taken"
            error = True
        else:
            usernameError = ""
        # check email
        if not email: # check if email is blank
            emailError = ""
        elif not validuser.valid_email(email): # check if email is valid
            emailError = "Invalid Email"
            error = True
        else:
            emailError = ""
        # see if any errors returned
        if error == False:
            username = username
            password = hashing.make_pw_hash(username, password) # hash password for storage in db
            authorization = "basic"
            user = Users(username=username, password=password, email=email, authorization=authorization) # create new users object named user
            user.put() # store post in database
            user_id = user.key().id()
            self.response.headers.add_header('Set-Cookie', 'user=%s' % hashing.make_secure_val(user_id)) # hash user id for use in cookie

            time.sleep(.2) # wait 2/10 of a second while post is entered into db

            # update cache
            caching.cached_user_by_name(username, True)
            caching.cached_check_username(username, True)
            caching.cached_get_users(True)

            self.redirect('/welcome')
        else:
            self.render_reg(username, email, usernameError, passwordError, passVerifyError, emailError)

class Login(Handler):
    def render_login(self, username="", error=""):
        # pull username
        if self.user:
            user = self.user.username # get username from user object
        else:
            user = ""

        self.render("login.html", username=username, error=error, user=user)

    def get(self):
        self.render_login()

    def post(self):
        username = self.request.get("username")
        password = self.request.get("password")

        if not caching.cached_check_username(username):
            error = "Invalid login"
        else:
            user_id = caching.cached_check_username(username)
            u = caching.cached_get_user_by_id(user_id)
            p = u.password
            salt = p.split("|")[1]
            if username == u.username:
                if hashing.make_pw_hash(username, password, salt) == p:
                    error = ""
                else:
                    error = "invalid login - pass"

        if error:
            self.render_login(username, error)
        else:
            self.response.headers.add_header('Set-Cookie', 'user=%s' % hashing.make_secure_val(user_id)) # hash user id for use in cookie
            self.redirect('/welcome')

class Logout(Handler):
    def get(self):
        self.response.headers.add_header('Set-Cookie', 'user=""; expires=Thu, 01-Jan-1970 00:00:10 GMT') #clear cookie
        self.redirect('/registration')

class Welcome(Handler):
    def render_welcome(self):
        c = self.request.cookies.get('user') # pull cookie value
        usr = hashing.get_user_from_cookie(c)

        self.redirect('/')

    def get(self):
        self.render_welcome()

class EditPage(Handler):
    def render_edit(self, url=""):
        self.write("edit")

    def get(self, url=""):
        self.render_edit()

class WikiPage(Handler):
    def render_wiki(self):
        self.write("wiki")

    def get(self):
        self.render_wiki()

# PAGE_RE = r'(/(?:[a-zA-Z0-9_-]+/?)*)'

app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/registration/?', Registration),
    ('/login/?', Login),
    ('/logout/?', Logout),
    ('/welcome/?', Welcome),
    webapp2.Route('/_edit/<url:[a-zA-Z0-9_-]>', EditPage),
    webapp2.Route('/<url:[a-zA-Z0-9_-]>', WikiPage)
], debug=True)

auth_paths = [ # must be logged in as admin to access these links
    webapp2.Route('/_edit/<url:[a-zA-Z0-9_-]>')
]
