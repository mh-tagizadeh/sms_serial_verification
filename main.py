from flask import Flask, request, jsonify
from pandas import read_excel
import requests
import config
import sqlite3
import re
app = Flask(__name__)

@app.route('/')
def hello():
    return "hello world"


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

def normalize_string(str):
    from_char = "1234567890" # the other time convert to persian numbers
    to_char = "1234567890" # the other time convert to persian numbers
    for i in range(len(from_char)):
        str = str.replace(from_char[i], to_char[i])
    str = re.sub(r'\W+', '', str) #remove any non alphanumric
    str = str.upper()
    return (str)







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
    conn = sqlite3.connect(config.DATABASE_FILE_PATH)
    cur = conn.cursor()

    # remvoe the serial table if exists
    cur.execute('DROP TABLE IF EXISTS serials')
    cur.execute("""CREATE TABLE IF NOT EXISTS serials(
        id INTEGER PRIMARY KEY,
        ref TEXT,
        desc TEXT,
        start_serial TEXT,
        end_serial TEXT,
        date DATE); 
        """)
    conn.commit()

    serial_counter = 0 
    df = read_excel(filepath, 0) 
    for index, (line, ref, desc, start_serial, end_serial, date) in df.iterrows():
        start_serial = normalize_string(start_serial)
        end_serial = normalize_string(end_serial)
        query = f"""INSERT INTO serials 
        VALUES ("{line}", "{ref}", "{desc}", "{start_serial}", "{end_serial}", "{date}")
        """
        cur.execute(query)
        # TODO: do some more error handling
        if serial_counter % 10 == 0:
            conn.commit()    
        serial_counter += 1
    conn.commit()
        
    

    # now lets save invalid serials

    # remvoe the serial table if exists, then create the new one 
    cur.execute('DROP TABLE IF EXISTS invalids')
    cur.execute(""" CREATE TABLE IF NOT EXISTS invalids (
        invalid_serial TEXT PRIMARY KEY
    )
    """)
    conn.commit()
    invalid_counter = 0
    df = read_excel(filepath, 1) 
    # sheet one contains failed serial numbers. only one column
    for index, (faild_serial, ) in df.iterrows():
        query = f'INSERT INTO invalids VALUES ("{faild_serial}")'
        cur.execute(query)
        # TODO: do some more error handling
        if invalid_counter % 10 == 0:
            conn.commit()    
        invalid_counter += 1
    conn.commit()

    conn.close()
    
    return (serial_counter, invalid_counter)


def check_serial(serial):
    """ this function will get one serial number  and serial appropriate
    answer to that, after consulting the db
    """
    conn = sqlite3.connect(config.DATABASE_FILE_PATH)
    cur = conn.cursor()

    query = f"SELECT * FROM invalids WHERE invalid_serial == '{serial}'"
    results = cur.execute(query)
    if len(results.fetchall()) == 1:
        return 'this serial is among failed ones' # TODO : return the string provided by the customer

    query = f"SELECT * FROM serials WHERE start_serial < '{serial}' and  end_serial > '{serial}'"
    print(query)
    results = cur.execute(query)
    if len(results.fetchall()) == 1:
        return 'I found your serial' # TODO: return the string provided by the customer     
    return 'It was not a db.' 
    
@app.route('/process', methods = ['POST', 'GET'])
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
    import_database_from_excel('data.xlsx')
    print(check_serial("JJ140"))
    app.run(debug = True)