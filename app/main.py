import re
import os
import requests


from flask import Flask, flash,request, jsonify,flash, abort, redirect, render_template, url_for, Response
import flask_login
from pandas import read_excel
from werkzeug.utils import secure_filename
import config
import MySQLdb 
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
limiter = Limiter(
    app,
    key_func=get_remote_address,
)

UPLOAD_FILE = config.UPLOAD_FILE 
ALLOWED_EXTENSIONS = config.ALLOWED_EXTENSIONS 

CALL_BACK_TOKEN = config.CALL_BACK_TOKEN 












login_manager = flask_login.LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(flask_login.UserMixin):
    def __init__(self, id):
        self.id = id
    
    def __repr__(self):
        return "%d" % (self.id)


user = User(0)

app.config.update (
    SECRET_KEY = config.SECRET_KEY
)


@app.route('/login', methods = ['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if request.method == 'POST': 
        username = request.form['username']
        password = request.form['password']
        if password == config.PASSWORD and username == config.USERNAME:
            flask_login.login_user(user)
            return redirect('/') 
        else :
            return abort(401)
    else:

        html_str = Response('''
        <form action="" method = "post">
            <P>
                <input type=text name="username">
            </P>
            <P>
                <input type=password name="password">
            </P>
            <P>
                <input type=submit value=Login>
            </P>
        </form>
        ''')
        return render_template('login.html')
    


@app.route('/check_one_serial', methods = [ 'POST'])
@flask_login.login_required
def check_one_serial():
    serial_to_check = request.form['serial']
    answer = check_serial(normalize_string(serial_to_check))
    flash(answer , 'info')

    return redirect('/')




@app.route('/logout')
@flask_login.login_required
def logout():
    flask_login.logout_user()
    flash('Logged out')
    return redirect('/login')

@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404
@app.route('/protected')
@flask_login.login_required
def protected():
    return 'Logged in as: ' + flask_login.current_user.id


def allowed_file(filename):
      return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# @app.route('/')
# def hello():
#     """
#     docstring
#     """
#     return 'hello'

@app.route('/', methods = ['GET', 'POST'])
@flask_login.login_required
def home():
    # if flask_login.current_user.is_authenticated:
    #   return redirect('/')
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # app.config['UPLOAD_FOLDER']
            file_path = os.path.join(config.UPLOAD_FILE ,filename)
            file.save(file_path)
            rows, failures = import_database_from_excel(file_path)
            flash(f'Imported { rows } rows of serials and {failures} rows of failure', 'success')
            os.remove(file_path)
            return redirect('/')
            #return redirect(url_for('uploaded_file', filename=filename))
    return render_template('index.html')







@login_manager.user_loader
def user_loader(userid):
    return User(userid)


@app.route('/v1/ok')
def health_check():
    ret = {'message' : 'ok'}
    return jsonify(ret), 200



def send_sms(receptor, message):
    """  this function will get a MSISDN and a message, then 
    uses Kabenegar to send sms.
    """
    # url = f'https://api.kavenegar.com/v1/{config.API_KEY}/sms/send.json'
    url = f"http://127.0.0.1:8000/v1/{config.API_KEY}"
    data = { 'message': message,
                'receptor' : receptor}
    res = requests.post(url, data)
    print(f"message *{message}* sent. status code is {res.status_code}")

def normalize_string(data, fixed_size = 30):
    from_persian_char = "1234567890" # the other time convert to persian numbers
    from_arabic_char = "1234567890" # the other time convert to persian numbers
    to_char = "1234567890" # the other time convert to persian numbers
    for i in range(len(to_char)):
        data = data.replace(from_persian_char[i], to_char[i])
        data = data.replace(from_arabic_char[i], to_char[i])
    data = data.upper()
    data = re.sub(r'\W+', '', data) #remove any non alphanumric
    all_alpha = ''
    all_digit = ''
    for c in data:
        if c.isalpha():
            all_alpha += c
        elif c.isdigit():
            all_digit += c

    missing_zeros = fixed_size - len(all_alpha) - len(all_digit)
    data = all_alpha + '0' * missing_zeros + all_digit
    return (data)







def import_database_from_excel(filepath):
    """ get an excel file name and imports lookup data (data and failures) from it
        the first (0) sheet contain serial data like:
        Row Refrence Number Start Serial End Serial Date
        and the 2nd (1) contains a column of invalid serials.  

        This data will be written   into the sqlite database located at config.DATABASE_FILE_PATH 
        into two tables. "serials and invalids"

        returns two integers : (number of serial rows, number of invalid rows)
    """
    # df contains lookup data in the form of
    # Row Refrence Number Start Serial End Serial Date

    # TODO: do some more normaliziation
    # TODO: make sure that the data is imported corectly, we need to backup the old one    

    ## our sqlite3 database will contain tow tables : serial and invalids
    db = MySQLdb.connect(host=config.MYSQL_HOST,port=3307,user=config.MYSQL_USERNAME,
                          passwd=config.MYSQL_PASSWORD,db=config.MYSQL_DBNAME)
    cur = db.cursor()

    # remvoe the serial table if exists
    cur.execute('DROP TABLE IF EXISTS serials')
    cur.execute("""CREATE TABLE serials(
        id INTEGER PRIMARY KEY,
        ref VARCHAR(200) ,
        description VARCHAR(200) ,
        start_serial CHAR(30) ,
        end_serial CHAR(30) ,
        date DATETIME); 
        """)
    db.commit()

    serial_counter = 0 
    df = read_excel(filepath, 0) 
    for index, (line, ref, description , start_serial, end_serial, date) in df.iterrows():
        start_serial = normalize_string(start_serial)
        end_serial = normalize_string(end_serial)
        cur.execute( "INSERT INTO serials VALUES (%s ,%s,%s,%s,%s,%s)", (
            line, ref, description, start_serial, end_serial, date)
            )
        
        # TODO: do some more error handling
        if serial_counter % 10 == 0:
            db.commit()    
        serial_counter += 1
    db.commit()
        
    

    # now lets save invalid serials

    # remvoe the serial table if exists, then create the new one 
    cur.execute('DROP TABLE IF EXISTS invalids')
    cur.execute(""" CREATE TABLE invalids (
        invalid_serial CHAR(30)
    );
    """)
    db.commit()
    invalid_counter = 0
    df = read_excel(filepath, 1) 
    # sheet one contains failed serial numbers. only one column
    for index, (faild_serial, ) in df.iterrows():
        cur.execute('INSERT INTO invalids VALUES (%s);', (faild_serial, ))

        # TODO: do some more error handling
        if invalid_counter % 10 == 0:
            db.commit()    
        invalid_counter += 1
    db.commit()

    db.close()
    
    return (serial_counter, invalid_counter)


def check_serial(serial):
    """ this function will get one serial number  and serial appropriate
    answer to that, after consulting the db
    """
    db = MySQLdb.connect(host=config.MYSQL_HOST,port=3307,user=config.MYSQL_USERNAME,
                          passwd=config.MYSQL_PASSWORD,db=config.MYSQL_DBNAME)
    cur = db.cursor()

    results = cur.execute("SELECT * FROM invalids WHERE invalid_serial = %s", (serial, ))
    if results > 0:
        db.close()
        return 'this serial is among failed ones' # TODO : return the string provided by the customer

    query = f"SELECT * FROM serials WHERE start_serial <= %s and  end_serial >= %s "
    # print(query)
    results = cur.execute(query, (serial, serial))
    if results > 1:
        db.close()
        return 'I found your serial' # TODO: fix with proper message
    if results  == 1:
        ret = cur.fetchone()
        desc = ret[2]
        db.close()
        return 'I found your serial', desc # TODO: return the string provided by the customer     
    db.close()
    return 'It was not a db.' 
    
@app.route('/v1/{CALL_BACK_TOKEN}/process', methods = ['POST', 'GET'])
def process():
    """ this is call back from Kavenegar. will get sender and message and 
    will check if it is valid, then ansewr back.
    """
    if request.method == 'POST':
        data = request.form
        # import pdb; pdb.set_trace()
        sender = data['from'] 
        message = normalize_string(data['message']) 
        print(f'recived {message} from {sender}') # TODO: logging
        answer = check_serial(message)
        send_sms(sender,answer)
        ret = {'message' : 'processed'}
        return jsonify(ret), 200
        


if __name__ == '__main__':
    # send_sms('09216273839', 'Hi there.')
    # a, b = import_database_from_excel('data.xlsx')
    # print(f'inserted {a} rows and {b} invalids ')
    #import_database_from_excel('/home/hosein/w/data.xlsx')
    #ss = ['', '1' , 'A', 'JM110','JM0000000000000000000000101','JM0000000000000000000000000101' ,'JM0000000000000000000109', 'JM101', 'JJ0000000000000000000007654321']
    # print(check_serial("JJ140"))
    #for s in ss:
    #    print(check_serial(s))
    app.run(debug = True)
    
