from flask import Flask, render_template, request, jsonify
import config
app = Flask(__name__)

@app.route('/')
def student():
   return render_template('student.html')


@app.route('/v1/<API_KEY>', methods = ['POST'])
def recived_message(API_KEY):
   if API_KEY == config.API_KEY:
      data = request.form
      serial_number = data['receptor']
      message = data['message']
      d = {'s' : serial_number, 'm' : message}
      print(f"recevied from {serial_number} message {message}.")
      return jsonify(d), 200
   



@app.route('/result', methods = ['POST', 'GET'])
def result():
    if request.method == 'POST':
        result = request.form
        return render_template('result.html', result = result)
    
    

if __name__ == '__main__':
   app.run('127.0.0.1', 8000 , debug=True)